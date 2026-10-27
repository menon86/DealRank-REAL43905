"""Spreadsheet import: the template round-trips, the old CSV templates still
read, and a workbook in someone else's layout is matched by its labels."""

import io
from decimal import Decimal

import pytest
from openpyxl import Workbook

from app.spreadsheet.fields import FIELDS
from app.spreadsheet.matcher import build_proposal, label_score, normalize
from app.spreadsheet.reader import SpreadsheetError, format_decimal, load_sheets, parse_number
from app.spreadsheet.template import build_template_bytes

OLD_UNDERWRITING_CSV = "\n".join(
    [
        "Property_Details,Value",
        "deal_name,Westwood Ridge Multifamily",
        "sub_asset_class,suburban_garden",
        "leasing_mode,per_unit",
        "purchase_price,24500000",
        "closing_costs,490000",
        "vacancy_rate_pct,5.0",
        "opex_annual,720000",
        "expense_growth_rate_pct,3.0",
        "rent_growth_rate_pct,3.0",
        "lease_expiration_month,6",
        "turnover_cost,800",
        "turnover_rate_pct,55.0",
        "hold_period_years,10",
        "exit_cap_rate_pct,5.75",
        "selling_costs_rate_pct,2.0",
        "",
        "Unit_Mix,Units,BedsPerUnit,AvgSqFt,MonthlyRent",
        "Studio,20,1,540,1200",
        "1bed,60,1,720,1450",
        "2bed,80,2,980,1800",
        "3bed,20,3,1240,2200",
        "4bed_plus,0,4,1500,0",
        "",
        "Ancillary_Inputs,Value",
        "surface_parking_stalls,180",
        "pet_penetration_pct,30",
    ]
)

OLD_FINANCING_CSV = "\n".join(
    [
        "Financing_Parameter,Value",
        "senior_loan_type,agency_fannie_mae",
        "loan_amount,15925000",
        "rate_type,fixed",
        "interest_rate_pct,6.25",
        "io_months,24",
        "amortization_years,30",
        "term_years,10",
        "recourse,non_recourse",
        "mezzanine_loan_amount,0",
    ]
)


def _values(proposal) -> dict[str, str]:
    return {f.key: f.value for f in proposal.fields if f.value is not None}


def _xlsx(build) -> bytes:
    wb = Workbook()
    build(wb)
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def _propose(filename: str, data: bytes):
    return build_proposal(filename, load_sheets(filename, data))


def test_template_has_the_expected_tabs():
    sheets = load_sheets("t.xlsx", build_template_bytes())
    assert [s.name for s in sheets] == [
        "Instructions",
        "Property",
        "Unit Mix",
        "Financing",
        "Lists",
    ]


def test_template_round_trips_every_sample_value():
    proposal = _propose("t.xlsx", build_template_bytes())
    values = _values(proposal)
    for spec in FIELDS:
        if spec.sample:
            expected = (
                spec.sample
                if spec.kind in ("text", "choice")
                else format_decimal(Decimal(spec.sample))
            )
            assert values.get(spec.key) == expected, spec.key
        else:
            assert spec.key not in values, spec.key
    assert all(f.confidence == "high" for f in proposal.fields if f.value is not None)
    mix = proposal.unit_mix
    assert mix is not None and mix.sheet == "Unit Mix"
    assert [r.cells[mix.mapping["name"]].text for r in mix.rows][:2] == ["Studio", "1 Bed / 1 Bath"]
    assert [r.cells[mix.mapping["rent"]].number for r in mix.rows] == [
        "1200",
        "1450",
        "1800",
        "2200",
        "0",
    ]
    assert proposal.warnings == []


def test_old_csv_templates_still_import():
    values = _values(_propose("old.csv", OLD_UNDERWRITING_CSV.encode()))
    assert values["name"] == "Westwood Ridge Multifamily"
    assert values["sub_asset_class"] == "suburban_garden"
    assert values["leasing_mode"] == "per_unit"
    assert values["purchase_price"] == "24500000"
    assert values["vacancy_rate_pct"] == "5"
    assert values["turnover_cost_per_unit_or_bed"] == "800"
    assert values["annual_turnover_rate_pct"] == "55"
    assert values["hold_period_years"] == "10"
    assert values["surface_parking_stalls"] == "180"

    proposal = _propose("old.csv", OLD_UNDERWRITING_CSV.encode())
    assert proposal.unit_mix is not None
    assert len(proposal.unit_mix.rows) == 5
    assert all(v is not None for v in proposal.unit_mix.mapping.values())

    financing = _values(_propose("fin.csv", OLD_FINANCING_CSV.encode()))
    assert financing == {
        "senior_loan_type": "agency_fannie_mae",
        "loan_amount": "15925000",
        "rate_type": "fixed",
        "interest_rate_pct": "6.25",
        "io_months": "24",
        "amortization_years": "30",
        "term_years": "10",
        "recourse": "non_recourse",
        "mezzanine_loan_amount": "0",
    }


def test_quoted_thousands_separators_in_csv():
    data = b'Field,Value\nPurchase Price,"$24,500,000"\nVacancy,5.5%\n'
    values = _values(_propose("deal.csv", data))
    assert values["purchase_price"] == "24500000"
    assert values["vacancy_rate_pct"] == "5.5"


