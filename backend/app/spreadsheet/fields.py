"""Every deal input a spreadsheet import can fill, and the labels it's known by.

One catalog drives both directions: the downloadable template is written
from it (label, unit, notes, sample value), and the importer matches the
labels it finds in an uploaded workbook against each field's synonyms. The
keys are the deal form's own field names (frontend/src/components/DealForm.tsx)
and, for financing, the keys the form's financing reader already takes, so an
import result maps straight onto the form.

Percent fields carry whole-number percents ("5.75" means 5.75%), the same
convention as the form's inputs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Kind = Literal["money", "percent", "integer", "number", "text", "choice"]
Section = Literal["property", "ancillary", "financing"]


@dataclass(frozen=True)
class Choice:
    value: str
    label: str
    synonyms: tuple[str, ...] = ()


@dataclass(frozen=True)
class FieldSpec:
    key: str
    label: str
    section: Section
    kind: Kind
    group: str
    unit: str = ""
    notes: str = ""
    sample: str = ""
    synonyms: tuple[str, ...] = ()
    choices: tuple[Choice, ...] = field(default_factory=tuple)

    @property
    def all_labels(self) -> tuple[str, ...]:
        # The key itself ("vacancy_rate_pct") is a label too, so the old CSV
        # templates keep importing.
        return (self.label, self.key, *self.synonyms)


SUB_ASSET_CLASSES = (
    Choice("suburban_garden", "Suburban garden", ("garden", "suburban", "garden style")),
    Choice("student_housing", "Student housing", ("student", "purpose built student housing")),
    Choice("urban_midrise", "Urban mid-rise", ("mid rise", "midrise", "urban", "high rise")),
)

LEASING_MODES = (
    Choice("per_unit", "Per unit", ("unit", "by unit", "conventional")),
    Choice("per_bed", "Per bed", ("bed", "by bed", "by the bed")),
)

# Mirrors the senior types in frontend/src/lib/capitalStack.ts LAYER_OPTIONS.
SENIOR_LOAN_TYPES = (
    Choice("agency_fannie_mae", "Agency - Fannie Mae", ("fannie mae", "fannie", "fnma")),
    Choice("agency_freddie_mac", "Agency - Freddie Mac", ("freddie mac", "freddie", "fhlmc")),
    Choice("hud_223f", "HUD/FHA 223(f)", ("hud 223f", "223f", "223 f")),
    Choice("hud_221d4", "HUD/FHA 221(d)(4)", ("hud 221d4", "221d4", "221 d 4")),
    Choice("bank_credit_union", "Bank / credit union", ("bank", "credit union")),
    Choice("life_company", "Life insurance company", ("life company", "life co", "lifeco")),
    Choice("cmbs", "CMBS / conduit", ("cmbs", "conduit")),
    Choice("bridge_debt_fund", "Bridge / debt fund", ("bridge", "debt fund", "bridge loan")),
    Choice("construction", "Construction loan", ("construction",)),
    Choice("loan_assumption", "Loan assumption", ("assumption", "assumed loan")),
    Choice("seller_financing", "Seller financing", ("seller financing", "seller note")),
    Choice("other_senior", "Other", ("other",)),
)

RATE_TYPES = (
    Choice("fixed", "Fixed", ("fixed rate",)),
    Choice("floating", "Floating", ("floating rate", "variable", "variable rate", "floating_rate")),
)

RECOURSE = (
    Choice("non_recourse", "Non-recourse", ("nonrecourse", "non recourse", "no")),
    Choice("recourse", "Recourse", ("full recourse", "yes")),
)


FIELDS: tuple[FieldSpec, ...] = (
    # ---- Property -------------------------------------------------------
    FieldSpec(
        "name",
        "Deal name",
        "property",
        "text",
        "Deal",
        notes="How the deal is listed in DealRank",
        sample="Westwood Ridge Multifamily",
        synonyms=("deal_name", "property name", "property", "project name", "asset name", "name"),
    ),
    FieldSpec(
        "sub_asset_class",
        "Property type",
        "property",
        "choice",
        "Deal",
        notes="Pick from the list",
        sample="suburban_garden",
        synonyms=("sub asset class", "asset class", "asset type", "product type"),
        choices=SUB_ASSET_CLASSES,
    ),
    FieldSpec(
        "leasing_mode",
        "Leasing mode",
        "property",
        "choice",
        "Deal",
        notes="Per bed is typical for student housing",
        sample="per_unit",
        synonyms=("lease type", "leased by"),
        choices=LEASING_MODES,
    ),
    FieldSpec(
        "purchase_price",
        "Purchase price",
        "property",
        "money",
        "Deal",
        unit="$",
        sample="24500000",
        synonyms=("acquisition price", "contract price", "price", "purchase"),
    ),
    FieldSpec(
        "closing_costs",
        "Closing costs",
        "property",
        "money",
        "Deal",
        unit="$",
        sample="490000",
        synonyms=("closing cost", "transaction costs", "acquisition costs", "acquisition fees"),
    ),
    FieldSpec(
        "hold_period_years",
        "Hold period",
        "property",
        "integer",
        "Deal",
        unit="years",
        notes="Whole years, 1 to 30",
        sample="10",
        synonyms=(
            "holding period",
            "hold years",
            "hold",
            "investment horizon",
            "hold period years",
        ),
    ),
    FieldSpec(
        "unit_count",
        "Number of units",
        "property",
        "integer",
        "Revenue",
        unit="units",
        notes="Per-unit deals. Leave blank to use the unit mix total",
        synonyms=("units", "unit count", "total units", "no of units", "number units"),
    ),
    FieldSpec(
        "monthly_rent_per_unit",
        "Average monthly rent per unit",
        "property",
        "money",
        "Revenue",
        unit="$/month",
        notes="Per-unit deals. Leave blank to use the unit mix average",
        synonyms=(
            "average rent",
            "avg rent",
            "average monthly rent",
            "avg monthly rent",
            "rent per unit",
            "monthly rent",
            "in place rent",
            "average rent per unit",
        ),
    ),
    FieldSpec(
        "bed_count",
        "Number of beds",
        "property",
        "integer",
        "Revenue",
        unit="beds",
        notes="Per-bed deals only",
        synonyms=("beds", "bed count", "total beds"),
    ),
    FieldSpec(
        "monthly_rent_per_bed",
        "Average monthly rent per bed",
        "property",
        "money",
        "Revenue",
        unit="$/month",
        notes="Per-bed deals only",
        synonyms=("rent per bed", "monthly rent per bed", "average rent per bed"),
    ),
    FieldSpec(
        "vacancy_rate_pct",
        "Vacancy rate",
        "property",
        "percent",
        "Revenue",
        unit="%",
        sample="5",
        synonyms=("vacancy", "economic vacancy", "physical vacancy", "vacancy loss", "vacancy pct"),
    ),
    FieldSpec(
        "credit_loss_rate_pct",
        "Credit loss",
        "property",
        "percent",
        "Revenue",
        unit="% of rent",
        sample="0",
        synonyms=("credit loss rate", "bad debt", "collection loss"),
    ),
    FieldSpec(
        "rent_growth_rate_pct",
        "Rent growth",
        "property",
        "percent",
        "Revenue",
        unit="% per year",
        sample="3",
        synonyms=("rent growth rate", "rental growth", "annual rent growth", "rent escalation"),
    ),
    FieldSpec(
        "other_income_annual",
        "Other income",
        "property",
        "money",
        "Revenue",
        unit="$/year",
        notes="Parking, storage, fees. Leave at 0 to use the helpers below",
        sample="0",
        synonyms=("ancillary income", "misc income", "miscellaneous income", "other revenue"),
    ),
    FieldSpec(
        "other_income_growth_rate_pct",
        "Other income growth",
        "property",
        "percent",
        "Revenue",
        unit="% per year",
        sample="0",
        synonyms=("other income growth rate",),
    ),
    FieldSpec(
        "opex_annual",
        "Operating expenses",
        "property",
        "money",
        "Expenses",
        unit="$/year",
        notes="Year 1, excluding management fee and reserves",
        sample="720000",
        synonyms=(
            "opex",
            "total operating expenses",
            "annual operating expenses",
            "total expenses",
            "annual opex",
        ),
    ),
    FieldSpec(
        "expense_growth_rate_pct",
        "Expense growth",
        "property",
        "percent",
        "Expenses",
        unit="% per year",
        sample="3",
        synonyms=("expense growth rate", "opex growth", "expense inflation"),
    ),
    FieldSpec(
        "management_fee_rate_pct",
        "Management fee",
        "property",
        "percent",
        "Expenses",
        unit="% of income",
        sample="0",
        synonyms=("management fee rate", "mgmt fee", "property management fee"),
    ),
    FieldSpec(
        "replacement_reserve_per_unit_or_bed",
        "Replacement reserves",
        "property",
        "money",
        "Expenses",
        unit="$/unit/year",
        sample="0",
        synonyms=("replacement reserve", "reserves", "capex reserve", "reserves per unit"),
    ),
    FieldSpec(
        "turnover_cost_per_unit_or_bed",
        "Turnover cost",
        "property",
        "money",
        "Expenses",
        unit="$ per turn",
        sample="800",
        synonyms=("turnover_cost", "make ready cost", "make ready", "turn cost"),
    ),
    FieldSpec(
        "annual_turnover_rate_pct",
        "Turnover rate",
        "property",
        "percent",
        "Expenses",
        unit="% per year",
        sample="55",
        synonyms=("turnover_rate_pct", "annual turnover", "annual turnover rate"),
    ),
    FieldSpec(
        "lease_expiration_month",
        "Lease expiration month",
        "property",
        "integer",
        "Expenses",
        unit="1-12",
        notes="Month most leases end",
        sample="6",
        synonyms=("lease expiry month", "lease turn month"),
    ),
    FieldSpec(
        "exit_cap_rate_pct",
        "Exit cap rate",
        "property",
        "percent",
        "Exit",
        unit="%",
        sample="5.75",
        synonyms=("exit cap", "terminal cap rate", "reversion cap rate", "residual cap rate"),
    ),
    FieldSpec(
        "selling_costs_rate_pct",
        "Selling costs",
        "property",
        "percent",
        "Exit",
        unit="% of sale price",
        sample="2",
        synonyms=("selling cost", "cost of sale", "costs of sale", "disposition costs"),
    ),
    # ---- Ancillary income helpers --------------------------------------
    FieldSpec(
        "surface_parking_stalls",
        "Surface parking stalls",
        "ancillary",
        "integer",
        "Ancillary income (optional)",
        unit="stalls",
        sample="180",
        synonyms=("surface parking", "surface stalls"),
    ),
    FieldSpec(
        "covered_parking_stalls",
        "Covered parking stalls",
        "ancillary",
        "integer",
        "Ancillary income (optional)",
        unit="stalls",
        sample="40",
        synonyms=("covered parking", "carports"),
    ),
    FieldSpec(
        "parking_monthly_rate",
        "Parking rate",
        "ancillary",
        "money",
        "Ancillary income (optional)",
        unit="$/stall/month",
        sample="50",
        synonyms=("parking monthly rate", "parking fee"),
    ),
    FieldSpec(
        "parking_occupancy_pct",
        "Parking occupancy",
        "ancillary",
        "percent",
        "Ancillary income (optional)",
        unit="%",
        sample="85",
        synonyms=("parking occupancy rate",),
    ),
    FieldSpec(
        "storage_units",
        "Storage units",
        "ancillary",
        "integer",
        "Ancillary income (optional)",
        unit="units",
        sample="30",
        synonyms=("storage",),
    ),
    FieldSpec(
        "storage_monthly_fee",
        "Storage fee",
        "ancillary",
        "money",
        "Ancillary income (optional)",
        unit="$/month",
        sample="60",
        synonyms=("storage monthly fee", "storage rent"),
    ),
    FieldSpec(
        "pet_monthly_fee",
        "Pet rent",
        "ancillary",
        "money",
        "Ancillary income (optional)",
        unit="$/month",
        sample="35",
        synonyms=("pet monthly fee", "pet fee"),
    ),
    FieldSpec(
        "pet_penetration_pct",
        "Units with pets",
        "ancillary",
        "percent",
        "Ancillary income (optional)",
        unit="%",
        sample="30",
        synonyms=("pet penetration", "pet penetration pct"),
    ),
    FieldSpec(
        "tech_package_monthly_fee",
        "Tech package fee",
        "ancillary",
        "money",
        "Ancillary income (optional)",
        unit="$/bed/month",
        notes="Student housing",
        synonyms=("tech package", "technology fee"),
    ),
    FieldSpec(
        "furniture_package_monthly_fee",
        "Furniture package fee",
        "ancillary",
        "money",
        "Ancillary income (optional)",
        unit="$/bed/month",
        notes="Student housing",
        synonyms=("furniture package", "furniture fee"),
    ),
    FieldSpec(
        "garage_parking_stalls",
        "Garage parking stalls",
        "ancillary",
        "integer",
        "Ancillary income (optional)",
        unit="stalls",
        notes="Urban mid-rise",
        synonyms=("garage stalls", "structured parking stalls"),
    ),
    FieldSpec(
        "garage_monthly_rate",
        "Garage parking rate",
        "ancillary",
        "money",
        "Ancillary income (optional)",
        unit="$/stall/month",
        notes="Urban mid-rise",
        synonyms=("garage monthly rate", "garage rate"),
    ),
    FieldSpec(
        "commercial_retail_sqft",
        "Retail square feet",
        "ancillary",
        "integer",
        "Ancillary income (optional)",
        unit="sq ft",
        notes="Urban mid-rise",
        synonyms=("commercial retail sqft", "retail sf", "commercial sf", "retail area"),
    ),
    FieldSpec(
        "commercial_rent_sqft_annual",
        "Retail rent",
        "ancillary",
        "money",
        "Ancillary income (optional)",
        unit="$/sq ft/year",
        notes="Urban mid-rise, NNN",
        synonyms=("commercial rent sqft annual", "retail rent psf", "commercial rent"),
    ),
    # ---- Financing ------------------------------------------------------
    FieldSpec(
        "senior_loan_type",
        "Senior loan type",
        "financing",
        "choice",
        "Senior loan",
        notes="Pick from the list",
        sample="agency_fannie_mae",
        synonyms=("loan type", "lender", "lender type", "debt type", "loan program"),
        choices=SENIOR_LOAN_TYPES,
    ),
    FieldSpec(
        "loan_amount",
        "Loan amount",
        "financing",
        "money",
        "Senior loan",
        unit="$",
        sample="15925000",
        synonyms=(
            "senior loan amount",
            "loan",
            "senior loan",
            "mortgage amount",
            "debt amount",
            "loan proceeds",
            "first mortgage",
        ),
    ),
    FieldSpec(
        "rate_type",
        "Rate type",
        "financing",
        "choice",
        "Senior loan",
        sample="fixed",
        synonyms=("interest rate type", "loan structure", "fixed or floating"),
        choices=RATE_TYPES,
    ),
    FieldSpec(
        "interest_rate_pct",
        "Interest rate",
        "financing",
        "percent",
        "Senior loan",
        unit="%",
        notes="Fixed-rate loans",
        sample="6.25",
        synonyms=("rate", "coupon", "note rate", "loan rate", "senior interest rate"),
    ),
    FieldSpec(
        "index_name",
        "Index",
        "financing",
        "text",
        "Senior loan",
        notes="Floating-rate loans, e.g. SOFR",
        synonyms=("index name", "rate index"),
    ),
    FieldSpec(
        "index_rate_pct",
        "Index rate",
        "financing",
        "percent",
        "Senior loan",
        unit="%",
        notes="Floating-rate loans",
        synonyms=("sofr", "sofr rate", "sofr_base_rate_pct", "base rate"),
    ),
    FieldSpec(
        "spread_bps",
        "Spread",
        "financing",
        "number",
        "Senior loan",
        unit="bps",
        notes="Floating-rate loans, in basis points",
        synonyms=("spread bps", "margin", "lender spread"),
    ),
    FieldSpec(
        "io_months",
        "Interest-only period",
        "financing",
        "integer",
        "Senior loan",
        unit="months",
        sample="24",
        synonyms=("io months", "io period", "interest only months", "interest only", "io"),
    ),
    FieldSpec(
        "amortization_years",
        "Amortization",
        "financing",
        "integer",
        "Senior loan",
        unit="years",
        sample="30",
        synonyms=("amortization period", "amortization years", "amort", "amortization term"),
    ),
    FieldSpec(
        "term_years",
        "Loan term",
        "financing",
        "integer",
        "Senior loan",
        unit="years",
        sample="10",
        synonyms=("term", "maturity", "term years", "loan_term_years", "loan maturity"),
    ),
    FieldSpec(
        "recourse",
        "Recourse",
        "financing",
        "choice",
        "Senior loan",
        sample="non_recourse",
        choices=RECOURSE,
    ),
    FieldSpec(
        "origination_fee_pct",
        "Origination fee",
        "financing",
        "percent",
        "Senior loan",
        unit="% of loan",
        sample="1",
        synonyms=("loan fee", "financing fee", "origination", "lender fee"),
    ),
    FieldSpec(
        "rate_cap_cost",
        "Rate cap cost",
        "financing",
        "money",
        "Senior loan",
        unit="$",
        notes="Floating-rate loans",
        sample="0",
        synonyms=("interest rate cap", "rate cap"),
    ),
    FieldSpec(
        "mezzanine_loan_amount",
        "Mezzanine loan amount",
        "financing",
        "money",
        "Mezzanine and preferred equity (optional)",
        unit="$",
        sample="0",
        synonyms=("mezzanine", "mezz loan", "mezz", "mezzanine debt"),
    ),
    FieldSpec(
        "mezzanine_interest_rate_pct",
        "Mezzanine interest rate",
        "financing",
        "percent",
        "Mezzanine and preferred equity (optional)",
        unit="%",
        sample="0",
        synonyms=("mezz rate", "mezzanine rate"),
    ),
    FieldSpec(
        "preferred_equity_amount",
        "Preferred equity amount",
        "financing",
        "money",
        "Mezzanine and preferred equity (optional)",
        unit="$",
        sample="0",
        synonyms=("preferred equity", "pref equity"),
    ),
    FieldSpec(
        "preferred_return_pct",
        "Preferred return",
        "financing",
        "percent",
        "Mezzanine and preferred equity (optional)",
        unit="%",
        sample="0",
        synonyms=("pref return", "preferred equity return"),
    ),
)

FIELD_BY_KEY = {f.key: f for f in FIELDS}


@dataclass(frozen=True)
class MixColumn:
    key: str
    label: str
    synonyms: tuple[str, ...]


# Columns of a unit mix table, keyed as the form's unit mix rows
# (frontend UnitMixTier). The first is the row label.
UNIT_MIX_COLUMNS: tuple[MixColumn, ...] = (
    MixColumn(
        "name",
        "Unit type",
        ("unit_mix", "type", "floor plan", "floorplan", "plan", "unit mix", "description"),
    ),
    MixColumn(
        "units",
        "Units",
        ("unit count", "number of units", "no of units", "count", "qty", "total units"),
    ),
    MixColumn(
        "bedsPerUnit",
        "Beds per unit",
        ("beds", "bedrooms", "br", "bd", "beds per unit", "bedrooms per unit"),
    ),
    MixColumn(
        "avgSqFt",
        "Avg sq ft",
        ("sq ft", "sqft", "sf", "avg sf", "average sf", "square feet", "size", "unit sf", "nrsf"),
    ),
    MixColumn(
        "rent",
        "Monthly rent",
        (
            "rent",
            "avg rent",
            "average rent",
            "market rent",
            "in place rent",
            "asking rent",
            "rent per unit",
        ),
    ),
)

SAMPLE_UNIT_MIX = (
    ("Studio", 20, 1, 540, 1200),
    ("1 Bed / 1 Bath", 60, 1, 720, 1450),
    ("2 Bed / 2 Bath", 80, 2, 980, 1800),
    ("3 Bed / 2 Bath", 20, 3, 1240, 2200),
    ("4+ Bed", 0, 4, 1500, 0),
)
