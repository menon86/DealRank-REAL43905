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


def _cand(key, spread, coc, dscr, ltv):
    return Candidate(key, D(spread), D(coc), None if dscr is None else D(dscr), D(ltv))


CANDS = [
    _cand("high_return", "0.04", "0.02", "1.30", "0.70"),
    _cand("high_income", "0.01", "0.08", "1.50", "0.60"),
    _cand("safe", "0.00", "0.04", "2.00", "0.40"),
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


def test_risk_factor_is_mean_of_normalized_dscr_and_unlevered_share():
    scored = {s.key: s for s in score_candidates(CANDS, Weights(D(0), D(0), D(1)))}
    # safe has the max DSCR (1.0 normalized) and the lowest LTV (1.0).
    assert scored["safe"].factors.risk == 1
    # high_return has the min DSCR (0) and the highest LTV (0).
    assert scored["high_return"].factors.risk == 0
    # high_income: dscr (1.5-1.3)/0.7, ltv (0.7-0.6)/0.3
    expected = ((D("0.2") / D("0.7")) + (D("0.1") / D("0.3"))) / 2
    assert scored["high_income"].factors.risk == expected


def test_ties_get_neutral_scores_and_all_cash_is_safe():
    same = [_cand("a", "0.02", "0.05", "1.4", "0.6"), _cand("b", "0.02", "0.05", "1.4", "0.6")]
    assert all(
        abs(s.score - D("0.5")) < D("1e-20")
        for s in score_candidates(same, Weights(D(1), D(1), D(1)))
    )

    cash = score_candidates(
        [_cand("cash", "0.02", "0.05", None, "0"), _cand("lev", "0.02", "0.05", "1.4", "0.6")],
        Weights(D(0), D(0), D(1)),
    )
    assert cash[0].factors.risk > cash[1].factors.risk


def test_empty_candidates():
    assert score_candidates([], Weights(D(1), D(0), D(0))) == []
