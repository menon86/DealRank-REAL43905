# DealRank Excel Underwriting & Financing Ingestion Specification

This specification defines the standardized format for importing property underwriting assumptions, granular unit mixes, asset-class custom drivers, and financing structures into DealRank via `.xlsx`, `.xls`, or `.csv` workbooks.

---

## 1. Workbook Structure Overview

A standard DealRank Underwriting Workbook contains four structured worksheets (or four identifiable tables in a single worksheet):

1. **`Property_Details`**: Core asset identification, valuation, acquisition costs, hold horizon, and macroeconomic growth rates.
2. **`Unit_Mix`**: Granular breakdown of units across Studio, 1-Bed, 2-Bed, 3-Bed, and 4+ Bed configurations.
3. **`Custom_Inputs`**: Housing-type specific operational drivers (parking spaces/fees, storage, pet rent, tech packages, retail).
4. **`Financing`**: Debt capital stack, loan types (amortizing, interest-only, floating rate), amortization schedules, and loan terms.

---

## 2. Worksheet Schemas & Data Dictionaries

### Sheet 1: `Property_Details`

| Column Header | Data Type | Required | Default | Description / Validation | Example |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `deal_name` | String(255) | Yes | — | Human-readable property name | *Northside Garden Apartments* |
| `sub_asset_class` | String(50) | Yes | — | Must be: `student_housing`, `suburban_garden`, or `urban_midrise` | `suburban_garden` |
| `leasing_mode` | String(20) | Yes | `per_unit` | Must be: `per_unit` or `per_bed` | `per_unit` |
| `purchase_price` | Decimal | Yes | — | Acquisition purchase price ($) | `28500000.00` |
| `closing_costs` | Decimal | Yes | 2% of price | Transaction & legal closing costs ($) | `570000.00` |
| `hold_period_years` | Integer | Yes | `10` | Planned investment holding period (1–30 years) | `7` |
| `exit_cap_rate` | Decimal / % | Yes | — | Underwritten forward-NOI exit cap rate (e.g. `0.055` or `5.5%`) | `0.055` |
| `selling_costs_rate` | Decimal / % | Yes | `0.02` | Broker commission and transfer taxes at sale (e.g. `2.0%`) | `0.02` |
| `vacancy_rate` | Decimal / % | Yes | `0.05` | General economic and credit vacancy rate (e.g. `5.0%`) | `0.05` |
| `rent_growth_rate` | Decimal / % | Yes | `0.03` | Compounding annual gross rent growth (e.g. `3.0%`) | `0.03` |
| `expense_growth_rate` | Decimal / % | Yes | `0.03` | Compounding annual OpEx inflation (e.g. `3.0%`) | `0.03` |
| `base_opex_annual` | Decimal | Yes | — | Base year operating expenses excluding turnover ($) | `950000.00` |
| `annual_turnover_rate` | Decimal / % | Yes | — | Percentage of units/beds that turn annually (e.g. `55%`) | `0.55` |
| `turnover_cost_per_turn` | Decimal | Yes | — | Make-ready and re-leasing cost per turn ($) | `900.00` |

---

### Sheet 2: `Unit_Mix`

Each row represents a distinct unit tier. The sum of `units` and `monthly_rent` establishes the baseline Gross Potential Rent (GPR).

| Column Header | Data Type | Required | Description / Validation | Example |
| :--- | :--- | :--- | :--- | :--- |
| `unit_type` | String | Yes | `studio`, `1bed`, `2bed`, `3bed`, or `4bed_plus` | `2bed` |
| `unit_count` | Integer | Yes | Number of units in this tier ($> 0$) | `80` |
| `beds_per_unit` | Integer | Yes | Number of beds per unit (default 1 for Studio/1Bed, 2 for 2Bed, etc.) | `2` |
| `avg_sqft` | Integer | Optional | Average unit square footage | `950` |
| `monthly_rent` | Decimal | Yes | Monthly rent per unit (or per bed in per-bed leasing mode) | `1650.00` |

#### Sample Unit Mix Matrix:
```csv
unit_type,unit_count,beds_per_unit,avg_sqft,monthly_rent
studio,20,1,550,1150.00
1bed,60,1,720,1350.00
2bed,80,2,980,1650.00
3bed,20,3,1250,2050.00
```
*Derived Totals:* 180 Units | 280 Beds | $277,000 Monthly GPR | $3,324,000 Annual GPR.

---

### Sheet 3: `Custom_Inputs`

Specific operational drivers tailored to housing types. Fields not applicable to a selected housing type may be left blank or omitted.

