"""The chat tools and preset answers, checked against the engine's known outputs
(docs/golden-case-derivation.md) and against independent_math. No LLM involved."""

import json
from datetime import date
from decimal import Decimal as D

import pytest

from app.api import chat_tools
from app.api.chat_presets import PRESETS, answer_preset
from app.api.chat_tools import TOOLS, ToolContext, run_tool
from app.api.ranking_data import RANKING_BASIS_NOTE
from app.api.risk_rank import BASIS_NOTE
from app.models.cap_rate_spread import CapRateSpread
from app.models.market_rent import MarketRent
from tests.engine import fixtures
from tests.engine.independent_math import forward_noi

STUDENT = "Campus View Student Housing"
GARDEN = "Willowbrook Suburban Garden"
MIDRISE = "Meridian Urban Mid-Rise"


@pytest.fixture()
def ctx(db_session, chat_deals):
    return ToolContext(db=db_session)


def call(ctx, name, **args):
    text, ok = run_tool(ctx, name, json.dumps(args))
    return json.loads(text), ok


def independent_dscr(deal, noi: D) -> D:
    r = deal.interest_rate / 12
    n = deal.amortization_years * 12
    growth = (1 + r) ** n
    payment = deal.loan_amount * r * growth / (growth - 1)
    return noi / (payment * 12)


# ------------------------------------------------------------------ tools


def test_list_deals(ctx):
    out, ok = call(ctx, "list_deals")
    assert ok and len(out["deals"]) == 3 and out["truncated"] is False
    student = next(d for d in out["deals"] if d["name"] == STUDENT)
    assert student["size"] == "240 beds" and student["purchase_price"] == "$21,500,000"


def test_get_deal_by_name_fragment_and_id(ctx, chat_deals):
    by_name, ok = call(ctx, "get_deal", deal="willowbrook")
    assert ok and by_name["name"] == GARDEN
    assert by_name["rent"] == "$1,450/unit/month" and by_name["loan"]["interest_rate"]
    by_id, _ = call(ctx, "get_deal", deal=str(chat_deals[GARDEN].id))
    assert by_id == by_name


def test_deal_lookup_errors_are_structured(ctx):
    missing, ok = call(ctx, "get_deal", deal="Nope")
    assert not ok and missing["error"] == "deal_not_found"
    ambiguous, ok = call(ctx, "get_deal", deal="e")  # matches all three names
    assert not ok and ambiguous["error"] == "ambiguous_deal" and ambiguous["candidates"]
    unknown_id, ok = call(ctx, "get_deal", deal="00000000-0000-0000-0000-000000000000")
    assert not ok and unknown_id["error"] == "deal_not_found"


def test_get_metrics_matches_independent_math(ctx):
    out, ok = call(ctx, "get_metrics", deal=STUDENT)
    assert ok
    seed = fixtures.STUDENT_HOUSING
    noi = forward_noi(seed, 1)
    assert out["year_one_noi"] == f"${noi:,.0f}"
    assert out["year_one"]["noi"] == out["year_one_noi"]
    assert out["year_one_dscr"] == f"{independent_dscr(seed, noi):.2f}x" == "1.33x"
    # golden case: net unlevered IRR 9.9086%; the ranking basis is the higher pre-cost IRR
    assert out["unlevered_irr_net_of_costs"] == "9.91%"
    assert D(out["unlevered_irr_before_costs_ranking_basis"].rstrip("%")) > D("9.91")
    assert len(out["dscr_by_year"]) == seed.hold_period_years
    assert out["min_dscr_over_hold"] is not None


def test_get_metrics_garden_and_midrise_dscr(ctx):
    garden, _ = call(ctx, "get_metrics", deal=GARDEN)
    midrise, _ = call(ctx, "get_metrics", deal=MIDRISE)
    assert garden["year_one_dscr"] == "1.46x"
    assert midrise["year_one_dscr"] == "0.87x"
    seed = fixtures.URBAN_MIDRISE
    assert midrise["year_one_dscr"] == f"{independent_dscr(seed, forward_noi(seed, 1)):.2f}x"


