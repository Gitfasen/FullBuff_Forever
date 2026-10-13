"""Read QuestieDB_Forever.toc and attach item acquisition sources to buffs."""
import base64
import re
from dataclasses import dataclass, field
from pathlib import Path

import cbor2

from tools.model import Buff, Source

FIELD_NAMES = {
    "Item": {1: "name", 2: "npcDrops", 3: "objectDrops", 6: "questRewards", 14: "vendors"},
    "Npc": {1: "name", 7: "spawns", 14: "subName"},
    "Object": {1: "name", 4: "spawns"},
    "Quest": {1: "name"},
}

LINE_RE = re.compile(r"^## X-(Item|Npc|Object|Quest)-(\d+)-(S|\d+)(?:-(\d+))?: (\S+)\s*$")
CHUNK_RE = re.compile(r"^~(\d+)~$")
DROP_CAP = 5


@dataclass
class QuestieData:
    items: dict[int, dict] = field(default_factory=dict)
    npcs: dict[int, dict] = field(default_factory=dict)
    objects: dict[int, dict] = field(default_factory=dict)
    quests: dict[int, dict] = field(default_factory=dict)


def _decode(value: str, key: str = "?"):
    try:
        return cbor2.loads(base64.b64decode(value))
    except Exception as e:
        raise ValueError(f"QuestieDB: key {key} has an undecodable value ({e})") from e


def _text(v):
    return v.decode("utf-8", "replace") if isinstance(v, bytes) else v


def load_questie(toc_path: Path) -> QuestieData:
    # key -> raw value; chunk keys (<key>-<n>) are kept in `chunks`.
    values: dict[tuple[str, int, str], str] = {}
    chunks: dict[tuple[str, int, str, int], str] = {}
    with open(toc_path, encoding="utf-8") as f:
        for line in f:
            m = LINE_RE.match(line)
            if not m:
                continue
            entity, eid, fld, chunk, val = m.groups()
            if chunk is None:
                values[(entity, int(eid), fld)] = val
            else:
                chunks[(entity, int(eid), fld, int(chunk))] = val

    targets = {"Item": {}, "Npc": {}, "Object": {}, "Quest": {}}
    for (entity, eid, fld), val in values.items():
        key = f"X-{entity}-{eid}-{fld}"
        cm = CHUNK_RE.match(val)
        if cm:
            n = int(cm.group(1))
            parts = []
            for i in range(1, n + 1):
                part = chunks.get((entity, eid, fld, i))
                if part is None:
                    raise ValueError(f"QuestieDB: key {key} declares {n} parts but part {i} is missing")
                parts.append(part)
            val = "".join(parts)
        names = FIELD_NAMES[entity]
        row = targets[entity].setdefault(eid, {})
        if fld == "S":
            scalar = _decode(val, key)
            # Dense rows are positional lists (1-indexed, None = absent).
            pairs = enumerate(scalar, 1) if isinstance(scalar, list) else scalar.items()
            for idx, v in pairs:
                if isinstance(idx, int) and idx in names and v is not None:
                    row[names[idx]] = _text(v)
        elif int(fld) in names:
            decoded = _decode(val, key)
            if isinstance(decoded, list) and names[int(fld)] == "spawns":
                # Sparse zone-keyed table stored as a positional list (zoneId = index).
                decoded = {i: v for i, v in enumerate(decoded, 1) if v is not None}
            row[names[int(fld)]] = decoded
    return QuestieData(items=targets["Item"], npcs=targets["Npc"],
                       objects=targets["Object"], quests=targets["Quest"])


def area_to_uimap(rows: list[dict]) -> dict[int, int]:
    best: dict[int, tuple[int, int]] = {}
    for r in rows:
        area = int(r["AreaID"])
        if area == 0:
            continue
        order = int(r["OrderIndex"])
        if area not in best or order < best[area][0]:
            best[area] = (order, int(r["UiMapID"]))
    return {a: m for a, (_, m) in best.items()}


