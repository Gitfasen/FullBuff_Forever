from pathlib import Path

import pytest
import yaml

from tools.curated import apply_curated, load_weights
from tools.model import Buff
from tools.sources.questie import QuestieData

CURATED = Path(__file__).resolve().parents[1] / "curated.yaml"


def mk(id, name, cat=None, **kw):
    return Buff(id=id, name=name, cat=cat, fx={"STR": 5}, dur=3600, lvl=0,
                excl=f"{cat}:{name}", items=[], burst=False, new=False, **kw)


def qdata():
    return QuestieData(
        npcs={14392: {"name": "Overlord Runthak", "spawns": {1519: [[50.0, 40.0], [150.0, 3.0]]}}},
        objects={164886: {"name": "Songflower", "spawns": {9999: [[1.0, 2.0]]}}},
    )


AMAP = {1519: 1453}


def test_include_moves_world_buff_with_npc_coords():
    un = [mk(22888, "Rallying Cry")]
    buffs = {}
    cur = {"include": [{"id": 22888, "cat": "WORLD",
                        "sources": [{"kind": "npc", "npc": 14392}]}]}
    warns = apply_curated(buffs, un, cur, qdata(), AMAP)
    b = buffs[22888]
    assert un == [] and warns == []
    assert b.cat == "WORLD" and b.excl == "WORLD:Rallying Cry"
    assert [(s.kind, s.name, s.mapID, s.x, s.y) for s in b.sources] == \
        [("npc", "Overlord Runthak", 1453, 0.5, 0.4)]


def test_include_unmappable_and_missing_sources_warn():
    un = [mk(1, "A"), mk(2, "B")]
    buffs = {}
    cur = {"include": [
        {"id": 1, "cat": "WORLD", "sources": [{"kind": "object", "object": 164886},
                                              {"kind": "npc", "npc": 555, "name": "Ghost"}]},
        {"id": 2, "cat": "WORLD", "sources": [{"kind": "npc", "name": "Sayge", "note": "x"}]}]}
    warns = apply_curated(buffs, un, cur, qdata(), AMAP)
    s1 = buffs[1].sources
    assert [(s.kind, s.name, s.mapID) for s in s1] == [("object", "Songflower", None), ("npc", "Ghost", None)]
    assert len(warns) == 2
    assert buffs[2].sources[0].name == "Sayge" and buffs[2].sources[0].note == "x"


def test_missing_include_id_warns():
    buffs = {}
    warns = apply_curated(buffs, [], {"include": [{"id": 77, "cat": "WORLD", "sources": []}]},
                          qdata(), AMAP)
    assert buffs == {} and len(warns) == 1 and "77" in warns[0]


def test_exclude_removes():
    buffs = {5: mk(5, "X", "FOOD")}
    un = [mk(6, "Y")]
    apply_curated(buffs, un, {"exclude": [5, 6]}, qdata(), AMAP)
    assert buffs == {} and un == []


def test_override_sets_field():
    shared = {"STR": 5}
    b = mk(5, "X", "FOOD")
    b.fx = shared
    buffs = {5: b}
    warns = apply_curated(buffs, [], {"override": {5: {"dur": 99, "fx": {"AGI": 3}},
                                                   6: {"dur": 1}, }}, qdata(), AMAP)
    assert b.dur == 99 and b.fx == {"AGI": 3} and shared == {"STR": 5}
    assert len(warns) == 1


def test_excl_merge_sets_shared_group():
    a, g = mk(1, "Power Word: Fortitude", "CLASS"), mk(2, "Prayer of Fortitude", "CLASS")
    buffs = {1: a, 2: g}
    warns = apply_curated(buffs, [], {"excl_merge": [["Power Word: Fortitude", "Prayer of Fortitude", "Nope"]]},
                          qdata(), AMAP)
    assert a.excl == g.excl == "CLASS:Power Word: Fortitude"
    assert len(warns) == 1 and "Nope" in warns[0]


