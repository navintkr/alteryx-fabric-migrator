# Known gotchas — read before writing any Spark/Delta code

Every item below has cost a real engagement at least one cycle of debugging.
The CLI ships with safe defaults for most; the skill notes them so an agent
generating bespoke code doesn't reintroduce them.

---

## 1. Delta column mapping is mandatory for Alteryx column names

Alteryx happily produces column names like `Plant Region`, `S4 PriceReasonCode`,
`PurchaseOrder #`. Delta rejects these by default with:

```
DELTA_INVALID_CHARACTERS_IN_COLUMN_NAMES
```

**Fix** — write tables with column mapping enabled:

```python
(sdf.write.mode("overwrite")
    .option("overwriteSchema", "true")
    .option("delta.columnMapping.mode", "name")
    .option("delta.minReaderVersion", "2")
    .option("delta.minWriterVersion", "5")
    .format("delta").saveAsTable(name))
```

And set defaults at session scope so any incidental writes don't regress:

```python
spark.conf.set("spark.databricks.delta.properties.defaults.columnMapping.mode", "name")
spark.conf.set("spark.databricks.delta.properties.defaults.minReaderVersion", "2")
spark.conf.set("spark.databricks.delta.properties.defaults.minWriterVersion", "5")
```

---

## 2. `timestampNtz` Delta feature requirement

Spark `TimestampNTZ` requires a manually-enabled Delta table feature:

```
DELTA_FEATURES_REQUIRE_MANUAL_ENABLEMENT: timestampNtz
```

This is triggered when you pass a pandas frame with a `datetime64[*]` column
to `spark.createDataFrame` and write it to Delta.

**Fix** — serialise datetimes to ISO strings before writing, then re-parse on
read if you need datetime semantics:

```python
for c in pdf.columns:
    if pd.api.types.is_datetime64_any_dtype(pdf[c]):
        pdf[c] = pdf[c].map(lambda v: v.strftime("%Y-%m-%d %H:%M:%S") if pd.notna(v) else None).astype("string")
```

---

## 3. Year-9999 sentinel dates overflow `datetime64[ns]`

Alteryx workflows often use `31-Dec-9999` as a "no end date" sentinel.
pandas `datetime64[ns]` cannot represent years > 2262.

```python
pd.to_datetime("31-Dec-9999", format="%d-%b-%Y")   # OverflowError or silent NaT
```

**Fix** — use Python `datetime` objects (object dtype) for date columns that
might carry sentinels:

```python
from datetime import datetime
def parse_alteryx_date(s):
    if s is None or pd.isna(s) or s == "": return None
    for fmt in ("%d-%b-%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try: return datetime.strptime(str(s).strip(), fmt)
        except Exception: pass
    return None
df["End Date"] = pd.Series([parse_alteryx_date(v) for v in df["End Date"]], dtype=object)
```

Or use `datetime64[us]` (microsecond precision) which extends the range to
year 9999.

---

## 4. NULL arithmetic — `skipna=True` is wrong for Alteryx parity

```python
s = pd.Series([1, 2, None, 4])
s.sum()                  # 7    (skipna=True default)
s.sum(skipna=False)      # NaN  (Alteryx behaviour)
```

When emulating an Alteryx Summarize that sums a column containing NULLs, the
Alteryx output for that group is NULL. Always pass `skipna=False`.

---

## 5. Join key NULL/whitespace equivalence

Alteryx Join treats `NULL`, `""`, and `"  "` as the **same** value when used
as a join key. pandas treats them as three distinct values.

**Fix** — normalise keys before merge:

```python
def normalize_join_key(s):
    return s.astype("string").fillna("").str.strip()

for k in join_keys:
    left[k] = normalize_join_key(left[k])
    right[k] = normalize_join_key(right[k])
merged = left.merge(right, on=join_keys, how="left", indicator=True)
```

The `indicator=True` flag recovers the "L only" / "R only" outputs of the
Alteryx Join tool.

---

## 6. Cleanse macro — does **not** uppercase by default

The shipped "Cleanse" macro can be misread as also normalising case. It does
not. Trim and collapse whitespace only, unless the workflow's Cleanse
configuration explicitly enables uppercase.

```python
def cleanse(df, cols):
    for c in cols:
        if c in df.columns:
            df[c] = df[c].astype("string").str.strip().str.replace(r"\s+", " ", regex=True)
    return df
```

---

## 7. Movement vs. change comparisons with NaN

When the Alteryx workflow checks `Movement != Change` and either value is
NULL, Alteryx returns FALSE (NULL ≠ anything is NULL, treated as no-match).
pandas `==` returns `False` for `NaN == NaN`, but `np.isclose` defaults to
`equal_nan=False` which is what you want for "real" mismatch detection.

```python
mismatch = ~np.isclose(df["Movement"], df["Change"], equal_nan=False, atol=1e-3)
```

---

## 8. Excel header offset

Alteryx Input tools can skip N header rows. Pandas equivalent:

```python
pd.read_excel(path, sheet_name="Sheet1", header=7)   # 8th row is the header
```

If you generate a Dataflow Gen2 instead, you have to emit a custom M step for
this — which is why the toolkit currently sticks with Notebook-based Bronze.

---

## 9. `drop_duplicates` order matters

```python
df.drop_duplicates(subset=["key"], keep="first")
```

Alteryx Unique keeps the *first* occurrence by row order. Sort before
deduplicating if your workflow depends on a specific ordering (e.g. the most
recent exchange rate row).

---

## 10. Crosstab column naming

Alteryx Crosstab replaces spaces in pivot column values with underscores
(`Commercial TVM` → `Commercial_TVM`). Mirror this when using `pd.crosstab`:

```python
ct = pd.crosstab(df["GroupKey"], df["Type"].str.replace(" ", "_"))
```
