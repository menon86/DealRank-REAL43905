"""Risk-adjusted hurdle, DSCR gate, and preference scoring — pure engine."""

from decimal import Decimal as D

import pytest

from app.engine.ranking import (
    Candidate,
    RiskAdjustedHurdle,
    Weights,
    passes_dscr_gate,
    questionnaire_to_weights,
    score_candidates,
)


def test_hurdle_is_treasury_plus_spread_plus_growth():
    h = RiskAdjustedHurdle(treasury_yield=D("0.046"), spread_bps=130, noi_growth=D("0.02"))
    assert h.cap_rate == D("0.059")
    assert h.total == D("0.079")


def test_dscr_gate_boundary_and_all_cash():
    assert passes_dscr_gate(D("1.25"), D("1.25"))  # at the minimum passes
    assert not passes_dscr_gate(D("1.2499"), D("1.25"))
    assert passes_dscr_gate(None, D("1.25"))  # no debt, nothing to fail


def test_questionnaire_weights_sum_to_one_and_follow_answers():
    balanced = questionnaire_to_weights("total_return", 3, 3)
    assert balanced.irr + balanced.cash_flow + balanced.risk == 1
    assert balanced.irr > balanced.cash_flow == balanced.risk

    cautious = questionnaire_to_weights("total_return", 1, 3)
    aggressive = questionnaire_to_weights("total_return", 5, 3)
    assert cautious.risk > balanced.risk > aggressive.risk

    income = questionnaire_to_weights("cash_flow", 3, 5)
    assert income.cash_flow > questionnaire_to_weights("cash_flow", 3, 1).cash_flow


def test_questionnaire_rejects_bad_answers():
    with pytest.raises(ValueError):
        questionnaire_to_weights("yolo", 3, 3)
    with pytest.raises(ValueError):
        questionnaire_to_weights("cash_flow", 6, 3)


def test_weights_must_have_a_positive_entry():
    with pytest.raises(ValueError):
        Weights(D(0), D(0), D(0)).normalized()


def _cand(key, spread, cash_yield, dscr, leverage):
    return Candidate(key, D(spread), D(cash_yield), None if dscr is None else D(dscr), D(leverage))


CANDS = [
    _cand("high_return", "0.05", "0.03", "1.00", "0.80"),
    _cand("high_income", "0.01", "0.08", "1.50", "0.40"),
    _cand("safe", "-0.03", "0.04", "2.00", "0.20"),
]


def test_return_only_weights_reduce_to_spread_ordering():
    scored = score_candidates(CANDS, Weights(D(1), D(0), D(0)))
    by_key = {s.key: s.score for s in scored}
    assert by_key["high_return"] == 1
    assert by_key["safe"] == 0
    assert by_key["high_return"] > by_key["high_income"] > by_key["safe"]


def test_each_single_factor_picks_its_own_winner():
    def winner(weights):
        scored = score_candidates(CANDS, weights)
        return max(scored, key=lambda s: s.score).key

    assert winner(Weights(D(1), D(0), D(0))) == "high_return"
    assert winner(Weights(D(0), D(1), D(0))) == "high_income"
    assert winner(Weights(D(0), D(0), D(1))) == "safe"


def test_risk_factor_is_mean_of_scaled_dscr_and_unlevered_share():
    scored = {s.key: s for s in score_candidates(CANDS, Weights(D(0), D(0), D(1)))}
    # safe: DSCR 2.0 is the ceiling (1), leverage 20% -> equity share 80% is past the ceiling (1).
    assert scored["safe"].factors.risk == 1
    # high_return: DSCR 1.0 is the floor (0), leverage 80% -> equity share 20% is the floor (0).
    assert scored["high_return"].factors.risk == 0
    # high_income: DSCR 1.5 -> 0.5, equity share 60% is the ceiling -> 1.
    assert scored["high_income"].factors.risk == D("0.75")


def test_scores_do_not_change_when_other_candidates_are_added():
    # Min-max scoring made A's score depend on who else was in the comparison.
    a = _cand("a", "0.02", "0.05", "1.4", "0.6")
    b = _cand("b", "0.03", "0.04", "1.5", "0.5")
    outlier = _cand("outlier", "0.40", "0.30", "9", "0")
    weights = Weights(D(1), D(1), D(1))
    alone = {s.key: s.score for s in score_candidates([a, b], weights)}
    crowded = {s.key: s.score for s in score_candidates([a, b, outlier], weights)}
    assert alone["a"] == crowded["a"] and alone["b"] == crowded["b"]


def test_single_candidate_is_scored_on_its_merits_not_neutral():
    strong = score_candidates([_cand("a", "0.05", "0.08", "2", "0.2")], Weights(D(1), D(1), D(1)))
    weak = score_candidates([_cand("a", "-0.03", "0.03", "1", "0.8")], Weights(D(1), D(1), D(1)))
    assert abs(strong[0].score - 1) < D("1e-20") and weak[0].score == 0


def test_identical_deals_tie_and_all_cash_is_safe():
    same = [_cand("a", "0.02", "0.05", "1.4", "0.6"), _cand("b", "0.02", "0.05", "1.4", "0.6")]
    scores = score_candidates(same, Weights(D(1), D(1), D(1)))
    assert scores[0].score == scores[1].score

    cash = score_candidates(
        [_cand("cash", "0.02", "0.05", None, "0"), _cand("lev", "0.02", "0.05", "1.4", "0.6")],
        Weights(D(0), D(0), D(1)),
    )
    assert cash[0].factors.risk > cash[1].factors.risk


def test_debt_yield_gate():
    from app.engine.ranking import passes_debt_yield_gate

    assert passes_debt_yield_gate(D("0.07"), None)  # gate off
    assert passes_debt_yield_gate(None, D("0.09"))  # no debt
    assert passes_debt_yield_gate(D("0.09"), D("0.09"))
    assert not passes_debt_yield_gate(D("0.0899"), D("0.09"))


def test_empty_candidates():
    assert score_candidates([], Weights(D(1), D(0), D(0))) == []
