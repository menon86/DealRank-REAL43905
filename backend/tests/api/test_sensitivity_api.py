from decimal import Decimal as D

from tests.api.payloads import SUBURBAN_GARDEN_PAYLOAD


def _deal(client):
    return client.post("/deals", json=SUBURBAN_GARDEN_PAYLOAD).json()["id"]


def test_sweep_defaults_center_on_the_deal_and_include_its_base_case(client):
    deal_id = _deal(client)
    metrics = client.get(f"/deals/{deal_id}/metrics").json()
    resp = client.post(
        f"/deals/{deal_id}/sensitivity", json={"variable": "exit_cap_rate", "steps": 13}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert D(body["base_value"]) == D("0.055")
    values = [D(p["value"]) for p in body["points"]]
    assert values[0] == D("0.040") and values[-1] == D("0.070") and len(values) == 13
    base_point = body["points"][6]
    assert D(base_point["value"]) == D("0.055")
    assert D(base_point["unlevered_irr"]) == D(metrics["unlevered_irr"])
    irrs = [D(p["unlevered_irr"]) for p in body["points"]]
    assert irrs == sorted(irrs, reverse=True)


def test_sweep_explicit_range_for_rent_growth(client):
    deal_id = _deal(client)
    body = client.post(
        f"/deals/{deal_id}/sensitivity",
        json={"variable": "rent_growth_rate", "low": "0", "high": "0.05", "steps": 6},
    ).json()
    assert [D(p["value"]) for p in body["points"]] == [D(x) / 100 for x in range(0, 6)]
    irrs = [D(p["unlevered_irr"]) for p in body["points"]]
    assert irrs == sorted(irrs)


def test_sweep_validation(client):
    deal_id = _deal(client)
    url = f"/deals/{deal_id}/sensitivity"
    assert client.post(url, json={"variable": "vacancy_rate"}).status_code == 422
    assert (
        client.post(
            url, json={"variable": "exit_cap_rate", "low": "0.06", "high": "0.05"}
        ).status_code
        == 422
    )
    missing = "00000000-0000-0000-0000-000000000000"
    assert (
        client.post(f"/deals/{missing}/sensitivity", json={"variable": "exit_cap_rate"}).status_code
        == 404
    )


def test_monte_carlo_with_user_hurdle(client):
    deal_id = _deal(client)
    resp = client.post(
        f"/deals/{deal_id}/monte-carlo",
        json={"simulations": 200, "seed": 11, "hurdle": "0.08", "exit_cap_sd": "0.005"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["hurdle_source"] == "user" and D(body["hurdle"]) == D("0.08")
    assert body["simulations"] == 200 and body["converged"] == 200
    assert sum(b["count"] for b in body["unlevered_histogram"]) == 200
    assert D(body["unlevered_irr"]["p5"]) < D(body["unlevered_irr"]["p95"])
    assert 0 <= D(body["prob_below_hurdle"]) <= 1
    # Same seed, same answer.
    again = client.post(
        f"/deals/{deal_id}/monte-carlo",
        json={"simulations": 200, "seed": 11, "hurdle": "0.08", "exit_cap_sd": "0.005"},
    ).json()
    assert again == body


def test_monte_carlo_limits(client):
    deal_id = _deal(client)
    url = f"/deals/{deal_id}/monte-carlo"
    assert client.post(url, json={"simulations": 5001, "hurdle": "0.08"}).status_code == 422
    assert client.post(url, json={"simulations": 0, "hurdle": "0.08"}).status_code == 422
    # Without a user hurdle the risk-adjusted one is needed; no reference data => 409.
    assert client.post(url, json={"simulations": 10}).status_code == 409
