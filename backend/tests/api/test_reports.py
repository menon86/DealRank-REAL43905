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


def test_pptx_tables_fit_on_their_slides_at_five_deals(client):
    """Every table's stored geometry has to end inside the slide. The
    assumptions table used to end at 7.65" on a 7.5" slide, which nothing
    caught because the file still opened; five deals is the most the UI
    lets you compare, so the comparison slide is checked at its widest."""
    import io

    from pptx import Presentation

    deal_ids = _seed_two_deals(client) + _seed_two_deals(client)
    deal_ids.append(client.post("/deals", json=STUDENT_HOUSING_PAYLOAD).json()["id"])

    resp = client.get(
        "/reports/pptx", params=[("deal_ids", i) for i in deal_ids] + [("hurdle_rate", "0.08")]
    )
    assert resp.status_code == 200

    prs = Presentation(io.BytesIO(resp.content))
    tables = [shape for slide in prs.slides for shape in slide.shapes if shape.has_table]
    assert tables
    for shape in tables:
        table = shape.table
        assert shape.top + sum(row.height for row in table.rows) <= prs.slide_height
        assert shape.left + sum(col.width for col in table.columns) <= prs.slide_width


def test_pdf_report_survives_markup_characters_in_deal_names(client):
    names = ["Smith & Sons Apts", "Bldg <A> Plaza", "<b>Bold</b> Place", '<img src="x"/>']
    ids = [
        client.post("/deals", json={**SUBURBAN_GARDEN_PAYLOAD, "name": name}).json()["id"]
        for name in names
    ]
    resp = client.get(
        "/reports/pdf", params=[("deal_ids", i) for i in ids] + [("hurdle_rate", "0.08")]
    )
    assert resp.status_code == 200
    assert resp.content.startswith(b"%PDF-")


def _pdf_page_texts(pdf: bytes) -> list[str]:
    """Decoded content stream of each page, in page order. ReportLab writes
    one ASCII85 + Flate encoded content stream per page, with text drawn as
    `(string) Tj` operators, so a substring check per page is enough to tell
    which page a heading or table row landed on."""
    import base64
    import re
    import zlib

    streams = re.findall(
        rb"/Filter \[ /ASCII85Decode /FlateDecode \].*?stream\r?\n(.*?)~>\s*endstream",
        pdf,
        re.S,
    )
    return [zlib.decompress(base64.a85decode(s)).decode("latin-1") for s in streams]


def test_pdf_keeps_headings_with_tables_and_never_splits_a_table(client):
    """Five deals is the largest report the UI can ask for. Every heading
    must share a page with the start of its table, and each table must
    start and end on the same page."""
    deal_ids = _seed_two_deals(client) + _seed_two_deals(client)
    deal_ids.append(client.post("/deals", json=STUDENT_HOUSING_PAYLOAD).json()["id"])

    resp = client.get(
        "/reports/pdf", params=[("deal_ids", i) for i in deal_ids] + [("hurdle_rate", "0.08")]
    )
    assert resp.status_code == 200
    pages = _pdf_page_texts(resp.content)
    assert len(pages) >= 2

    def page_of(text: str) -> int:
        hits = [i for i, page in enumerate(pages) if f"({text})" in page]
        assert len(hits) == 1, f"{text!r} found on pages {hits}"
        return hits[0]

    # Comparison: heading, first row and last row on one page.
    assert page_of("Comparison") == page_of("Hold period") == page_of("Net sale proceeds")
    # Ranking: heading, header row and every ranked row on one page.
    assert page_of("Ranking") == page_of("Rank") == page_of("#1") == page_of("#5")
    # Assumptions heading sits with the first deal's table.
    assumptions_page = page_of("Assumptions")
    assert "(Sub-asset class)" in pages[assumptions_page]
    # Each assumptions table starts and ends on the same page.
    for page in pages:
        assert page.count("(Sub-asset class)") == page.count("(Selling costs rate)")
