# DealRank spreadsheet import

How deal inputs get from a spreadsheet into the New deal form: the downloadable template, and
importing a workbook in any layout. The field list below is generated from
`backend/app/spreadsheet/fields.py`, which drives both the template and the importer.

---

## 1. Template

`GET /deals/import/template` returns `dealrank_underwriting_template.xlsx`, one workbook with:

- **Instructions**: how to fill it in and import it.
- **Property**: deal, revenue, expense, exit and optional ancillary-income inputs, one per row
  (Field, Value, Unit, Notes).
- **Unit Mix**: one row per unit type, with a total row.
- **Financing**: the senior loan, plus optional mezzanine debt and preferred equity.
- **Lists** (hidden): the options behind the dropdowns.

Input cells are shaded; money, percent and count cells carry Excel number formats; property type,
leasing mode, loan type, rate type and recourse are dropdowns. Sample values describe a suburban
garden deal for the user to overwrite.

## 2. Import

`POST /deals/import` takes one file (multipart field `file`): `.xlsx`, `.xlsm`, `.csv` or `.tsv`,
up to 5 MB. Old `.xls` files are refused with a message to re-save as `.xlsx`. Formulas are read
from the values Excel last saved. Each sheet is scanned up to 400 rows by 40 columns, and sheets
named Instructions or Lists are skipped.

Import **never creates or changes a deal**. It returns a proposal; the frontend shows it on a
review screen, the user confirms or fixes each value, and only then is the form filled. The
normal `POST /deals` validation applies when the deal is saved.

### How values are found

1. **Unit mix table.** A header row naming at least two of units, beds, square feet and rent
   (for example `Floor Plan | # Units | Avg SF | Market Rent`) is read down to the first blank or
   total/average row. Beds per unit are guessed from the unit type name ("Studio", "2 Bed",
   "2x2", "2BR") when there's no beds column.
2. **Label/value pairs.** Every other text cell is compared with each field's labels below. The
   value is the first filled cell to the right (skipping unit cells like `%` or `years`), or the
   cell directly below. An exact label match is marked **Matched**; a label that only contains
   one (for example "Total Operating Expenses (Yr 1)") is marked **Check**. One-word labels only
   match exactly, and a label with "per unit" / "per sf" isn't taken as a total, so "Price per
   Unit" isn't read as the purchase price. Each field takes its best label and each cell is used
   once.
3. **Values.** `$`, thousands separators, `(1,200)` negatives and `k` / `M` suffixes are handled.
   Percent fields accept Excel percent cells, `5.5%` text, or a bare fraction (`0.055` is read as
   5.5% and flagged for checking). An interest-only period labelled in years is converted to
   months; a spread entered as a percent is converted to basis points.

### Response

- `fields`: every importable field, with `value` (in form units: percents as whole numbers),
  `source` (sheet, cell and the label it was found next to), `confidence` and an optional `note`.
- `candidates`: every label/value pair in the workbook, so the user can point a field at a
  different cell.
- `unit_mix`: the detected table (all columns, raw rows) and which column was matched to each
  unit mix attribute, so the user can remap columns.
- `warnings`: shown at the top of the review screen.

An unreadable file returns 422 with a message for the user.

## 3. Fields

### Property tab

| Template label | Key | Unit | Also recognized as |
| :--- | :--- | :--- | :--- |
| Deal name | `name` | — | deal_name, property name, property, project name, asset name, name |
| Property type | `sub_asset_class` | — | sub asset class, asset class, asset type, product type; options: Suburban garden (`suburban_garden`), Student housing (`student_housing`), Urban mid-rise (`urban_midrise`) |
| Leasing mode | `leasing_mode` | — | lease type, leased by; options: Per unit (`per_unit`), Per bed (`per_bed`) |
| Purchase price | `purchase_price` | $ | acquisition price, contract price, price, purchase |
| Closing costs | `closing_costs` | $ | closing cost, transaction costs, acquisition costs, acquisition fees |
| Hold period | `hold_period_years` | years | holding period, hold years, hold, investment horizon, hold period years |
| Number of units | `unit_count` | units | units, unit count, total units, no of units, number units |
| Average monthly rent per unit | `monthly_rent_per_unit` | $/month | average rent, avg rent, average monthly rent, avg monthly rent, rent per unit, monthly rent, in place rent, average rent per unit |
| Number of beds | `bed_count` | beds | beds, bed count, total beds |
| Average monthly rent per bed | `monthly_rent_per_bed` | $/month | rent per bed, monthly rent per bed, average rent per bed |
| Vacancy rate | `vacancy_rate_pct` | % | vacancy, economic vacancy, physical vacancy, vacancy loss, vacancy pct |
| Credit loss | `credit_loss_rate_pct` | % of rent | credit loss rate, bad debt, collection loss |
| Rent growth | `rent_growth_rate_pct` | % per year | rent growth rate, rental growth, annual rent growth, rent escalation |
| Other income | `other_income_annual` | $/year | ancillary income, misc income, miscellaneous income, other revenue |
| Other income growth | `other_income_growth_rate_pct` | % per year | other income growth rate |
| Operating expenses | `opex_annual` | $/year | opex, total operating expenses, annual operating expenses, total expenses, annual opex |
| Expense growth | `expense_growth_rate_pct` | % per year | expense growth rate, opex growth, expense inflation |
| Management fee | `management_fee_rate_pct` | % of income | management fee rate, mgmt fee, property management fee |
| Replacement reserves | `replacement_reserve_per_unit_or_bed` | $/unit/year | replacement reserve, reserves, capex reserve, reserves per unit |
| Turnover cost | `turnover_cost_per_unit_or_bed` | $ per turn | turnover_cost, make ready cost, make ready, turn cost |
| Turnover rate | `annual_turnover_rate_pct` | % per year | turnover_rate_pct, annual turnover, annual turnover rate |
| Lease expiration month | `lease_expiration_month` | 1-12 | lease expiry month, lease turn month |
| Exit cap rate | `exit_cap_rate_pct` | % | exit cap, terminal cap rate, reversion cap rate, residual cap rate |
| Selling costs | `selling_costs_rate_pct` | % of sale price | selling cost, cost of sale, costs of sale, disposition costs |

