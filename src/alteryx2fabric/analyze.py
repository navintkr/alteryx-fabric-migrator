"""Batch analysis of multiple Alteryx workflows.

Given a folder of `.yxmd` files, produce:
  1. Per-workflow report: tool counts, plugin breakdown, inputs/outputs,
     macro refs, complexity score, estimated migration effort.
  2. Dependency graph: edges A -> B when an output of A is consumed as input by B.
  3. Duplicate clusters: exact-structure duplicates + near-duplicates by Jaccard.
"""
from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path

from .parse import parse_yxmd


# ----------------------------- per-workflow report -----------------------------

@dataclass
class WorkflowReport:
    name: str
    path: str
    size_bytes: int
    tool_count: int
    connection_count: int
    input_count: int
    output_count: int
    macro_count: int
    formula_count: int
    join_count: int
    container_count: int
    top_plugins: str   # "Formula:12, Filter:8, Join:5"
    inputs: str        # ";"-joined
    outputs: str       # ";"-joined
    complexity_score: int
    effort: str        # S / M / L / XL
    structure_hash: str
    error: str = ""


def _short(plugin: str) -> str:
    return plugin.rsplit(".", 1)[-1] if plugin else ""


def _normalise_path(p: str) -> str:
    return p.replace("\\", "/").lower().strip()


def _basename(p: str) -> str:
    return _normalise_path(p).rsplit("/", 1)[-1]


def _effort_bucket(score: int) -> str:
    if score < 30:
        return "S"
    if score < 80:
        return "M"
    if score < 200:
        return "L"
    return "XL"


def _structure_hash(ir: dict) -> str:
    """Order-independent hash of the workflow's structural fingerprint."""
    plugins = sorted(_short(t["plugin"]) for t in ir.get("tools", []))
    edges = sorted(
        f"{c['from_anchor']}->{c['to_anchor']}" for c in ir.get("connections", [])
    )
    blob = "|".join(plugins) + "##" + "|".join(edges)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:16]


def analyze_one(path: Path) -> WorkflowReport:
    try:
        ir = parse_yxmd(path)
    except Exception as e:
        return WorkflowReport(
            name=path.name, path=str(path), size_bytes=path.stat().st_size,
            tool_count=0, connection_count=0, input_count=0, output_count=0,
            macro_count=0, formula_count=0, join_count=0, container_count=0,
            top_plugins="", inputs="", outputs="", complexity_score=0,
            effort="S", structure_hash="", error=str(e)[:200],
        )
    tools = ir.get("tools", [])
    conns = ir.get("connections", [])
    counter = Counter(_short(t["plugin"]) for t in tools)
    macro_count = sum(n for p, n in counter.items() if "macro" in p.lower())
    formula_count = sum(n for p, n in counter.items() if "formula" in p.lower())
    join_count = sum(n for p, n in counter.items() if "join" in p.lower())
    container_count = counter.get("ContainerTool", 0)
    top = ", ".join(f"{p}:{n}" for p, n in counter.most_common(5))

    score = (
        len(tools)
        + len(conns) // 2
        + formula_count * 2
        + join_count * 3
        + macro_count * 5
    )

    return WorkflowReport(
        name=path.name,
        path=str(path),
        size_bytes=path.stat().st_size,
        tool_count=len(tools),
        connection_count=len(conns),
        input_count=len(ir.get("inputs", [])),
        output_count=len(ir.get("outputs", [])),
        macro_count=macro_count,
        formula_count=formula_count,
        join_count=join_count,
        container_count=container_count,
        top_plugins=top,
        inputs=";".join(i["file"] for i in ir.get("inputs", [])),
        outputs=";".join(o["file"] for o in ir.get("outputs", [])),
        complexity_score=score,
        effort=_effort_bucket(score),
        structure_hash=_structure_hash(ir),
    )


# ----------------------------- batch / dependency / dup -----------------------------

@dataclass
class DependencyEdge:
    upstream: str    # workflow that writes the shared file
    downstream: str  # workflow that reads it
    shared_file: str


@dataclass
class DuplicateCluster:
    kind: str                  # "exact" or "near"
    similarity: float          # 1.0 for exact, otherwise Jaccard
    members: list[str] = field(default_factory=list)