def test_weights_nine_classes_three_specs():
    cur = yaml.safe_load(CURATED.read_text(encoding="utf-8"))
    w = load_weights(cur)
    assert len(w) == 9 and all(len(v) == 3 for v in w.values())
    assert w["WARRIOR"][2]["HP"] == 0.5


def test_weights_reject_bad_shape():
    with pytest.raises(ValueError):
        load_weights({"weights": {"WARRIOR": [{"BOGUS": 1}] * 3}})
    cur = yaml.safe_load(CURATED.read_text(encoding="utf-8"))
    cur["weights"]["MAGE"] = cur["weights"]["MAGE"][:2]
    with pytest.raises(ValueError):
        load_weights(cur)
    del cur["weights"]["MAGE"]
    with pytest.raises(ValueError):
        load_weights(cur)


def test_curated_yaml_loads():
    cur = yaml.safe_load(CURATED.read_text(encoding="utf-8"))
    # Forever's live world-buff ids (the vanilla ids are dummy auras in Forever DB2)
    assert {i["id"] for i in cur["include"]} >= {1304452, 1304594, 1304690, 24425, 1304751, 1304759, 1304771}
    assert not {i["id"] for i in cur["include"]} & {22888, 16609, 15366, 22817, 22818, 22820}
    assert len(cur["excl_merge"]) == 15
    assert ["Rat Familiar", "Frog Familiar", "Cat Familiar"] in cur["excl_merge"]
    assert {1304753, 1304782, 1304780, 1304778, 1304772, 1304775} <= {i["id"] for i in cur["include"]}


def test_include_synthesizes_buff_without_spell():
    buffs = {}
    cur = {"include": [{"id": 900001, "cat": "WORLD", "name": "Made Up Blessing",
                        "fx": {"SPI": 10, "MP5": 4}, "dur": 7200, "lvl": 50,
                        "sources": [{"kind": "npc", "npc": 14392}]}]}
    warns = apply_curated(buffs, [], cur, qdata(), AMAP)
    b = buffs[900001]
    assert warns == []
    assert (b.name, b.cat, b.fx, b.dur, b.lvl, b.excl, b.burst, b.items) == \
        ("Made Up Blessing", "WORLD", {"SPI": 10.0, "MP5": 4.0}, 7200, 50, "WORLD:Made Up Blessing", False, [])
    assert b.sources[0].name == "Overlord Runthak"


def test_include_synthesized_short_buff_is_burst_and_lvl_defaults_to_zero():
    buffs = {}
    apply_curated(buffs, [], {"include": [{"id": 5, "cat": "WORLD", "name": "Short", "fx": {"AP": 1},
                                           "dur": 30}]}, qdata(), AMAP)
    assert buffs[5].burst is True and buffs[5].lvl == 0


def test_include_rejects_unknown_category_and_stat_keys():
    un = [mk(1, "A")]
    buffs = {}
    cur = {"include": [{"id": 1, "cat": "WORLDS"},
                       {"id": 2, "cat": "WORLD", "name": "B", "fx": {"BOGUS": 1}, "dur": 60}]}
    warns = apply_curated(buffs, un, cur, qdata(), AMAP)
    assert buffs == {} and [b.id for b in un] == [1]
    assert len(warns) == 2 and "WORLDS" in warns[0] and "BOGUS" in warns[1]


def test_override_rejects_unknown_category_and_stat_keys():
    b = mk(5, "X", "FOOD")
    buffs = {5: b}
    warns = apply_curated(buffs, [], {"override": {5: {"cat": "SNACK", "fx": {"NOPE": 2}, "dur": 7}}},
                          qdata(), AMAP)
    assert (b.cat, b.fx, b.dur) == ("FOOD", {"STR": 5}, 7)
    assert len(warns) == 2 and "SNACK" in warns[0] and "NOPE" in warns[1]


