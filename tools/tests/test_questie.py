import base64

import cbor2
import pytest

from tools.model import Buff, Source
from tools.sources.questie import QuestieData, area_to_uimap, attach_sources, load_area_map, load_questie


def b64(obj) -> str:
    return base64.b64encode(cbor2.dumps(obj)).decode()


def write_toc(tmp_path, lines):
    p = tmp_path / "q.toc"
    p.write_text("## Interface: 1\n## X-IDS: ~1~\n" + "\n".join(lines) + "\n", encoding="utf-8")
    return p


def buff(items):
    return Buff(id=1, name="b", cat=None, fx={}, dur=1, lvl=1, excl="", items=items,
                burst=False, new=False)


def test_decodes_scalar_and_table_fields(tmp_path):
    toc = write_toc(tmp_path, [
        f"## X-Item-5-S: {b64({1: b'Elixir', 7: 3, b'p': 64})}",
        f"## X-Item-5-14: {b64([100, 200])}",
        f"## X-Npc-100-S: {b64({1: b'Kelsey Yance', 14: b'Vendor'})}",
        f"## X-Npc-100-7: {b64({1429: [[27.2, 77.0]]})}",
        f"## X-Object-7-S: {b64({1: b'Chest'})}",
        f"## X-Object-7-4: {b64({1: [[1.0, 2.0]]})}",
        f"## X-Quest-9-S: {b64({1: b'A Quest'})}",
        f"## X-Quest-10-S: {b64([b'Dense', None, None, 30])}",
        f"## X-Npc-11-7: {b64([None, [[1.0, 2.0]]])}",
        "## X-Npc-IDS: ~3~",
        "## X-l10n-deDE-Item-5: abc",
    ])
    q = load_questie(toc)
    assert q.items[5]["name"] == "Elixir"
    assert q.items[5]["vendors"] == [100, 200]
    assert q.npcs[100]["name"] == "Kelsey Yance"
    assert q.npcs[100]["subName"] == "Vendor"
    assert q.npcs[100]["spawns"] == {1429: [[27.2, 77.0]]}
    assert q.objects[7]["spawns"] == {1: [[1.0, 2.0]]}
    assert q.npcs[11]["spawns"] == {2: [[1.0, 2.0]]}
    assert q.quests[9]["name"] == "A Quest"
    assert q.quests[10] == {"name": "Dense"}


def test_reassembles_chunked_value(tmp_path):
    raw = base64.b64encode(cbor2.dumps({12: [[1.5, 2.5], [3.5, 4.5]]})).decode()
    toc = write_toc(tmp_path, [
        "## X-Npc-3-7: ~2~",
        f"## X-Npc-3-7-2: {raw[10:]}",
        f"## X-Npc-3-7-1: {raw[:10]}",
        f"## X-Npc-3-S: {b64({1: b'Chunky'})}",
    ])
    q = load_questie(toc)
    assert q.npcs[3]["spawns"] == {12: [[1.5, 2.5], [3.5, 4.5]]}


def test_area_to_uimap_lowest_order():
    rows = [
        {"AreaID": "12", "UiMapID": "5", "OrderIndex": "3"},
        {"AreaID": "12", "UiMapID": "6", "OrderIndex": "1"},
        {"AreaID": "13", "UiMapID": "7", "OrderIndex": "0"},
    ]
    assert area_to_uimap(rows) == {12: 6, 13: 7}


def _vendor_data():
    return QuestieData(
        items={5: {"name": "Elixir", "vendors": [100]}},
        npcs={100: {"name": "Kelsey Yance", "spawns": {1429: [[27.2, 77.0]], 99: [[1, 1]]}}},
        objects={}, quests={},
    )


def test_attach_vendor_source_with_coords():
    b = buff([5])
    attach_sources({1: b}, _vendor_data(), {1429: 1434})
    assert b.sources == [Source(kind="vendor", name="Kelsey Yance", mapID=1434, x=0.272, y=0.77)]


def test_drop_sources_capped_at_five():
    q = QuestieData(
        items={5: {"name": "E", "npcDrops": [1], "objectDrops": [2], "questRewards": [9]}},
        npcs={1: {"name": "Mob", "spawns": {10: [[i, i] for i in range(1, 5)]}}},
        objects={2: {"name": "Chest", "spawns": {10: [[50, 50], [60, 60], [70, 70]]}}},
        quests={9: {"name": "Quest Name"}},
    )
    b = buff([5])
    attach_sources({1: b}, q, {10: 100})
    drops = [s for s in b.sources if s.kind == "drop"]
    assert len(drops) == 5
    assert drops[-1].note == "+2 more"
    quests = [s for s in b.sources if s.kind == "quest"]
    assert quests == [Source(kind="quest", name="Quest Name")]


def test_load_area_map_questie_wins(tmp_path):
    d = tmp_path / "support" / "Forever" / "Zones"
    d.mkdir(parents=True)
    (d / "areaIdToUiMapId.lua").write_text(
        "local x = 1\n"
        "Z.override = [[return {\n    [0] = 0, -- failsafe\n    [20] = 0, -- suppress\n"
        "    [30] = 999, -- alias\n}]]\n"
        "Z.base = [[return {\n    [10] = 111,\n    [20] = 222,\n    [30] = 333,\n}]]\n",
        encoding="utf-8")
    rows = [{"AreaID": "10", "UiMapID": "5", "OrderIndex": "0"},
            {"AreaID": "40", "UiMapID": "44", "OrderIndex": "0"}]
    assert load_area_map(tmp_path, rows) == {10: 111, 30: 999, 40: 44}


def test_invalid_points_skipped_before_first_and_cap():
    q = QuestieData(
        items={5: {"name": "E", "vendors": [100]}},
        npcs={100: {"name": "V", "spawns": {1: [[-1, -1], [10, 20]]}}},
        objects={}, quests={},
    )
    b = buff([5])
    attach_sources({1: b}, q, {1: 7})
    assert b.sources == [Source("vendor", "V", 7, 0.1, 0.2)]


def test_dedupe_and_idempotent():
    q = QuestieData(
        items={5: {"name": "A", "vendors": [100]}, 6: {"name": "B", "vendors": [100]}},
        npcs={100: {"name": "V", "spawns": {1: [[10, 20]]}}}, objects={}, quests={},
    )
    b = buff([5, 6])
    attach_sources({1: b}, q, {1: 7})
    attach_sources({1: b}, q, {1: 7})
    assert len(b.sources) == 1


def test_unnamed_entities_skipped():
    q = QuestieData(
        items={5: {"name": "A", "vendors": [100], "npcDrops": [101], "objectDrops": [2]}},
        npcs={100: {"spawns": {1: [[10, 20]]}}, 101: {"spawns": {1: [[10, 20]]}}},
        objects={2: {"spawns": {1: [[1, 2]]}}}, quests={},
    )
    b = buff([5])
    attach_sources({1: b}, q, {1: 7})
    assert b.sources == []


def test_missing_chunk_part_raises_clear_error(tmp_path):
    toc = write_toc(tmp_path, ["## X-Npc-3-7: ~3~", "## X-Npc-3-7-1: AAAA", "## X-Npc-3-7-3: AAAA"])
    with pytest.raises(ValueError, match=r"X-Npc-3-7 declares 3 parts but part 2 is missing"):
        load_questie(toc)


def test_undecodable_value_raises_clear_error(tmp_path):
    toc = write_toc(tmp_path, ["## X-Npc-3-7: !!!!"])
    with pytest.raises(ValueError, match="X-Npc-3-7"):
        load_questie(toc)
