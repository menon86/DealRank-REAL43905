import pytest

from app.config import Settings


@pytest.mark.parametrize(
    "url",
    ["postgres://u:p@h/db", "postgresql://u:p@h/db", "postgresql+psycopg://u:p@h/db"],
)
def test_database_url_is_normalized_to_psycopg3(url):
    assert Settings(DATABASE_URL=url).DATABASE_URL == "postgresql+psycopg://u:p@h/db"