def mkfx(id, name, cat, fx, **kw):
    b = mk(id, name, cat, **kw)
    b.fx = fx
    return b


def test_stacking_groups_for_exclusive_consumables():
    buffs = {b.id: b for b in [
        mkfx(1, "Flask of the Titans", "FLASK", {"HP": 1200}),
        mkfx(2, "Supreme Power", "FLASK", {"SPELL_DMG": 150}),
        mkfx(3, "Wizard Oil", "WEAPON", {"SPELL_DMG": 24, "HEAL": 24}),
        mkfx(4, "Rockbiter Weapon", "CLASS", {"AP": 50}, cls="SHAMAN", enchant=1664, self_only=True),
        mkfx(5, "Well Fed", "FOOD", {"STA": 10}),
        mkfx(6, "Kreeg's Stout Beatdown", "FOOD", {"SPI": 25}),
        mkfx(7, "Elixir of the Mongoose", "ELIXIR", {"AGI": 25, "CRIT": 2, "SPELL_CRIT": 2}),
        mkfx(8, "Elixir of the Sages", "ELIXIR", {"INT": 18, "SPI": 18}),
        mkfx(9, "Elixir of the Phalanx", "ELIXIR", {"ARMOR": 500, "HP": 400}),
        mkfx(10, "Greater Mageblood Elixir", "ELIXIR", {"MP5": 20}),
        mkfx(11, "Intellect", "SCROLL", {"INT": 16}),
        mkfx(12, "Arcane Intellect", "CLASS", {"INT": 31}, cls="MAGE"),
        mkfx(13, "Songflower Serenade", "WORLD", {"STR": 15, "CRIT": 5}),
        mkfx(14, "Sharpen", "WEAPON", {"CRIT": 2}),
    ]}
    assert apply_curated(buffs, [], {}, qdata(), AMAP) == []
    got = {i: b.excl for i, b in buffs.items()}
    assert got == {1: "FLASK", 2: "FLASK", 3: "WEAPON", 4: "WEAPON", 5: "FOOD:Well Fed",
                   6: "FOOD:Well Fed", 7: "ELIXIR:AGI", 8: "ELIXIR:INT", 9: "ELIXIR:ARMOR",
                   10: "ELIXIR:MP5", 11: "SCROLL:INT", 12: "CLASS:Arcane Intellect",
                   13: "WORLD:Songflower Serenade", 14: "WEAPON"}


def test_excl_merge_overrides_stacking_group_with_own_key():
    buffs = {b.id: b for b in [
        mkfx(1, "Rat Familiar", "SCROLL", {"INT": 2}), mkfx(2, "Cat Familiar", "SCROLL", {"INT": 12}),
        mkfx(3, "Intellect", "SCROLL", {"INT": 16}),
        mkfx(4, "Rumsey Rum Black Label", "FOOD", {"STA": 15}), mkfx(5, "Well Fed", "FOOD", {"STA": 10}),
        mkfx(6, "Spirit of Zanza", "ELIXIR", {"SPI": 50, "STA": 50}),
    ]}
    cur = {"excl_merge": [["Rat Familiar", "Cat Familiar"], ["Rumsey Rum Black Label"], ["Spirit of Zanza"]]}
    assert apply_curated(buffs, [], cur, qdata(), AMAP) == []
    got = {i: b.excl for i, b in buffs.items()}
    assert got == {1: "SCROLL:Rat Familiar", 2: "SCROLL:Rat Familiar", 3: "SCROLL:INT",
                   4: "FOOD:Rumsey Rum Black Label", 5: "FOOD:Well Fed", 6: "ELIXIR:Spirit of Zanza"}


def test_override_excl_beats_stacking_group():
    buffs = {1: mkfx(1, "Odd Elixir", "ELIXIR", {"STR": 5})}
    apply_curated(buffs, [], {"override": {1: {"excl": "ELIXIR:odd"}}}, qdata(), AMAP)
    assert buffs[1].excl == "ELIXIR:odd"