def test_rank_deals_simple_hurdle(ctx):
    out, ok = call(ctx, "rank_deals", hurdle_rate=0.07)
    assert ok and out["basis_note"] == RANKING_BASIS_NOTE
    assert [r["deal"] for r in out["ranking"]] == [GARDEN, STUDENT, MIDRISE]
    assert out["hurdle_rate"] == "7.00%"
    assert out["ranking"][1]["unlevered_irr"] is not None


def test_rank_deals_defaults_to_the_ui_hurdle_or_asks_for_one(db_session, chat_deals):
    out, ok = call(ToolContext(db=db_session), "rank_deals")
    assert not ok and out["error"] == "missing_argument"
    out, ok = call(ToolContext(db=db_session, hurdle_rate=D("0.07")), "rank_deals")
    assert ok and out["hurdle_rate"] == "7.00%"


def test_risk_rank_gate_exclusion_hurdles_and_basis(ctx):
    out, ok = call(ctx, "risk_rank")
    assert ok and out["basis_note"] == BASIS_NOTE
    assert [r["deal"] for r in out["ranked"]] == [GARDEN, STUDENT]
    top = out["ranked"][0]
    assert top["hurdle"]["total"] == "6.61%"
    assert top["hurdle"]["cap_rate_spread"] == "61 bps"
    assert top["hurdle"]["treasury"] == "4.60%"
    gross = D(
        call(ctx, "get_metrics", deal=GARDEN)[0]["unlevered_irr_before_costs_ranking_basis"].rstrip(
            "%"
        )
    )
    assert top["unlevered_irr_before_costs"] == f"{gross}%"
    assert top["spread_vs_hurdle"] == f"{gross - D('6.61')}%"
    assert [e["deal"] for e in out["excluded"]] == [MIDRISE]
    assert "0.87x" in out["excluded"][0]["reason"] and "1.25x" in out["excluded"][0]["reason"]
    assert out["treasury"]["is_fallback"] is False


def test_risk_rank_takes_ui_defaults_and_overrides(db_session, chat_deals):
    selected = (chat_deals[GARDEN].id, chat_deals[STUDENT].id)
    ui = ToolContext(db=db_session, selected_deal_ids=selected, dscr_minimum=D("1.4"))
    out, _ = call(ui, "risk_rank")
    assert [r["deal"] for r in out["ranked"]] == [GARDEN]  # 1.4x gate from the UI
    assert [e["deal"] for e in out["excluded"]] == [STUDENT]
    out, _ = call(ui, "risk_rank", dscr_minimum=0, weights={"irr": 0, "cash_flow": 0, "risk": 1})
    assert len(out["ranked"]) == 2 and out["weights"]["risk"] == "100%"


def test_risk_rank_labels_a_fallback_treasury(ctx, chat_treasury):
    chat_treasury["source"] = "fallback"
    out, _ = call(ctx, "risk_rank")
    assert out["treasury"]["is_fallback"] is True
    assert "FALLBACK" in out["treasury"]["source"] and out["treasury"]["as_of"] is None


def test_sensitivity_sweeps_exit_cap(ctx):
    out, ok = call(ctx, "sensitivity", deal=GARDEN, variable="exit_cap_rate", steps=3)
    assert ok and out["variable"] == "exit_cap_rate" and len(out["points"]) == 3
    irrs = [D(p["unlevered_irr"].rstrip("%")) for p in out["points"]]
    assert irrs == sorted(irrs, reverse=True)  # a higher exit cap lowers the return
    values = [p["exit_cap_rate"] for p in out["points"]]
    assert out["base_value"] in values or D(out["base_value"].rstrip("%")) > 0


