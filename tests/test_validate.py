"""Smoke tests for alteryx2fabric.validate."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from alteryx2fabric.validate import diff_dataframes, diff_folders


def test_diff_dataframes_identical():
    df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
    assert diff_dataframes(df, df.copy()) == {}


def test_diff_dataframes_within_atol():
    a = pd.DataFrame({"v": [1.0, 2.0, 3.0]})
    b = pd.DataFrame({"v": [1.0005, 2.0, 3.0]})
    assert diff_dataframes(a, b, atol=1e-3) == {}


def test_diff_dataframes_outside_atol():
    a = pd.DataFrame({"v": [1.0, 2.0, 3.0]})
    b = pd.DataFrame({"v": [1.5, 2.0, 3.0]})
    assert diff_dataframes(a, b, atol=1e-3) == {"v": 1}


def test_diff_dataframes_strings():
    a = pd.DataFrame({"s": ["x", "y"]})
    b = pd.DataFrame({"s": ["x", "Y"]})
    assert diff_dataframes(a, b) == {"s": 1}


def test_diff_folders_match(tmp_path: Path):
    ref = tmp_path / "ref"
    gen = tmp_path / "gen"
    ref.mkdir(); gen.mkdir()
    df = pd.DataFrame({"id": [1, 2], "amount": [10.0, 20.0]})
    df.to_csv(ref / "out.csv", index=False)
    df.to_csv(gen / "out.csv", index=False)

    results = diff_folders(ref, gen)
    assert len(results) == 1
    assert results[0].passed


def test_diff_folders_missing(tmp_path: Path):
    ref = tmp_path / "ref"
    gen = tmp_path / "gen"
    ref.mkdir(); gen.mkdir()
    pd.DataFrame({"x": [1]}).to_csv(ref / "out.csv", index=False)

    results = diff_folders(ref, gen)
    assert len(results) == 1
    assert not results[0].passed
    assert "missing" in results[0].note
