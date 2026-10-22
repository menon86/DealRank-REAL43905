"""Brand palette and boilerplate shared by the PDF and PPTX exports, so the
two formats read as one product. Hex strings (no '#') because reportlab and
python-pptx each wrap them in their own colour type.
"""

NAME = "DealRank"
REPORT_TITLE = "Deal Comparison & Ranking"

# The web app's brand colours (frontend/src/theme.css): ink navy, teal and
# brass on cool neutrals, so a report looks like it came from the product.
INK = "0C1727"
PRIMARY = "0C1727"
PRIMARY_MID = "0B6B63"
ACCENT = "B3812A"
TINT = "EEF1F5"
STRIPE = "F6F8FA"
HIGHLIGHT = "FBF3E2"
RULE = "DCE2EA"
MUTED = "5A677A"
NEGATIVE = "B42318"
WHITE = "FFFFFF"

# Light text for use on a PRIMARY (dark) background.
ON_DARK = "C5CFDD"

DISCLAIMER = (
    "This report is a screening analysis prepared from the assumptions entered by the user. "
    "It is not an appraisal, a broker opinion of value, or investment advice. Projections are "
    "hypothetical, depend on the inputs shown in each deal profile, and are not guarantees of "
    "future performance. Market reference data (Treasury yields and survey cap-rate spreads) "
    "is third-party information transcribed from published sources and has not been "
    "independently verified."
)