def test_sensitivity_bad_range_is_an_error_not_a_crash(ctx):
    out, ok = call(ctx, "sensitivity", deal=GARDEN, variable="exit_cap_rate", low=0.09, high=0.05)
    assert not ok and out["error"] == "not_available"


def test_market_check_lists_geographies_then_compares(ctx, db_session):
    for period, rent in ((date(2026, 9, 1), "1500"), (date(2025, 9, 1), "1400")):
        db_session.add(
            MarketRent(
                source="zillow_zori",
                geography="West Lafayette, IN",
                sub_asset_class="all",
                period=period,
                median_rent=D(rent),
            )
        )
    db_session.flush()
    listing, ok = call(ctx, "market_check", deal=GARDEN)
    assert ok and listing["geographies"] == [
        {"geography": "West Lafayette, IN", "source": "zillow_zori"}
    ]
    out, ok = call(ctx, "market_check", deal=GARDEN, geography="West Lafayette, IN")
    assert ok and out["status"] == "ok" and out["market_rent"] == "$1,500"
    assert out["deal_rent"] == "$1,450" and out["variance_vs_market"] == "-3.33%"
    nodata, _ = call(ctx, "market_check", deal=GARDEN, geography="Nowhere")
    assert nodata["status"] == "no_data"


def test_get_hurdles_breakdown_and_fallback_label(ctx, chat_treasury):
    out, ok = call(ctx, "get_hurdles")
    assert ok and out["treasury"]["source"] == "live (FRED DGS10)"
    student = next(h for h in out["hurdles"] if h["sub_asset_class"] == "student_housing")
    assert student == {
        "sub_asset_class": "student_housing",
        "treasury": "4.60%",
        "cap_rate_spread": "130 bps",
        "cap_rate": "5.90%",
        "noi_growth": "2.00%",
        "total_hurdle": "7.90%",
        "survey": "test survey 2026H1",
    }
    chat_treasury["source"] = "fallback"
    assert call(ctx, "get_hurdles")[0]["treasury"]["is_fallback"] is True


def test_missing_reference_data_is_reported(db_session, chat_deals):
    ctx = ToolContext(db=db_session)
    ranked, ok = call(ctx, "risk_rank")
    assert ok
    db_session.execute(CapRateSpread.__table__.delete())
    out, ok = call(ctx, "risk_rank")
    assert not ok and out["error"] == "not_available" and "spread" in out["message"]


def test_no_deals_is_reported(db_session):
    out, ok = call(ToolContext(db=db_session), "risk_rank")
    assert not ok and out["error"] == "no_deals"


# ------------------------------------------------------------------ validation


def test_allowlist_is_exactly_the_read_only_tools():
    assert set(TOOLS) == {
        "list_deals",
        "get_deal",
        "get_metrics",
        "rank_deals",
        "risk_rank",
        "sensitivity",
        "market_check",
        "get_hurdles",
    }


def test_advertised_parameters_match_the_validators():
    for tool in TOOLS.values():
        advertised = set(tool.parameters["properties"])
        assert advertised == set(tool.args_model.model_fields), tool.name
        assert set(tool.parameters.get("required", [])) <= advertised


@pytest.mark.parametrize("name", ["delete_deal", "update_deal", "__import__", "", "Get_Deal"])
def test_unknown_or_write_tools_never_run(ctx, name):
    out, ok = call(ctx, name)
    assert not ok and out["error"] == "unknown_tool"
    assert "get_deal" in out["available_tools"] and "delete_deal" not in out["available_tools"]


