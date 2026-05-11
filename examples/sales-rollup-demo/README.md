# sales-rollup-demo

A small **synthetic** example for the `alteryx2fabric` toolkit. There is no
real `.yxmd` here — the example exists to demonstrate the toolkit's CLI
workflow and validation loop on data you can re-run locally.

## Scenario

A fictional retailer wants a quarterly rollup of sales by region.

**Inputs** (`inputs/`)
- `sales.csv` — order-level records: `OrderID, RegionCode, Product, Quantity, UnitPrice, OrderDate`
- `regions.csv` — region dimension: `RegionCode, RegionName, Country`

**Expected outputs** (`reference_outputs/`)
- `quarterly_rollup.csv` — `Country, RegionName, Quarter, TotalRevenue, OrderCount`

## Logic

```
revenue = Quantity * UnitPrice
quarter = "Q" + month_to_quarter(OrderDate) + "-" + year(OrderDate)
join sales × regions on RegionCode
group by Country, RegionName, Quarter
  sum(revenue)  → TotalRevenue
  count(OrderID) → OrderCount
sort by Country, RegionName, Quarter
```

## Run

```powershell
cd D:\sales-rollup
a2f init sales-rollup --workspace-id <YOUR_WS_GUID>
copy ..\alteryx2fabric\examples\sales-rollup-demo\inputs\*  .\inputs\
copy ..\alteryx2fabric\examples\sales-rollup-demo\reference_outputs\*  .\reference_outputs\
a2f provision --lakehouse sales_rollup_lh
a2f upload inputs --to Input
# ... write notebooks/nb_silver.py implementing the logic above ...
a2f deploy
a2f run
a2f download Files/Output --out fabric_outputs
a2f validate --ref reference_outputs --gen fabric_outputs
```

## Regenerating the example data

```
python examples/sales-rollup-demo/generate.py
```

Produces `inputs/*.csv` and `reference_outputs/quarterly_rollup.csv`
deterministically from a fixed RNG seed.
