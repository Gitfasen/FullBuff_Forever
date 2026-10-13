from pathlib import Path

from tools.model import Buff, Source
from tools.sources.forever_info import (CampBuff, apply_camping, crosscheck, fetch_site,
                                        parse_camping, parse_finder)

FIX = Path(__file__).parent / "fixtures"


def buff(id, name, cat=None, excl=None, cls=None, items=()):
    return Buff(id=id, name=name, cat=cat, fx={}, dur=1, lvl=1,
                excl=excl if excl is not None else f"{cat}:{name}", items=list(items),
                burst=False, new=False, cls=cls)


def camps():
    return parse_camping((FIX / "camping_min.html").read_text(encoding="utf-8"))


def test_parse_camping_mana_well():
    assert CampBuff("Boosted Mana Regeneration", "Mana Well", "alchemy", 20,
                    "Blessing of Wisdom") in camps()


def test_parse_camping_skips_null_buff_and_dedupes():
    result = camps()
    assert all(c.buff_name for c in result)
    assert [c.object_name for c in result].count("Faction Banner") == 1
    assert "Fermenter" not in [c.object_name for c in result]


def test_apply_camping_shares_class_excl():
    wisdom = buff(1, "Blessing of Wisdom", "CLASS", excl="CLASS:wisdom-curated", cls="PALADIN")
    r1 = buff(10, "Boosted Mana Regeneration")
    r2 = buff(11, "Boosted Mana Regeneration")
    buffs = {1: wisdom, 10: r1}
    unclassified = [r2]
    unmatched = apply_camping(buffs, unclassified, camps())
    for b in (r1, r2):
        assert b.cat == "CAMPING"
        assert b.excl == "CLASS:wisdom-curated"
        assert b.sources == [Source(kind="camping", name="Mana Well", note="alchemy 20")]
    assert "Boosted Mana Regeneration" not in unmatched
    # idempotent
    apply_camping(buffs, unclassified, camps())
    assert len(r1.sources) == 1


def test_apply_camping_without_class_buff_keeps_excl():
    b = buff(10, "Boosted Mana Regeneration")
    apply_camping({10: b}, [], camps())
    assert b.cat == "CAMPING" and b.excl == "CAMPING:Boosted Mana Regeneration"


def test_unmatched_camp_reported():
    b = buff(10, "Boosted Mana Regeneration")
    unmatched = apply_camping({10: b}, [], camps())
    assert "Boosted Attack Power" in unmatched and "Boosted Spirit" in unmatched
    assert "Boosted Mana Regeneration" not in unmatched


def test_crosscheck_reports_missing_item():
    import json
    finder = parse_finder(json.loads((FIX / "finder_min.json").read_text()))
    assert finder[3825].startswith("Use: Increases")
    have = buff(1, "Fort", "ELIXIR", items=[3825])
    assert crosscheck({1: have}, finder) == [268880]


def test_fetch_site_one_get_per_url():
    calls = []
    pages = {
        "https://wowclassicforever.info/camping/": "CAMP",
        "https://wowclassicforever.info/consumables/":
            '<a href="/assets/consumables/finder-en-tips-aaa.json"></a>'
            '<script src="/assets/consumables/finder-en-73e85eb348.json"></script>',
        "https://wowclassicforever.info/assets/consumables/finder-en-73e85eb348.json":
            '{"items": []}',
    }

    def http_get(url, headers):
        calls.append((url, headers))
        return pages[url]

    html, data = fetch_site(http_get)
    assert html == "CAMP" and data == {"items": []}
    assert len(calls) == 3 and len({u for u, _ in calls}) == 3
    assert all(h["User-Agent"] == "FullBuff-build" for _, h in calls)
