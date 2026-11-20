from collections import Counter
from pathlib import Path
import math

import pandas as pd
from pandas.api.types import is_bool_dtype, is_numeric_dtype


def finite(value):
    value = float(value)
    return value if math.isfinite(value) else None


def profile_csv(path, *, delimiter=",", encoding="utf-8-sig", na_values=(), max_rows=None):
    """Read a local CSV and compute exact statistics for the loaded rows."""
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"File does not exist: {path}")
    if max_rows is not None and max_rows < 1:
        raise ValueError("max_rows must be positive.")
    if len(delimiter) != 1:
        raise ValueError("The delimiter must be one character.")
    # Read one extra row so the report can distinguish a full scan from a prefix.
    frame = pd.read_csv(
        path, sep=delimiter, encoding=encoding, keep_default_na=True,
        na_values=list(na_values), skip_blank_lines=False, low_memory=False,
        nrows=max_rows + 1 if max_rows else None,
    )
    truncated = max_rows is not None and len(frame) > max_rows
    if truncated:
        frame = frame.iloc[:max_rows].copy()
    # Whitespace-only fields count as missing; do not strip meaningful strings.
    frame = frame.replace(r"^\s*$", pd.NA, regex=True)
    rows, cols = frame.shape
    missing = frame.isna()
    columns, findings = [], []
    for name in frame.columns:
        series = frame[name]
        present = series.dropna()
        unique = int(present.nunique())
        count = int(missing[name].sum())
        kind = "boolean" if is_bool_dtype(series) else (
            "numeric" if is_numeric_dtype(series) else "text"
        )
        item = {
            "name": str(name), "dtype": str(series.dtype), "kind": kind,
            "missing": count, "missing_pct": round(100 * count / rows, 2) if rows else 0,
            "unique": unique, "non_missing": len(present),
        }
        if kind == "numeric":
            numeric = pd.to_numeric(present).astype(float)
            good = numeric[numeric.map(math.isfinite)]
            item["infinite"] = len(numeric) - len(good)
            item["stats"] = {
                "min": finite(good.min()), "median": finite(good.median()),
                "max": finite(good.max()), "mean": finite(good.mean()),
            }
            if len(good):
                q1, q3 = good.quantile([.25, .75])
                iqr = q3 - q1
                item["iqr_outliers"] = int(((good < q1 - 1.5 * iqr) |
                                            (good > q3 + 1.5 * iqr)).sum()) if iqr else 0
            if item["infinite"]:
                findings.append(f"{name}: {item['infinite']} infinite numeric values.")
        if rows and count == rows:
            findings.append(f"{name}: entirely missing.")
        elif count:
            findings.append(f"{name}: {item['missing_pct']}% missing ({count} rows).")
        if unique == 1:
            findings.append(f"{name}: constant among non-missing values.")
        if len(present) >= 2 and unique == len(present):
            item["possible_identifier"] = True
        columns.append(item)
    duplicate_rows = int(frame.duplicated().sum())
    if duplicate_rows:
        findings.append(f"{duplicate_rows} duplicate rows beyond the first occurrence.")
    incomplete = int(missing.any(axis=1).sum())
    patterns = Counter(
        tuple(str(frame.columns[i]) for i, absent in enumerate(row) if absent)
        for row in missing.itertuples(index=False, name=None)
    )
    patterns.pop((), None)
    return {
        "schema_version": 1, "dataset": path.name,
        "rows": rows, "columns_count": cols, "prefix_scan": truncated,
        "scan_note": f"First {rows:,} rows only." if truncated else "All rows scanned.",
        "missing_cells": int(missing.sum().sum()),
        "missing_pct": round(100 * missing.sum().sum() / (rows * cols), 2) if rows * cols else 0,
        "incomplete_rows": incomplete, "duplicate_rows": duplicate_rows,
        "columns": columns, "findings": findings,
        "missing_patterns": [
            {"columns": list(pattern), "rows": count}
            for pattern, count in patterns.most_common(10)
        ],
        "missing_policy": "Pandas default NA tokens, whitespace-only fields, and supplied --na tokens.",
        "ai": {"status": "disabled"},
    }
