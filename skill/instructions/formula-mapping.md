# Alteryx expression language → Python cheatsheet

This is the formula language used by the Formula, Multi-Row Formula, Multi-Field
Formula, and Filter tools.

## Strings

| Alteryx                           | Python (pandas Series `s`) |
|---|---|
| `Trim([col])`                     | `s.str.strip()` |
| `Trim([col], " ")`                | `s.str.strip(" ")` |
| `Length([col])`                   | `s.str.len()` |
| `Uppercase([col])` / `Lowercase`  | `s.str.upper()` / `s.str.lower()` |
| `Substring([col], n)`             | `s.str[n:]` |
| `Substring([col], n, k)`          | `s.str[n:n+k]` |
| `Left([col], k)` / `Right`        | `s.str[:k]` / `s.str[-k:]` |
| `Contains([col], "x")`            | `s.str.contains("x", na=False)` |
| `StartsWith([col], "x")`          | `s.str.startswith("x")` |
| `FindString([col], "x")`          | `s.str.find("x")` (returns -1 if not found, same as Alteryx) |
| `Replace([col], "a", "b")`        | `s.str.replace("a", "b", regex=False)` |
| `RegEx_Match([col], pat)`         | `s.str.match(pat)` |
| `RegEx_Replace([col], pat, rep)`  | `s.str.replace(pat, rep, regex=True)` |
| `PadLeft([col], n, "0")`          | `s.str.rjust(n, "0")` |
| `[a] + [b]`                       | `a.fillna("") + b.fillna("")` (Alteryx treats NULL strings as empty in concat) |

## Numerics

| Alteryx                           | Python |
|---|---|
| `IsNull([x])` / `!IsNull([x])`    | `x.isna()` / `x.notna()` |
| `Null()`                          | `np.nan` (or `None` for object dtype) |
| `IIF(cond, a, b)`                 | `np.where(cond, a, b)` |
| `IF a THEN b ELSEIF c THEN d ELSE e ENDIF` | `np.select([a, c], [b, d], default=e)` |
| `MOD([x], 10)`                    | `x % 10` |
| `Floor([x])` / `Ceil`             | `np.floor(x)` / `np.ceil(x)` |
| `Round([x], 2)`                   | `x.round(2)` |
| `Abs([x])`                        | `x.abs()` |
| `ToNumber([col])`                 | `pd.to_numeric(col, errors="coerce")` |
| `ToString([col])`                 | `col.astype("string")` |

## Dates

| Alteryx                                 | Python |
|---|---|
| `DateTimeNow()`                         | `pd.Timestamp.now()` |
| `DateTimeToday()`                       | `pd.Timestamp.today().normalize()` |
| `DateTimeParse([col], "%d-%b-%Y")`      | `pd.to_datetime(col, format="%d-%b-%Y", errors="coerce")` |
| `DateTimeFormat([col], "%Y-%m-%d")`     | `col.dt.strftime("%Y-%m-%d")` |
| `DateTimeAdd([col], 1, "days")`         | `col + pd.Timedelta(days=1)` |
| `DateTimeDiff([a], [b], "days")`        | `(a - b).dt.days` |
| `DateTimeYear/Month/Day([col])`         | `col.dt.year / .month / .day` |

**Warning**: Alteryx supports year 9999 sentinels (e.g. `31-Dec-9999`). pandas
`datetime64[ns]` overflows at year 2262. Use Python `datetime` (object dtype)
or `datetime64[us]`. See `known-gotchas.md`.

## NULL semantics

Alteryx propagates NULL through arithmetic — `5 + NULL == NULL`. pandas does
this for `+`/`-`/`*` automatically; but **`Series.sum()` defaults to
`skipna=True`**. When emulating Alteryx aggregation, write `s.sum(skipna=False)`
explicitly.

In string concatenation, however, Alteryx treats NULL as empty string. So
`Trim([a] + [b])` becomes `(a.fillna("") + b.fillna("")).str.strip()`.

## Common compound formulas

### `IF FindString([s], "1") > -1 THEN FindString([s], "1") ELSEIF FindString([s], "2") > -1 THEN ... ENDIF`

Find the first occurrence of any digit:

```python
def first_digit_pos(s: str) -> int:
    if not isinstance(s, str): return -1
    for d in "123456789":
        i = s.find(d)
        if i > -1: return i
    return -1
```

### Chained `IIF` ladder

Translate every condition to a boolean array, then `np.select`:

```python
out = np.select(
    [cond1, cond2, cond3],
    [val1,  val2,  val3],
    default=val_else,
)
```

### Multi-Row Formula referencing `[Row-1:col]`

Use `groupby().shift()` to access prior rows safely:

```python
df = df.sort_values(["GroupKey", "OrderKey"])
df["prev"] = df.groupby("GroupKey")["col"].shift(1)
df["delta"] = df["col"] - df["prev"]
```

If you need a running maximum (a common pattern):

```python
df["latest"] = df.groupby("GroupKey")["col"].cummax()
```
