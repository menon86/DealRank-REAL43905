"""Brand palette and boilerplate shared by the PDF and PPTX exports, so the
two formats read as one product. Hex strings (no '#') because reportlab and
python-pptx each wrap them in their own colour type.
"""

NAME = "DealRank"
REPORT_TITLE = "Deal Comparison & Ranking"

# Deep evergreen + bright accent on warm neutrals: the institutional
# brokerage look (dark cover, one accent colour, hairline rules).
INK = "0B1F1B"
PRIMARY = "003B33"
PRIMARY_MID = "1C6B5C"
ACCENT = "2BD48D"
TINT = "EAF4F0"
STRIPE = "F5F8F7"
RULE = "D5DEDB"
MUTED = "5F6F6B"
NEGATIVE = "B42318"
WHITE = "FFFFFF"

DISCLAIMER = (
    "This report is a screening analysis prepared from the assumptions entered by the user. "
    "It is not an appraisal, a broker opinion of value, or investment advice. Projections are "
    "hypothetical, depend on the inputs shown in each deal profile, and are not guarantees of "
    "future performance. Market reference data (Treasury yields and survey cap-rate spreads) "
    "is third-party information transcribed from published sources and has not been "
    "independently verified."
)
