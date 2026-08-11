"""Generic diff harness — compare two folders of tabular files (Excel / CSV / Parquet).

Used to validate Fabric outputs against the original Alteryx reference outputs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass
class FileDiff:
    name: str
    ref_shape: tuple[int, int] | None = None
    gen_shape: tuple[int, int] | None = None
    missing_in_gen: list[str] = field(default_factory=list)
    extra_in_gen: list[str] = field(default_factory=list)
    diff_columns: list[tuple[str, int]] = field(default_factory=list)
    note: str = ""

    @property
    def passed(self) -> bool:
        if self.note.startswith("missing"):
            return False
        return (
            not self.missing_in_gen
            and not self.diff_columns
            and self.ref_shape == self.gen_shape
        )


def _read(p: Path) -> pd.DataFrame:
    suf = p.suffix.lower()
    if suf in (".xlsx", ".xls"):
        return pd.read_excel(p)
    if suf == ".csv":
        return pd.read_csv(p)
    if suf == ".parquet":
        return pd.read_parquet(p)
    raise ValueError(f"unsupported file type: {p}")


def diff_dataframes(ref: pd.DataFrame, gen: pd.DataFrame, *, atol: float = 1e-3) -> dict:
    """Column-wise diff. Returns {column: n_diff_rows}. Both frames must have
    the same row count and column order is matched by name."""
    common = [c for c in ref.columns if c in gen.columns]
    diffs: dict[str, int] = {}
    n = min(len(ref), len(gen))
    if len(ref) != len(gen):
        return {"__shape__": abs(len(ref) - len(gen))}
    for c in common:
        a = ref[c].iloc[:n]
        b = gen[c].iloc[:n]
        if a.dtype.kind in "fc" or b.dtype.kind in "fc":
            same = np.isclose(
                pd.to_numeric(a, errors="coerce"),
                pd.to_numeric(b, errors="coerce"),
                equal_nan=True,
                atol=atol,
            )
        else:
            same = (a.astype(str) == b.astype(str)) | (a.isna() & b.isna())
        n_diff = int((~same).sum())
        if n_diff:
            diffs[c] = n_diff
    return diffs


def _sort_keys(common: list[str]) -> list[str]:
    """Heuristic — sort by the first non-numeric column for stable comparisons."""
    return common[:1] if common else []


def diff_folders(ref_dir: str | Path, gen_dir: str | Path, *, atol: float = 1e-3) -> list[FileDiff]:
    ref_dir, gen_dir = Path(ref_dir), Path(gen_dir)
    results: list[FileDiff] = []
    for ref_path in sorted(ref_dir.iterdir()):
        if ref_path.is_dir() or ref_path.suffix.lower() not in (".xlsx", ".csv", ".parquet"):
            continue
        gen_path = gen_dir / ref_path.name
        fd = FileDiff(name=ref_path.name)
        if not gen_path.exists():
            fd.note = "missing in generated folder"
            results.append(fd)
            continue
        try:
            ref_df = _read(ref_path)
            gen_df = _read(gen_path)
        except Exception as e:  # noqa: BLE001 - report per-file reader failures without aborting the batch
            fd.note = f"read error: {e}"
            results.append(fd)
            continue
        fd.ref_shape = ref_df.shape
        fd.gen_shape = gen_df.shape
        ref_cols = set(ref_df.columns)
        gen_cols = set(gen_df.columns)
        fd.missing_in_gen = sorted(ref_cols - gen_cols)
        fd.extra_in_gen = sorted(gen_cols - ref_cols)

        common = [c for c in ref_df.columns if c in gen_df.columns]
        if ref_df.empty and gen_df.empty:
            fd.note = "both empty (match)"
            results.append(fd)
            continue
        keys = _sort_keys(common)
        if keys:
            ref_df = ref_df[common].sort_values(keys).reset_index(drop=True)
            gen_df = gen_df[common].sort_values(keys).reset_index(drop=True)
        else:
            ref_df = ref_df[common].reset_index(drop=True)
            gen_df = gen_df[common].reset_index(drop=True)
        diffs = diff_dataframes(ref_df, gen_df, atol=atol)
        fd.diff_columns = sorted(diffs.items(), key=lambda kv: -kv[1])
        results.append(fd)
    return results


def format_report(results: list[FileDiff]) -> str:
    lines = ["=== alteryx2fabric validation report ==="]
    n_pass = sum(1 for r in results if r.passed)
    lines.append(f"{n_pass}/{len(results)} files match\n")
    for r in results:
        status = "OK " if r.passed else "FAIL"
        lines.append(f"[{status}] {r.name}  ref={r.ref_shape}  gen={r.gen_shape}")
        if r.note:
            lines.append(f"        note: {r.note}")
        if r.missing_in_gen:
            lines.append(f"        missing cols: {r.missing_in_gen}")
        if r.extra_in_gen:
            lines.append(f"        extra   cols: {r.extra_in_gen}")
        if r.diff_columns:
            lines.append(f"        diff cols:    {r.diff_columns[:10]}")
    return "\n".join(lines)
