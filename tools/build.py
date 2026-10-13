"""FullBuff build: DB2 + site + Questie -> addon/FullBuff/Data/*.lua and a report."""
import argparse
import json
import sys
import urllib.request
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # python tools/build.py

from tools.curated import apply_curated, load_weights
from tools.emit_lua import emit_buffs, emit_slots, emit_sources, emit_weights, write_report
from tools.extract import extract_buffs
from tools.slots import apply_slots
from tools.sources.crafting import attach_craft_sources
from tools.sources.db2 import DB2_TABLES, default_get, fetch_tables, read_table
from tools.sources.forever_info import (apply_camping, crosscheck, fetch_site, parse_camping,
                                        parse_finder, unresolved_exclusives)
from tools.sources.questie import (apply_acquisition_levels, attach_sources, routeless_item_buffs,
                                   drop_unobtainable, load_area_map, load_questie)

ROOT = Path(__file__).resolve().parent.parent
ERA_BUILD = "1.15.9.70003"
DEFAULT_QUESTIE = Path(r"C:\Program Files (x86)\World of Warcraft\_classic_beta_"
                       r"\Interface\AddOns\QuestieDB\QuestieDB_Forever.toc")


def _http_text(url: str, headers: dict) -> str:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read().decode("utf-8")


def _load_site(cache: Path, offline: bool) -> tuple[str, dict]:
    site = cache / "site"
    camp_path, finder_path = site / "camping.html", site / "finder.json"
    if offline:
        if not (camp_path.exists() and finder_path.exists()):
            raise RuntimeError(f"--offline: site cache missing in {site}; run once online")
        return camp_path.read_text(encoding="utf-8"), json.loads(finder_path.read_text(encoding="utf-8"))
    camp_html, finder = fetch_site(_http_text)
    site.mkdir(parents=True, exist_ok=True)
    camp_path.write_text(camp_html, encoding="utf-8", newline="\n")
    finder_path.write_text(json.dumps(finder), encoding="utf-8", newline="\n")
    return camp_html, finder


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="build.py")
    ap.add_argument("--build", required=True, help="Forever DB2 build, e.g. 1.60.1.70338")
    ap.add_argument("--questie", type=Path, default=DEFAULT_QUESTIE, help="QuestieDB_Forever.toc path")
    ap.add_argument("--offline", action="store_true", help="use caches only, no network")
    ap.add_argument("--out", type=Path, default=ROOT / "addon" / "FullBuff" / "Data")
    ap.add_argument("--cache", type=Path, default=ROOT / "tools" / ".cache")
    ap.add_argument("--curated", type=Path, default=ROOT / "tools" / "curated.yaml")
    ap.add_argument("--era-build", default=ERA_BUILD)
    ap.add_argument("--report", type=Path, default=ROOT / "tools" / "out" / "build_report.md")
    args = ap.parse_args(argv)

    def db2_get(url: str) -> bytes:
        if args.offline:
            raise RuntimeError(f"--offline: DB2 cache incomplete, would fetch {url}")
        return default_get(url)

    try:
        paths = fetch_tables(args.build, DB2_TABLES, args.cache, db2_get)
        era_path = fetch_tables(args.era_build, ["SpellName"], args.cache, db2_get)["SpellName"]
        camp_html, finder = _load_site(args.cache, args.offline)
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    t = {name: read_table(p) for name, p in paths.items()}
    era_ids = {int(r["ID"]) for r in read_table(era_path)}

    cur = yaml.safe_load(args.curated.read_text(encoding="utf-8")) or {}
    q = load_questie(args.questie)
    amap = load_area_map(args.questie.parent, t["UiMapAssignment"])

    buffs, unclassified = extract_buffs(t, era_ids)
    warnings = apply_curated(buffs, unclassified, cur, q, amap)
    camps = parse_camping(camp_html)
    unmatched = apply_camping(buffs, unclassified, camps)
    # apply_camping categorises candidates in place; promote them out of the unclassified list.
    for b in [b for b in unclassified if b.cat]:
        unclassified.remove(b)
        buffs[b.id] = b
    slots, slot_warnings = apply_slots(buffs, cur)
    warnings += slot_warnings
    attach_sources(buffs, q, amap)
    attach_craft_sources(buffs, t)
    apply_acquisition_levels(buffs, q)  # after craft sources: a craft route means level 0
    curated_ids = {inc["id"] for inc in cur.get("include") or []}
    unobtainable = drop_unobtainable(buffs, q, curated_ids)
    weights = load_weights(cur)

    emit_buffs(buffs, args.out / "Buffs.lua")
    emit_sources(buffs, args.out / "Sources.lua")
    emit_weights(weights, args.out / "Weights.lua")
    emit_slots(slots, args.out / "Slots.lua")
    craft_count = sum(any(s.kind == "craft" for s in b.sources) for b in buffs.values())
    write_report(buffs, unclassified, warnings, unmatched,
                 crosscheck(buffs, parse_finder(finder)), args.report,
                 unresolved_exclusives(buffs, camps), craft_count, unobtainable,
                 routeless_item_buffs(buffs, q), slots)
    print(f"{len(buffs)} buffs, {len(unclassified)} unclassified, {len(unobtainable)} unobtainable, "
          f"{len(warnings)} warnings; "
          f"report: {args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
