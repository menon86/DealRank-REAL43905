# TASK: Deliverable 3 — Customized Housing Inputs, Unit Mix, Financing Flexibility & Excel Ingestion

## Why
While Deliverable 2 provided a solid MVP waterfall calculation engine, institutional underwriting requires granular operational inputs and financing structures. Real estate analysts underwrite multifamily deals with granular unit mixes (studio through 4+ beds), asset-class-specific revenues (e.g. structured parking, pet rent, tech packages), flexible debt products (Interest-Only periods, floating rates, balloon maturities), and direct Excel workbook import/export rather than manual single-number entries.

---

## What to do

### 1. Housing-Type Specific Custom Input Fields
Enable tailored input fields dynamically keyed to the selected `sub_asset_class`:
- **Student Housing**:
  - Per-bed leasing primary mode (leased by bed rather than unit).
  - Academic year leasing schedules vs. 12-month annual contracts.
  - August turn concentration schedule (turnover rate default 80%–90%).
  - Mandatory tenant fee packages: Tech/Wi-Fi packages, furniture package rentals, utility caps.
- **Suburban Garden**:
  - Surface stalls vs. covered carports vs. detached garages.
  - Storage locker counts and monthly fee schedules.
  - Pet rent, pet deposit fees, and pet penetration rates.
  - Ratio Utility Billing System (RUBS) reimbursement rate (% of utility OpEx billed back to tenants).
  - Amenity packages (clubhouse, pool, dog park maintenance).
- **Urban Mid-Rise**:
  - Structured/subterranean parking stalls, parking ratios (stalls/unit), and monthly garage parking rents.
  - Ground-floor commercial / retail square footage and annual NNN lease rent.
  - High-density amenities (concierge desk, automated package locker systems, rooftop lounge fees).

### 2. Granular Unit Mix Modeling (Studio, 1, 2, 3, 4+ Beds)
Replace the single blended unit/bed input with a structured 5-tier unit mix matrix:
- **Studio**: Unit count, average square footage, monthly rent.
- **1 Bedroom / 1 Bath**: Unit count, average square footage, monthly rent.
- **2 Bedroom**: Unit count, beds per unit, average square footage, monthly rent (or rent/bed).
- **3 Bedroom**: Unit count, beds per unit, average square footage, monthly rent (or rent/bed).
- **4+ Bedroom**: Unit count, beds per unit, average square footage, monthly rent (or rent/bed).
- **Calculated Roll-Ups**:
  - Total Units $= \sum \text{units}_t$
  - Total Beds $= \sum (\text{units}_t \times \text{beds}_t)$
  - Aggregate Gross Potential Rent (GPR) $= 12 \times \sum (\text{units}_t \times \text{rent}_t)$
  - Weighted Average Rent per Unit and Rent per Square Foot.

### 3. Expanded Operational Inputs & Ancillary Revenue
Provide dedicated input fields for non-rental income:
- **Parking Revenue Engine**:
  - Number of rentable parking stalls (surface, covered, garage).
  - Monthly rent per stall.
  - Parking occupancy rate.
  - Total Annual Parking Revenue $= \text{stalls} \times \text{fee} \times \text{occupancy} \times 12$.
- **Storage Revenue**: Storage unit count $\times$ monthly storage rate $\times 12$.
- **Pet Revenue**: Active pet count $\times$ monthly pet rent $\times 12$.
- **Utility Reimbursement**: RUBS recovery rate applied to utility expenses.
- **Capital Expenditures (CapEx)**: Replacement reserve per unit/year deducted below NOI or factored into cash flow.

### 4. Financing Flexibility & Diverse Loan Types
Expand the debt engine beyond standard 30-year fixed amortization:
- **Interest-Only (I/O) Periods**:
  - Configurable I/O horizon (e.g. 1, 2, 3, or 5 years).
  - During I/O: Monthly debt service $= \text{loan\_amount} \times (\text{rate} / 12)$, principal payment $= 0$.
  - Post-I/O: Level amortization solved over remaining term ($\text{amortization\_years} - \text{io\_years}$).
- **Floating-Rate Debt**:
  - Reference Index (e.g. 30-day SOFR) + Spread (bps).
  - Optional Interest Rate Cap strike rate to model worst-case debt service.
- **Balloon Payment at Loan Maturity**:
  - Loan term (e.g. 5, 7, 10 years) independent of amortization duration (e.g. 30 years).
  - Unamortized balloon balance calculated at loan maturity or exit hold date.
- **Multi-Tranche Debt (Senior + Mezzanine)**:
  - Support for secondary debt tranches (mezzanine / second lien) with separate LTV, interest rate, and term.
  - Composite DSCR and blended debt yield reporting.

### 5. Excel Import for Property Details & Financing
Enable seamless ingestion of spreadsheets for instant deal creation:
- **Underwriting & Property Details Import**:
  - Supports `.xlsx` and `.csv` files matching the schema in `docs/templates/underwriting-and-financing-import-spec.md`.
  - Ingests Property Name, Sub-Asset Class, Acquisition Price, Closing Costs, 5-tier Unit Mix, Parking details, and OpEx lines.
- **Financing Details Import**:
  - Upload debt assumptions: Loan Amount, Loan Type (Fixed / Floating / I-O), Interest Rate, I/O Duration, Amortization Schedule, and Fees.
- **Template Generation & Download**:
  - Provide downloadable pre-formatted `.xlsx` underwriting templates directly from the UI.
  - Robust client-side and server-side cell validation with row/column error messaging.

---

## Acceptance Criteria
- [ ] Database schema and Pydantic models support granular unit mix entries (`studio`, `1bed`, `2bed`, `3bed`, `4bed_plus`).
- [ ] GPR calculation engine dynamically rolls up unit mix rows into annual GPR.
- [ ] Housing-type custom fields (parking stalls, storage, pet fees, RUBS, tech packages) integrated into revenue and EGI calculation.
- [ ] Debt calculation engine models Interest-Only periods, remaining-term amortization, and balloon balances at maturity.
- [ ] Excel import endpoint (`POST /deals/import/excel`) successfully parses `.xlsx` workbooks and populates all deal parameters.
- [ ] Frontend Deal Form provides dynamic sub-asset class field toggling, an interactive unit mix matrix, financing structure options, and an Excel dropzone.
- [ ] Full unit-test suite covers unit mix roll-ups, I/O debt schedules, and Excel parser error handling.

---

# PRIOR COMPLETED TASKS

## TASK: Render deployment & DB provisioning (Completed in PR #5)
- Automated database URL normalization (`postgresql+psycopg://`).
- Idempotent database migrations and seeding (`seed.py`, `seed_reference_data.py`) in `render.yaml`.
- Wildcard CORS support for Render subdomains.
- Live deployment configuration verified.

## TASK: UI/UX — Deal form & deal list (Completed in PR #7)
- Leasing-mode visual distinction and conditional field display.
- In-line field-level validation and clear error states.
- Helpful call-to-action prompts for empty states.
- Responsive form and table layouts.