| Field Name | Target Sub-Asset Class | Data Type | Description |
| :--- | :--- | :--- | :--- |
| `surface_parking_stalls` | `suburban_garden` | Integer | Total rentable surface parking spaces |
| `covered_parking_stalls` | `suburban_garden` | Integer | Total covered carports / detached garages |
| `parking_monthly_rate` | `suburban_garden`, `urban_midrise` | Decimal | Monthly fee per parking space ($) |
| `parking_occupancy_rate` | All | Decimal / % | Underwritten parking utilization (e.g. `90%`) |
| `garage_parking_stalls` | `urban_midrise` | Integer | Total structured/subterranean parking stalls |
| `storage_units` | `suburban_garden`, `urban_midrise` | Integer | Number of rentable tenant storage units |
| `storage_monthly_fee` | `suburban_garden`, `urban_midrise` | Decimal | Monthly fee per storage unit ($) |
| `pet_fee_monthly` | `suburban_garden` | Decimal | Average monthly pet rent per participating unit ($) |
| `pet_penetration_rate` | `suburban_garden` | Decimal / % | Percentage of units paying pet rent (e.g. `35%`) |
| `rubs_recovery_pct` | `suburban_garden` | Decimal / % | Ratio Utility Billing System recovery rate on utilities |
| `tech_package_monthly_fee` | `student_housing` | Decimal | High-speed Wi-Fi / smart tech fee per bed ($) |
| `furniture_package_monthly_fee`| `student_housing` | Decimal | Furnished unit package fee per bed ($) |
| `commercial_retail_sqft` | `urban_midrise` | Integer | Ground-floor retail rentable square feet |
| `commercial_rent_sqft_annual` | `urban_midrise` | Decimal | Annual triple-net (NNN) rent per square foot ($) |

---

### Sheet 4: `Financing`

Builds the deal's capital stack (see `docs/methodology.md` section 3): one senior loan, plus a
mezzanine and a preferred equity layer when their amounts are above zero. Equity layers already
on the form are kept. This is what the deal form's **Template (Financing)** download contains
and what **Import Financing** reads.

| Column Header | Data Type | Required | Default | Description / Validation | Example |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `senior_loan_type` | String | No | `other_senior` | A senior layer type: `agency_fannie_mae`, `agency_freddie_mac`, `hud_223f`, `hud_221d4`, `bank_credit_union`, `life_company`, `cmbs`, `bridge_debt_fund`, `construction`, `loan_assumption`, `seller_financing` | `agency_fannie_mae` |
| `loan_amount` | Decimal | Yes | — | Senior loan principal ($) | `18500000.00` |
| `rate_type` | String | No | `fixed` | `fixed` or `floating` | `fixed` |
| `interest_rate_pct` | Decimal | Fixed only | — | Annual rate in percent | `6.25` |
| `index_name` | String | No | `SOFR` | Floating-rate index name | `SOFR` |
| `index_rate_pct` | Decimal | Floating only | — | Index rate in percent | `4.30` |
| `spread_bps` | Decimal | Floating only | — | Lender spread in basis points | `275` |
| `io_months` | Integer | No | `0` | Interest-only months; can't exceed the term | `24` |
| `amortization_years` | Integer | No | `30` | Amortization after I/O runs over the remaining months | `30` |
| `term_years` | Integer | No | blank | Maturity; a term inside the hold is repaid as a balloon | `10` |
| `recourse` | String | No | blank | `recourse` or `non_recourse` | `non_recourse` |
| `origination_fee_pct` | Decimal | No | `0` | Paid at closing out of equity | `1.0` |
| `rate_cap_cost` | Decimal | No | `0` | Floating only; paid at closing ($) | `0` |
| `mezzanine_loan_amount` | Decimal | No | `0` | Adds an interest-only mezzanine layer when > 0 | `0.00` |
| `mezzanine_interest_rate_pct` | Decimal | No | `0` | Mezzanine rate in percent | `11.0` |
| `preferred_equity_amount` | Decimal | No | `0` | Adds a preferred equity layer when > 0 | `0.00` |
| `preferred_return_pct` | Decimal | No | `0` | Annual preferred return in percent | `9.0` |

The earlier template's `loan_structure`, `io_period_years`, `sofr_base_rate_pct` and
`loan_term_years` columns are still read for backward compatibility.

---

## 3. Ingestion & Validation Pipeline

When an Excel workbook is uploaded via `POST /deals/import/excel`:

1. **Header Normalization**: Headers are trimmed, lowercased, and mapped to internal Pydantic models.
2. **Type Coercion & Discipline**:
   - Percentages entered as whole numbers (e.g. `5.5%` or `5.5`) are automatically converted to decimal fractions (`0.055`).
   - Currency strings (e.g. `$28,500,000`) are stripped and parsed directly into `Decimal`.
3. **Cross-Field Integrity**:
   - Verifies that `unit_count` in `Property_Details` matches the sum of units in `Unit_Mix`.
   - Rejects files with negative rents, negative unit counts, or interest rates $> 25\%$.
   - Validates that `io_months` does not exceed the term, and the capital stack rules in `docs/methodology.md` section 3.
4. **Error Reporting**:
   - If validation fails, returns HTTP 422 with a structured error payload detailing:
     `{"sheet": "Unit_Mix", "row": 3, "column": "monthly_rent", "error": "Rent must be greater than zero"}`.