def _collect_irs(workflow_dir: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for p in sorted(workflow_dir.rglob("*.yxmd")):
        try:
            out[str(p)] = parse_yxmd(p)
        except Exception:
            pass
    return out


def detect_dependencies(irs: dict[str, dict]) -> list[DependencyEdge]:
    """A.workflow.yxmd -> B.workflow.yxmd if any output basename of A matches
    any input basename of B."""
    outputs_by_wf: dict[str, set[str]] = {}
    inputs_by_wf: dict[str, set[str]] = {}
    for wf, ir in irs.items():
        outputs_by_wf[wf] = {_basename(o["file"]) for o in ir.get("outputs", []) if o.get("file")}
        inputs_by_wf[wf] = {_basename(i["file"]) for i in ir.get("inputs", []) if i.get("file")}

    edges: list[DependencyEdge] = []
    for up, out_set in outputs_by_wf.items():
        if not out_set:
            continue
        for down, in_set in inputs_by_wf.items():
            if down == up:
                continue
            shared = out_set & in_set
            for f in sorted(shared):
                edges.append(DependencyEdge(upstream=up, downstream=down, shared_file=f))
    return edges


def _plugin_multiset(ir: dict) -> Counter:
    return Counter(_short(t["plugin"]) for t in ir.get("tools", []))


def _jaccard(a: Counter, b: Counter) -> float:
    if not a and not b:
        return 1.0
    inter = sum((a & b).values())
    union = sum((a | b).values())
    return inter / union if union else 0.0


def detect_duplicates(
    irs: dict[str, dict],
    *,
    near_threshold: float = 0.9,
) -> list[DuplicateCluster]:
    """Exact clusters by structure_hash; near clusters by Jaccard on plugin
    multisets above `near_threshold` (single-link)."""
    # exact
    hash_to_members: dict[str, list[str]] = defaultdict(list)
    for wf, ir in irs.items():
        hash_to_members[_structure_hash(ir)].append(wf)
    clusters: list[DuplicateCluster] = []
    exact_members_flat: set[str] = set()
    for h, members in hash_to_members.items():
        if len(members) > 1:
            clusters.append(DuplicateCluster(kind="exact", similarity=1.0, members=sorted(members)))
            exact_members_flat.update(members)

    # near (skip workflows already in an exact cluster)
    candidates = [(wf, _plugin_multiset(ir)) for wf, ir in irs.items() if wf not in exact_members_flat]
    # single-link clustering
    parent: dict[str, str] = {wf: wf for wf, _ in candidates}
    sim_for_pair: dict[tuple[str, str], float] = {}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i in range(len(candidates)):
        wf_a, ms_a = candidates[i]
        for j in range(i + 1, len(candidates)):
            wf_b, ms_b = candidates[j]
            s = _jaccard(ms_a, ms_b)
            if s >= near_threshold:
                ra, rb = find(wf_a), find(wf_b)
                if ra != rb:
                    parent[ra] = rb
                sim_for_pair[(wf_a, wf_b)] = s

    groups: dict[str, list[str]] = defaultdict(list)
    for wf, _ in candidates:
        groups[find(wf)].append(wf)
    for members in groups.values():
        if len(members) > 1:
            # average pairwise similarity within group
            pairs = []
            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    a, b = members[i], members[j]
                    key = (a, b) if (a, b) in sim_for_pair else (b, a)
                    pairs.append(sim_for_pair.get(key, 0.0))
            avg = sum(pairs) / len(pairs) if pairs else 0.0
            clusters.append(DuplicateCluster(kind="near", similarity=round(avg, 3), members=sorted(members)))
    return clusters


# ----------------------------- writers -----------------------------

def _write_csv(rows: list[dict], path: Path) -> None:
    import csv
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def write_reports(
    out_dir: Path,
    reports: list[WorkflowReport],
    edges: list[DependencyEdge],
    clusters: list[DuplicateCluster],
    *,
    write_xlsx: bool = True,
) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}

    report_rows = [asdict(r) for r in reports]
    edge_rows = [asdict(e) for e in edges]
    cluster_rows = [
        {"kind": c.kind, "similarity": c.similarity, "size": len(c.members),
         "members": ";".join(c.members)}
        for c in clusters
    ]

    p1 = out_dir / "workflow_report.csv"; _write_csv(report_rows, p1); written["report_csv"] = p1
    p2 = out_dir / "workflow_dependencies.csv"; _write_csv(edge_rows, p2); written["dependencies_csv"] = p2
    p3 = out_dir / "workflow_duplicates.csv"; _write_csv(cluster_rows, p3); written["duplicates_csv"] = p3

    if write_xlsx:
        try:
            import pandas as pd
            xlsx_path = out_dir / "workflow_analysis.xlsx"
            with pd.ExcelWriter(xlsx_path, engine="openpyxl") as xw:
                pd.DataFrame(report_rows).to_excel(xw, sheet_name="Report", index=False)
                pd.DataFrame(edge_rows).to_excel(xw, sheet_name="Dependencies", index=False)
                pd.DataFrame(cluster_rows).to_excel(xw, sheet_name="Duplicates", index=False)
            written["xlsx"] = xlsx_path
        except Exception:
            pass

    # Mermaid graph for dependencies
    if edges:
        mermaid = ["graph LR"]
        seen = set()
        def nid(p): return "wf_" + hashlib.md5(p.encode()).hexdigest()[:8]
        for e in edges:
            for w in (e.upstream, e.downstream):
                if w not in seen:
                    mermaid.append(f'  {nid(w)}["{Path(w).name}"]')
                    seen.add(w)
            mermaid.append(f"  {nid(e.upstream)} -- {e.shared_file} --> {nid(e.downstream)}")
        p4 = out_dir / "workflow_dependencies.mmd"
        p4.write_text("\n".join(mermaid), encoding="utf-8")
        written["dependencies_mermaid"] = p4

    return written


def analyze_dir(workflow_dir: Path, out_dir: Path, *, near_threshold: float = 0.9) -> dict:
    files = sorted(workflow_dir.rglob("*.yxmd"))
    reports = [analyze_one(p) for p in files]
    irs = _collect_irs(workflow_dir)
    edges = detect_dependencies(irs)
    clusters = detect_duplicates(irs, near_threshold=near_threshold)
    written = write_reports(out_dir, reports, edges, clusters)
    return {
        "file_count": len(files),
        "report_count": len(reports),
        "dependency_edges": len(edges),
        "duplicate_clusters": len(clusters),
        "written": {k: str(v) for k, v in written.items()},
    }
