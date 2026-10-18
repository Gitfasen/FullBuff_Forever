from pathlib import Path

from tools.model import Buff, Source
from tools.sources.forever_info import (CampBuff, apply_camping, crosscheck, fetch_site,
                                        parse_camping, parse_finder, unresolved_exclusives)

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


def test_boosted_stats_picks_exclusive_by_fx_overlap():
    kings = buff(1, "Blessing of Kings", "CLASS", excl="CLASS:kings", cls="PALADIN")
    kings.fx = {"STAT_PCT": 0.1}
    motw = buff(2, "Mark of the Wild", "CLASS", excl="CLASS:motw", cls="DRUID")
    motw.fx = {"STR": 12, "AGI": 12}
    pct = buff(10, "Boosted Stats")
    pct.fx = {"STAT_PCT": 0.05}
    flat = buff(11, "Boosted Stats")
    flat.fx = {"STR": 8, "AGI": 8}
    apply_camping({1: kings, 2: motw, 10: pct, 11: flat}, [], camps())
    assert pct.excl == "CLASS:kings"
    assert flat.excl == "CLASS:motw"
    assert {s.name for s in pct.sources} == {"Enchanted Lute", "Fish Bowl"}
    assert {s.name for s in flat.sources} == {"Enchanted Lute", "Fish Bowl"}


def test_unresolved_exclusive_reported():
    wisdom = buff(1, "Blessing of Wisdom", "CLASS", excl="CLASS:w", cls="PALADIN")
    result = unresolved_exclusives({1: wisdom}, camps())
    assert ("Boosted Mana Regeneration", "Blessing of Wisdom") not in result
    assert ("Boosted Attack Power", "Blessing of Might") in result


# --- fix A: camp buffs by level bands ---
STATS_FX = dict(AGI=13, ARMOR=308, INT=13, SPI=13, STA=13, STR=13)


def test_parse_camping_keeps_bands():
    lute = next(c for c in camps() if c.object_name == "Enchanted Lute")
    assert [b[0] for b in lute.bands] == [1, 10, 20, 60]
    assert "308 Armor" in lute.bands[-1][1]


def test_apply_camping_builds_level_band_ranks():
    motw = buff(1, "Mark of the Wild", "CLASS", excl="STATS", cls="DRUID")
    lute = buff(1230653, "Boosted Stats")
    lute.fx, lute.lvl = dict(STATS_FX), 0
    bowl = buff(1230098, "Boosted Stats")
    bowl.fx, bowl.lvl = {"STAT_PCT": 8}, 0
    apply_camping({1: motw, 1230653: lute, 1230098: bowl}, [], camps())
    assert [(r.spell, r.lvl) for r in lute.ranks] == [(1230653, 1), (1230653, 10), (1230653, 20),
                                                       (1230653, 60)]
    low, top = lute.ranks[0], lute.ranks[-1]
    assert low.fx == {"ARMOR": 28}
    assert lute.ranks[2].fx == dict(AGI=4, ARMOR=114, INT=4, SPI=4, STA=4, STR=4)
    assert top.fx == STATS_FX
    assert lute.lvl == 1 and lute.fx == STATS_FX
    # one band only: no ranks, unchanged
    assert bowl.ranks is None and bowl.lvl == 0
    # idempotent
    apply_camping({1: motw, 1230653: lute, 1230098: bowl}, [], camps())
    assert len(lute.ranks) == 4


def test_band_ranks_parse_by_phrase_and_ignore_cooldown():
    from tools.sources.forever_info import band_ranks, parse_band
    lute = next(c for c in camps() if c.object_name == "Enchanted Lute")
    assert parse_band(lute.bands[0][1]) == {"ARMOR": 28}  # "cooldown of 1 hrs" is not a stat
    assert parse_band(lute.bands[1][1]) == dict(ARMOR=71, STR=2, AGI=2, STA=2, INT=2, SPI=2)
    assert parse_band(lute.bands[-1][1])["ARMOR"] == 308  # resistances ignored
    ranks = band_ranks(7, STATS_FX, lute.bands)
    assert ranks[0].fx == {"ARMOR": 28}
    assert ranks[1].fx == dict(ARMOR=71, STR=2, AGI=2, STA=2, INT=2, SPI=2)
    assert ranks[-1].fx == STATS_FX


def test_band_phrases_other_stats():
    from tools.sources.forever_info import parse_band
    assert parse_band("regenerate 10 Mana every 5 sec ... cooldown of 1 hrs.") == {"MP5": 10}
    assert parse_band("gain 12 increased melee Attack Power, x") == {"AP": 12}
    assert parse_band("gain 6 increased Strength, x. cooldown of 1 hrs.") == {"STR": 6}
    assert parse_band("gain 8% increased stats, x") == {"STAT_PCT": 8}
    assert parse_band("gain 2% increased critical strike chance with all") == {"CRIT": 2,
                                                                              "SPELL_CRIT": 2}