def _parse_lua_tables(text: str) -> list[dict[int, int]]:
    """Parse each `[[return { [id] = value, ... }]]` block into {id: value}."""
    tables = []
    for block in re.findall(r"\[\[return \{(.*?)\}\]\]", text, re.S):
        tables.append({int(a): int(v) for a, v in
                       re.findall(r"^\s*\[(\d+)\]\s*=\s*(\d+)", block, re.M)})
    return tables


def load_area_map(questie_dir: Path, uimap_rows: list[dict]) -> dict[int, int]:
    """AreaID -> UiMapID. Questie's tables win over UiMapAssignment; override value 0 suppresses."""
    amap = area_to_uimap(uimap_rows)
    path = Path(questie_dir) / "support" / "Forever" / "Zones" / "areaIdToUiMapId.lua"
    tables = _parse_lua_tables(path.read_text(encoding="utf-8"))
    if len(tables) != 2:
        raise ValueError(f"QuestieDB: expected 2 tables in {path}, found {len(tables)}")
    override, base = tables
    amap.update(base)
    for area, ui in override.items():
        if ui == 0:
            amap.pop(area, None)
        else:
            amap[area] = ui
    return amap


def _locations(spawns, amap, first_per_zone=False):
    out = []
    for zone, points in (spawns or {}).items():
        map_id = amap.get(int(zone))
        if map_id is None:
            continue
        valid = [pt for pt in points if 0 <= pt[0] <= 100 and 0 <= pt[1] <= 100]
        for pt in valid[:1] if first_per_zone else valid:
            out.append((map_id, round(pt[0] / 100, 4), round(pt[1] / 100, 4)))
    return out


KEEP_SOURCE_KINDS = {"craft", "camping"}


def drop_unobtainable(buffs: dict[int, Buff], q: QuestieData, keep: set[int]) -> list[Buff]:
    """Remove item buffs whose items are all absent from QuestieDB_Forever and that have no
    craft/camping source and are not curated (`keep`); return them, sorted by id."""
    dropped = []
    for bid in sorted(buffs):
        b = buffs[bid]
        if not b.items or bid in keep or any(i in q.items for i in b.items):
            continue
        if any(s.kind in KEEP_SOURCE_KINDS for s in b.sources):
            continue
        dropped.append(buffs.pop(bid))
    return dropped


def attach_sources(buffs: dict[int, Buff], q: QuestieData, amap: dict[int, int]) -> None:
    for buff in buffs.values():
        seen = {(s.kind, s.name, s.mapID, s.x, s.y) for s in buff.sources}

        def add(src: Source) -> None:
            k = (src.kind, src.name, src.mapID, src.x, src.y)
            if k not in seen:
                seen.add(k)
                buff.sources.append(src)

        for item_id in buff.items:
            item = q.items.get(item_id)
            if not item:
                continue
            for npc_id in item.get("vendors", []):
                npc = q.npcs.get(npc_id)
                if not npc or not npc.get("name"):
                    continue
                for map_id, x, y in _locations(npc.get("spawns"), amap, first_per_zone=True):
                    add(Source("vendor", npc["name"], map_id, x, y))

            drops: list[Source] = []
            dseen: set[tuple] = set()
            for ids, table in ((item.get("npcDrops", []), q.npcs),
                               (item.get("objectDrops", []), q.objects)):
                for eid in ids:
                    ent = table.get(eid)
                    if not ent or not ent.get("name"):
                        continue
                    for map_id, x, y in _locations(ent.get("spawns"), amap):
                        if (ent["name"], map_id, x, y) not in dseen:
                            dseen.add((ent["name"], map_id, x, y))
                            drops.append(Source("drop", ent["name"], map_id, x, y))
            if len(drops) > DROP_CAP:
                extra = len(drops) - DROP_CAP
                drops = drops[:DROP_CAP]
                drops[-1].note = f"+{extra} more"
            for d in drops:
                add(d)

            for qid in item.get("questRewards", []):
                quest = q.quests.get(qid)
                if quest and quest.get("name"):
                    add(Source("quest", quest["name"]))