def _broker_model(wb: Workbook) -> None:
    ws = wb.active
    ws.title = "Summary"
    ws["A1"] = "Maple Court Apartments - Acquisition Summary"
    ws["B3"], ws["D3"] = "Property Name:", "Maple Court Apartments"
    ws["B4"], ws["D4"] = "Acquisition Price", 31_250_000
    ws["B5"], ws["D5"] = "Price per Unit", 156_250
    ws["B6"], ws["D6"] = "Going-in Cap Rate", 0.052
    ws["D6"].number_format = "0.0%"
    ws["B7"], ws["D7"] = "Exit Cap", 0.0575
    ws["D7"].number_format = "0.00%"
    ws["B8"], ws["C8"], ws["D8"] = "Holding Period", "yrs", 7
    ws["B9"], ws["D9"] = "Economic Vacancy", "6%"
    ws["B10"], ws["D10"] = "Total Operating Expenses (Yr 1)", "$1,180,000"
    ws["B11"], ws["D11"] = "Rent Growth", 0.03

    loan = wb.create_sheet("Debt")
    loan["A1"], loan["B1"] = "Lender", "Freddie Mac"
    loan["A2"], loan["B2"] = "Loan Amount", "$20.3M"
    loan["A3"], loan["B3"] = "Interest Rate", 0.0595
    loan["A3"].number_format = "General"
    loan["B3"].number_format = "0.00%"
    loan["A4"], loan["B4"] = "IO Period (Years)", 2
    loan["A5"], loan["B5"] = "Amortization", 30
    loan["A6"], loan["B6"] = "Mezzanine Interest Rate", 0.11

    mix = wb.create_sheet("Rent Roll Summary")
    mix.append([])
    mix.append(["Floor Plan", "# Units", "Bed/Bath", "Avg SF", "Market Rent"])
    mix.append(["A1 - 1x1", 80, "1/1", 690, 1395])
    mix.append(["B1 - 2x2", 100, "2/2", 1010, 1725])
    mix.append(["C1 - 3x2", 20, "3/2", 1260, 2150])
    mix.append(["Total", 200, None, 905, 1621])


def test_own_layout_is_matched_by_label():
    proposal = _propose("broker.xlsx", _xlsx(_broker_model))
    values = _values(proposal)
    assert values["name"] == "Maple Court Apartments"
    assert values["purchase_price"] == "31250000"  # not the per-unit price
    assert values["exit_cap_rate_pct"] == "5.75"
    assert values["hold_period_years"] == "7"  # skips the "yrs" unit cell
    assert values["vacancy_rate_pct"] == "6"
    assert values["opex_annual"] == "1180000"
    assert values["rent_growth_rate_pct"] == "3"
    assert values["loan_amount"] == "20300000"
    assert values["interest_rate_pct"] == "5.95"
    assert values["io_months"] == "24"
    assert values["mezzanine_interest_rate_pct"] == "11"
    assert values["senior_loan_type"] == "agency_freddie_mac"
    # A going-in cap rate isn't any field.
    assert "Summary!D6" not in {f.candidate_id for f in proposal.fields if f.value}

    by_key = {f.key: f for f in proposal.fields}
    assert by_key["purchase_price"].source.cell == "D4"
    assert by_key["purchase_price"].source.label == "Acquisition Price"
    # A bare 0.03 is read as 3% and flagged.
    assert by_key["rent_growth_rate_pct"].confidence == "medium"
    assert by_key["rent_growth_rate_pct"].note

    mix = proposal.unit_mix
    assert mix is not None and mix.sheet == "Rent Roll Summary" and mix.header_row == 2
    assert len(mix.rows) == 3  # stops at the total row
    assert mix.mapping["name"] == 0
    assert mix.columns[mix.mapping["units"]].header == "# Units"
    assert mix.columns[mix.mapping["rent"]].header == "Market Rent"
    assert mix.columns[mix.mapping["avgSqFt"]].header == "Avg SF"

    # Every label/value pair is offered for manual mapping, used or not.
    ids = {c.id for c in proposal.candidates}
    assert {"Summary!D5", "Summary!D6", "Debt!B2"} <= ids


def test_unrecognized_file_warns_but_still_offers_cells():
    proposal = _propose("x.csv", b"Foo,12\nBar,baz\n")
    assert all(f.value is None for f in proposal.fields)
    assert proposal.warnings
    assert [c.label for c in proposal.candidates] == ["Foo", "Bar"]


@pytest.mark.parametrize(
    ("filename", "data", "message"),
    [
        ("deal.xls", b"x", ".xlsx"),
        ("deal.pdf", b"x", "Excel workbook"),
        ("deal.xlsx", b"not a zip", "couldn't be opened"),
        ("deal.csv", b"", "empty"),
    ],
)
def test_unreadable_files_raise_a_readable_error(filename, data, message):
    with pytest.raises(SpreadsheetError, match=message):
        load_sheets(filename, data)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("$24,500,000", "24500000"),
        ("(1,200)", "-1200"),
        ("5.5%", "5.5"),
        ("$20.3M", "20300000"),
        ("750k", "750000"),
        (0.0575, "0.0575"),
        ("n/a", None),
        (True, None),
    ],
)
def test_parse_number(raw, expected):
    assert parse_number(raw) == (None if expected is None else Decimal(expected))


def test_label_scoring():
    assert label_score(normalize("Purchase Price ($)"), "purchase price") == 3
    assert label_score(normalize("Cap Rate"), "rate") == 0  # single words match exactly only
    assert label_score(normalize("Purchase price per unit"), "purchase price") == 0
    assert 2 < label_score(normalize("Year 1 Operating Expenses"), "operating expenses") < 3
    assert normalize("BedsPerUnit") == "beds per unit"
