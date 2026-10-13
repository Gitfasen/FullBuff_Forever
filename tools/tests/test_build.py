import base64
import csv
import shutil
from pathlib import Path

import cbor2
import lupa

from tools.build import ERA_BUILD, main
from tools.sources.db2 import DB2_TABLES

FIX = Path(__file__).parent / "fixtures"
BUILD = "1.60.1.70338"

COLUMNS = {
    "SpellName": ["ID", "Name_lang"],
    "SpellEffect": ["SpellID", "Effect", "EffectAura", "EffectBasePointsF", "EffectMiscValue_0",
                    "EffectTriggerSpell", "EffectItemType"],
    "SpellMisc": ["SpellID", "DifficultyID", "DurationIndex"],
    "SpellDuration": ["ID", "Duration"],
    "ItemEffect": ["ID", "TriggerType", "SpellID"],
    "ItemXItemEffect": ["ItemEffectID", "ItemID"],
    "Item": ["ID", "ClassID", "SubclassID", "InventoryType"],
    "ItemSparse": ["ID", "RequiredLevel", "RequiredSkillRank"],
    "UiMapAssignment": ["AreaID", "OrderIndex", "UiMapID"],
    "SkillLine": ["ID", "DisplayName_lang"],
}
ROWS = {
    "SpellName": [[17538, "Elixir of the Mongoose"], [900001, "Boosted Mana Regeneration"]],
    "SpellEffect": [[17538, 6, 29, 25, 1, 0, 0], [17538, 6, 290, 2, 0, 0, 0],
                    [900001, 6, 29, 5, 1, 0, 0]],
    "SpellMisc": [[17538, 0, 1], [900001, 0, 1]],
    "SpellDuration": [[1, 3600000]],
    "ItemEffect": [[1, 0, 17538]],
    "ItemXItemEffect": [[1, 13452]],
    "Item": [[13452, 0, 2, 0]],
    "ItemSparse": [[13452, 46, 0]],
    "UiMapAssignment": [[1429, 0, 37]],
}


def write_csv(path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def b64(obj):
    return base64.b64encode(cbor2.dumps(obj)).decode()


def setup(tmp_path):
    cache = tmp_path / "cache"
    for table in DB2_TABLES:
        write_csv(cache / BUILD / f"{table}.csv", COLUMNS.get(table, ["ID"]), ROWS.get(table, []))
    write_csv(cache / ERA_BUILD / "SpellName.csv", ["ID", "Name_lang"], [[17538, "Elixir of the Mongoose"]])
    site = cache / "site"
    site.mkdir()
    shutil.copy(FIX / "camping_min.html", site / "camping.html")
    shutil.copy(FIX / "finder_min.json", site / "finder.json")

    qdir = tmp_path / "QuestieDB"
    zones = qdir / "support" / "Forever" / "Zones"
    zones.mkdir(parents=True)
    (zones / "areaIdToUiMapId.lua").write_text(
        "local override = [[return {\n}]]\nlocal base = [[return {\n  [1429] = 37,\n}]]\n", encoding="utf-8")
    toc = qdir / "QuestieDB_Forever.toc"
    toc.write_text("\n".join([
        "## Interface: 1",
        f"## X-Item-13452-S: {b64({1: b'Elixir of the Mongoose'})}",
        f"## X-Item-13452-14: {b64([100])}",
        f"## X-Npc-100-S: {b64({1: b'Kelsey Yance'})}",
        f"## X-Npc-100-7: {b64({1429: [[27.2, 77.0]]})}",
    ]) + "\n", encoding="utf-8")
    return cache, toc


def test_build_offline_end_to_end(tmp_path):
    cache, toc = setup(tmp_path)
    out, report = tmp_path / "out", tmp_path / "report.md"
    rc = main(["--build", BUILD, "--offline", "--questie", str(toc), "--cache", str(cache),
               "--out", str(out), "--report", str(report)])
    assert rc == 0
    for name in ("Buffs.lua", "Sources.lua", "Weights.lua"):
        assert (out / name).exists()
    assert report.exists() and "CAMPING: 1" in report.read_text(encoding="utf-8")

    from lupa.lua51 import LuaRuntime
    lua = LuaRuntime()
    ns = lua.eval("{}")
    load = lua.eval("function(src, ns) return loadstring(src)(nil, ns) end")
    for name in ("Buffs.lua", "Sources.lua", "Weights.lua"):
        load((out / name).read_text(encoding="utf-8"), ns)
    assert ns.Buffs[17538].fx.AGI == 25
    camp = ns.Buffs[900001]  # unclassified candidate matched by the camping page -> promoted
    assert camp.cat == "CAMPING"
    assert ns.Sources[900001][1].kind == "camping"
    src = ns.Sources[17538][1]
    assert (src.kind, src.name, src.mapID, src.x, src.y) == ("vendor", "Kelsey Yance", 37, 0.272, 0.77)
    assert ns.Weights.WARRIOR[1] is not None


def test_build_offline_refuses_missing_cache(tmp_path, capsys):
    cache, toc = setup(tmp_path)
    shutil.rmtree(cache / "site")
    rc = main(["--build", BUILD, "--offline", "--questie", str(toc), "--cache", str(cache),
               "--out", str(tmp_path / "o"), "--report", str(tmp_path / "r.md")])
    assert rc == 1 and "site cache missing" in capsys.readouterr().err