def test_invalid_arguments_get_a_retryable_error(ctx):
    for raw in ("{not json", "[1]", '"x"'):
        out, ok = (lambda t: (json.loads(t[0]), t[1]))(run_tool(ctx, "get_deal", raw))
        assert not ok and out["error"] == "arguments_not_valid_json"

    out, ok = call(ctx, "get_deal")  # missing required field
    assert not ok and out["error"] == "invalid_arguments"
    assert (
        out["problems"][0]["field"] == "deal" and "deal" in out["expected_parameters"]["required"]
    )

    out, ok = call(ctx, "get_deal", deal="x", sql="drop table deals")  # extra field
    assert not ok and out["problems"][0]["field"] == "sql"

    out, ok = call(ctx, "sensitivity", deal=GARDEN, variable="vacancy_rate")  # bad enum
    assert not ok and out["problems"][0]["field"] == "variable"

    out, ok = call(ctx, "sensitivity", deal=GARDEN, variable="exit_cap_rate", steps=500)
    assert not ok and out["problems"][0]["field"] == "steps"

    out, ok = call(ctx, "rank_deals", hurdle_rate="seven percent")
    assert not ok and out["problems"][0]["field"] == "hurdle_rate"

    out, ok = call(ctx, "risk_rank", weights={"irr": -1, "cash_flow": 0, "risk": 0})
    assert not ok and out["error"] == "invalid_arguments"


def test_empty_arguments_are_fine_for_no_arg_tools(ctx):
    for raw in ("", "{}", None):
        text, ok = run_tool(ctx, "list_deals", raw)
        assert ok and "deals" in json.loads(text)


def test_oversized_results_are_refused_not_sent(ctx, monkeypatch):
    monkeypatch.setattr(chat_tools, "MAX_RESULT_CHARS", 50)
    out, ok = call(ctx, "get_metrics", deal=STUDENT)
    assert not ok and out["error"] == "result_too_large"


def test_engine_failure_becomes_tool_failed(ctx, monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("secret internals")

    monkeypatch.setattr(chat_tools, "compute", boom)
    text, ok = run_tool(ctx, "get_metrics", json.dumps({"deal": STUDENT}))
    assert not ok and json.loads(text)["error"] == "tool_failed"
    assert "secret internals" not in text


# ------------------------------------------------------------------ presets


def test_every_preset_answers_with_engine_numbers(ctx):
    answers = {p.id: answer_preset(ctx, p.id) for p in PRESETS}
    for text in answers.values():
        assert "not investment advice" in text

    top = answers["top_deal"]
    assert top.startswith(f"{GARDEN} is ranked #1 of 2")
    assert "6.61%" in top and "61 bps" in top and "spread 4.00%" in top
    assert "never sorted on" in top

    gate = answers["dscr_gate"]
    assert MIDRISE in gate and "0.87x" in gate and "1.25x" in gate

    hurdles = answers["hurdle_breakdown"]
    assert "7.90%" in hurdles and "6.61%" in hurdles and "6.60%" in hurdles
    assert "live (FRED DGS10)" in hurdles

    extremes = answers["dscr_extremes"]
    assert f"Highest lowest-DSCR-over-the-hold: {GARDEN}" in extremes
    assert f"Lowest: {MIDRISE}" in extremes

    assert "unlevered IRR" in answers["ranking_basis"]


def test_presets_flag_a_fallback_treasury(ctx, chat_treasury):
    chat_treasury["source"] = "fallback"
    assert "fallback default" in answer_preset(ctx, "hurdle_breakdown")
    assert "not a live quote" in answer_preset(ctx, "hurdle_breakdown")


def test_presets_when_everything_is_gated_out(db_session, chat_deals):
    ui = ToolContext(db=db_session, dscr_minimum=D("3"))
    assert "No deal is ranked" in answer_preset(ui, "top_deal")
    assert answer_preset(ui, "dscr_gate").count("\n- ") == 3


def test_presets_without_data_say_so(db_session):
    text = answer_preset(ToolContext(db=db_session), "top_deal")
    assert text.startswith("I can't answer that yet")
    assert "No deal" in answer_preset(ToolContext(db=db_session), "dscr_extremes")


def test_unknown_preset_raises(ctx):
    with pytest.raises(KeyError):
        answer_preset(ctx, "nope")
