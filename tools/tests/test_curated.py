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
    assert {i["id"] for i in cur["include"]} >= {22888, 16609, 15366, 24425, 23735, 23769}
    assert len(cur["excl_merge"]) == 9


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
