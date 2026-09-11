"""See docs/build-plan.md Phase 6 — PDF and PPTX export. Every prior
API/DB code path this session had a real bug the first time it actually
ran (a masked password, an enum stored by name instead of value, an
async-only test transport); these exist to catch the equivalent for
export rather than trusting it on lint alone.
"""

from tests.api.payloads import STUDENT_HOUSING_PAYLOAD, SUBURBAN_GARDEN_PAYLOAD


def _seed_two_deals(client) -> list[str]:
    student = client.post("/deals", json=STUDENT_HOUSING_PAYLOAD).json()
    suburban = client.post("/deals", json=SUBURBAN_GARDEN_PAYLOAD).json()
    return [student["id"], suburban["id"]]


def test_pdf_report_returns_a_real_pdf(client):
    deal_ids = _seed_two_deals(client)

    resp = client.get(
        "/reports/pdf", params=[("deal_ids", i) for i in deal_ids] + [("hurdle_rate", "0.08")]
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF-")
    assert len(resp.content) > 500


def test_pptx_report_returns_a_real_pptx(client):
    deal_ids = _seed_two_deals(client)

    resp = client.get(
        "/reports/pptx", params=[("deal_ids", i) for i in deal_ids] + [("hurdle_rate", "0.08")]
    )
    assert resp.status_code == 200
    assert (
        resp.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    )
    # PPTX/DOCX/XLSX files are zip archives — this is the zip magic number.
    assert resp.content.startswith(b"PK")
    assert len(resp.content) > 500


def test_pdf_report_unknown_deal_id_is_404(client):
    import uuid

    resp = client.get("/reports/pdf", params={"deal_ids": str(uuid.uuid4()), "hurdle_rate": "0.08"})
    assert resp.status_code == 404


def test_report_requires_at_least_one_deal_id(client):
    resp = client.get("/reports/pdf", params={"hurdle_rate": "0.08"})
    assert resp.status_code == 422
