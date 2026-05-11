# Contributing

Thanks for your interest in improving **alteryx2fabric**!

This project is an early-stage toolkit. Issues, ideas, and PRs are all welcome.

## Ground rules

- **No customer data, ever.** Do not commit `.yxmd` files, input files, or
  output files derived from a real customer engagement. The `examples/`
  folder is synthetic by design — keep it that way.
- **One change per PR.** Prefer small, focused PRs over large omnibus ones.
- **Tests for new logic.** Anything in `parse.py`, `validate.py`, or the
  notebook builders should have a pytest covering the happy path.
- **No breaking CLI changes without a deprecation cycle.** Once a flag is
  documented, keep it working for at least one minor version.

## Dev setup

```powershell
git clone <your-fork>
cd alteryx2fabric
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
pip install pytest
pytest -q
```

## Code style

- Python 3.10+ syntax (`X | Y` unions, `list[...]` generics).
- Type hints on public functions.
- Click for CLI surfaces; do not hand-roll argparse.
- Keep modules small and single-purpose — one file per concern.
- Standard library + the deps already in `pyproject.toml`. Open an issue
  before adding a new dependency.

## What to work on

Good starter issues:

- Dataflow Gen2 emission for Bronze (alternative to Notebook-based Bronze).
- Spark Job Definition (SJD) output mode for environments where notebooks
  are disallowed.
- Better Alteryx Macro (`.yxmc`) inlining in `parse.py`.
- Additional formula mappings in
  [`skill/instructions/formula-mapping.md`](skill/instructions/formula-mapping.md).
- More gotchas you've hit — PRs to
  [`skill/instructions/known-gotchas.md`](skill/instructions/known-gotchas.md)
  with a short repro are extremely welcome.

## Reporting issues

When filing a bug, include:

- The command you ran.
- The relevant section of the YXMD (if it can be sanitized) or a synthetic
  reproduction.
- Full traceback or CLI output.
- `a2f --version` and Python version.

## License

By contributing, you agree your contributions are licensed under the MIT
License — see [`LICENSE`](LICENSE).
