from pathlib import Path

from tools.sources.db2 import DB2_TABLES, fetch_tables, read_table

FIXTURES = Path(__file__).parent / "fixtures"
BUILD = "1.60.1.70338"


def test_fetch_builds_wago_url(tmp_path):
    urls = []

    def fake_get(url):
        urls.append(url)
        return b"ID,Name_lang\n1,Foo\n"

    result = fetch_tables(BUILD, ["SpellName"], tmp_path, http_get=fake_get)
    assert urls == ["https://wago.tools/db2/SpellName/csv?build=1.60.1.70338"]
    assert result["SpellName"] == tmp_path / BUILD / "SpellName.csv"
    assert result["SpellName"].read_bytes() == b"ID,Name_lang\n1,Foo\n"


def test_fetch_uses_cache(tmp_path):
    calls = []

    def fake_get(url):
        calls.append(url)
        return b"ID\n1\n"

    fetch_tables(BUILD, ["SpellName"], tmp_path, http_get=fake_get)
    fetch_tables(BUILD, ["SpellName"], tmp_path, http_get=fake_get)
    assert len(calls) == 1


def test_read_table_returns_dicts():
    rows = read_table(FIXTURES / "SpellName.csv")
    assert rows == [{"ID": "1", "Name_lang": "Foo"}]


def test_db2_tables_list():
    assert len(DB2_TABLES) == 16
    assert DB2_TABLES[0] == "SpellName"
    assert DB2_TABLES[-1] == "SkillLine"