### Property tab: ancillary income (optional)

| Template label | Key | Unit | Also recognized as |
| :--- | :--- | :--- | :--- |
| Surface parking stalls | `surface_parking_stalls` | stalls | surface parking, surface stalls |
| Covered parking stalls | `covered_parking_stalls` | stalls | covered parking, carports |
| Parking rate | `parking_monthly_rate` | $/stall/month | parking monthly rate, parking fee |
| Parking occupancy | `parking_occupancy_pct` | % | parking occupancy rate |
| Storage units | `storage_units` | units | storage |
| Storage fee | `storage_monthly_fee` | $/month | storage monthly fee, storage rent |
| Pet rent | `pet_monthly_fee` | $/month | pet monthly fee, pet fee |
| Units with pets | `pet_penetration_pct` | % | pet penetration, pet penetration pct |
| Tech package fee | `tech_package_monthly_fee` | $/bed/month | tech package, technology fee |
| Furniture package fee | `furniture_package_monthly_fee` | $/bed/month | furniture package, furniture fee |
| Garage parking stalls | `garage_parking_stalls` | stalls | garage stalls, structured parking stalls |
| Garage parking rate | `garage_monthly_rate` | $/stall/month | garage monthly rate, garage rate |
| Retail square feet | `commercial_retail_sqft` | sq ft | commercial retail sqft, retail sf, commercial sf, retail area |
| Retail rent | `commercial_rent_sqft_annual` | $/sq ft/year | commercial rent sqft annual, retail rent psf, commercial rent |

### Financing tab

| Template label | Key | Unit | Also recognized as |
| :--- | :--- | :--- | :--- |
| Senior loan type | `senior_loan_type` | — | loan type, lender, lender type, debt type, loan program; options: Agency - Fannie Mae (`agency_fannie_mae`), Agency - Freddie Mac (`agency_freddie_mac`), HUD/FHA 223(f) (`hud_223f`), HUD/FHA 221(d)(4) (`hud_221d4`), Bank / credit union (`bank_credit_union`), Life insurance company (`life_company`), CMBS / conduit (`cmbs`), Bridge / debt fund (`bridge_debt_fund`), Construction loan (`construction`), Loan assumption (`loan_assumption`), Seller financing (`seller_financing`), Other (`other_senior`) |
| Loan amount | `loan_amount` | $ | senior loan amount, loan, senior loan, mortgage amount, debt amount, loan proceeds, first mortgage |
| Rate type | `rate_type` | — | interest rate type, loan structure, fixed or floating; options: Fixed (`fixed`), Floating (`floating`) |
| Interest rate | `interest_rate_pct` | % | rate, coupon, note rate, loan rate, senior interest rate |
| Index | `index_name` | — | index name, rate index |
| Index rate | `index_rate_pct` | % | sofr, sofr rate, sofr_base_rate_pct, base rate |
| Spread | `spread_bps` | bps | spread bps, margin, lender spread |
| Interest-only period | `io_months` | months | io months, io period, interest only months, interest only, io |
| Amortization | `amortization_years` | years | amortization period, amortization years, amort, amortization term |
| Loan term | `term_years` | years | term, maturity, term years, loan_term_years, loan maturity |
| Recourse | `recourse` | — | options: Non-recourse (`non_recourse`), Recourse (`recourse`) |
| Origination fee | `origination_fee_pct` | % of loan | loan fee, financing fee, origination, lender fee |
| Rate cap cost | `rate_cap_cost` | $ | interest rate cap, rate cap |
| Mezzanine loan amount | `mezzanine_loan_amount` | $ | mezzanine, mezz loan, mezz, mezzanine debt |
| Mezzanine interest rate | `mezzanine_interest_rate_pct` | % | mezz rate, mezzanine rate |
| Preferred equity amount | `preferred_equity_amount` | $ | preferred equity, pref equity |
| Preferred return | `preferred_return_pct` | % | pref return, preferred equity return |

### Unit Mix tab

| Column | Also recognized as |
| :--- | :--- |
| Unit type | unit_mix, type, floor plan, floorplan, plan, unit mix, description |
| Units | unit count, number of units, no of units, count, qty, total units |
| Beds per unit | beds, bedrooms, br, bd, beds per unit, bedrooms per unit |
| Avg sq ft | sq ft, sqft, sf, avg sf, average sf, square feet, size, unit sf, nrsf |
| Monthly rent | rent, avg rent, average rent, market rent, in place rent, asking rent, rent per unit |
