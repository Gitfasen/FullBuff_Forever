"""Apply hand-curated overrides (includes, excludes, field overrides, exclusive groups, weights)."""
import copy
from dataclasses import fields

from tools.model import Buff, Source
from tools.sources.questie import QuestieData, _locations

CLASSES = ["WARRIOR", "PALADIN", "HUNTER", "ROGUE", "PRIEST", "SHAMAN", "MAGE", "WARLOCK", "DRUID"]
STAT_KEYS = {"STR", "AGI", "STA", "INT", "SPI", "AP", "RAP", "SPELL_DMG", "HEAL", "ARMOR", "HP",
             "MANA", "MP5", "HP5", "CRIT", "SPELL_CRIT", "HIT", "SPELL_HIT", "STAT_PCT", "ARMOR_PCT"}
BUFF_FIELDS = {f.name for f in fields(Buff)} - {"id"}


def _resolve_sources(spec: dict, q: QuestieData, amap: dict[int, int], spell: int,
                     warnings: list[str]) -> list[Source]:
    kind = spec["kind"]
    note = spec.get("note")
    given = spec.get("name")
    if kind in ("npc", "object") and spec.get(kind) is not None:
        eid = spec[kind]
        ent = (q.npcs if kind == "npc" else q.objects).get(eid)
        name = given or (ent or {}).get("name") or f"{kind} {eid}"
        if ent and ent.get("name"):
            name = ent["name"]
        locs = _locations(ent.get("spawns"), amap) if ent else []
        if locs:
            return [Source(kind, name, m, x, y, note) for m, x, y in locs]
        why = "not found in QuestieDB" if not ent else "has no mappable spawn"
        warnings.append(f"curated include {spell}: {kind} {eid} {why}")
        return [Source(kind, name, note=note)]
    return [Source(kind, given or "", note=note)]


def apply_curated(buffs: dict[int, Buff], unclassified: list[Buff], cur: dict,
                  q: QuestieData, amap: dict[int, int]) -> list[str]:
    warnings: list[str] = []

    for inc in cur.get("include") or []:
        sid = inc["id"]
        found = next((b for b in unclassified if b.id == sid), None)
        if found is None:
            if sid not in buffs:
                warnings.append(f"curated include {sid}: spell not found in unclassified")
            continue
        unclassified.remove(found)
        found.cat = inc["cat"]
        found.excl = f"{found.cat}:{found.name}"
        for spec in inc.get("sources") or []:
            found.sources.extend(_resolve_sources(spec, q, amap, sid, warnings))
        buffs[sid] = found

    for sid in cur.get("exclude") or []:
        hit = buffs.pop(sid, None) is not None
        n = len(unclassified)
        unclassified[:] = [b for b in unclassified if b.id != sid]
        if not hit and len(unclassified) == n:
            warnings.append(f"curated exclude {sid}: spell not found")

    for sid, changes in (cur.get("override") or {}).items():
        buff = buffs.get(sid) or next((b for b in unclassified if b.id == sid), None)
        if buff is None:
            warnings.append(f"curated override {sid}: spell not found")
            continue
        for key, value in changes.items():
            if key not in BUFF_FIELDS:
                warnings.append(f"curated override {sid}: unknown field {key}")
                continue
            setattr(buff, key, copy.deepcopy(value))  # never alias/mutate shared dicts

    by_name: dict[str, list[Buff]] = {}
    for b in buffs.values():
        by_name.setdefault(b.name, []).append(b)
    for group in cur.get("excl_merge") or []:
        members = []
        for name in group:
            if name in by_name:
                members.append(by_name[name])
            else:
                warnings.append(f"curated excl_merge: buff '{name}' not found")
        if not members:
            continue
        key = members[0][0].excl
        for lst in members:
            for b in lst:
                b.excl = key
    return warnings


def load_weights(cur: dict) -> dict[str, list[dict[str, float]]]:
    raw = cur.get("weights") or {}
    if set(raw) != set(CLASSES):
        raise ValueError(f"weights must cover exactly {CLASSES}, got {sorted(raw)}")
    out: dict[str, list[dict[str, float]]] = {}
    for cls in CLASSES:
        specs = raw[cls]
        if not isinstance(specs, list) or len(specs) != 3:
            raise ValueError(f"weights[{cls}] must be a list of 3 spec maps")
        for spec in specs:
            bad = set(spec) - STAT_KEYS
            if bad:
                raise ValueError(f"weights[{cls}] has unknown stat keys {sorted(bad)}")
        out[cls] = [{k: float(v) for k, v in s.items()} for s in specs]
    return out
