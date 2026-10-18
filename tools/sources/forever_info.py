"""Camping buffs and a consumables cross-check from wowclassicforever.info."""
import json
import re
from dataclasses import dataclass, field

from tools.model import STAT_KEYS, Buff, Rank, Source

BASE = "https://wowclassicforever.info"
USER_AGENT = "FullBuff-build"
SCRIPT_RE = re.compile(r'<script type="application/json"[^>]*>(.*?)</script>', re.S)
# "finder-en-<hash>.json" only; "finder-en-tips-<hash>.json" is a different file.
FINDER_RE = re.compile(r"/assets/consumables/finder-en-[0-9a-f]+\.json")
INCREASES_RE = re.compile(r"increase[sd]", re.I)
NUMBER_RE = re.compile(r"\d+")
# fx keys given in percent: kept at the top band's value when no band number matches.
PCT_KEYS = frozenset(k for k in STAT_KEYS if k.endswith("_PCT")) | {"CRIT", "SPELL_CRIT", "HIT",
                                                                     "SPELL_HIT"}


@dataclass(frozen=True)
class CampBuff:
    buff_name: str
    object_name: str
    profession: str
    skill: int
    exclusive_with: str | None
    # ((level, text), ...) sorted by level: the camp object's description per level band.
    bands: tuple[tuple[int, str], ...] = field(default=(), compare=False)


def parse_camping(html: str) -> list[CampBuff]:
    result: list[CampBuff] = []
    seen: set[CampBuff] = set()
    for m in SCRIPT_RE.finditer(html):
        try:
            data = json.loads(m.group(1))
        except ValueError:
            continue
        if not isinstance(data, dict) or "objects" not in data:
            continue
        for obj in data["objects"]:
            buff = obj.get("buff")
            if not buff or not buff.get("name"):
                continue
            exclusive = obj.get("exclusive")
            bands = tuple(sorted((int(b[0]), str(b[1])) for b in obj.get("bands") or []
                                 if isinstance(b, list) and len(b) == 2))
            camp = CampBuff(buff["name"], obj["name"], obj["profession"], int(obj["skill"]),
                            exclusive.get("name") if exclusive else None, bands)
            if camp not in seen:
                seen.add(camp)
                result.append(camp)
    return result


def _numbers(text: str) -> list[int]:
    return [int(n) for n in NUMBER_RE.findall(text)]


def _positions(fx: dict[str, float], top_text: str) -> dict[str, int]:
    """fx key -> index of its value among the top band's numbers (keys not found are left out)."""
    nums = _numbers(top_text)
    return {k: nums.index(v) for k, v in fx.items() if v in nums}


def band_ranks(spell: int, fx: dict[str, float], bands, pct_keys=PCT_KEYS) -> list[Rank]:
    """One rank per level band (same spell id). fx is the top band's: each key takes the number
    at the position its top value has in the top band's text. A key not found is skipped, except
    percent keys, which keep the top value. A band too short for a position skips that key."""
    pos = _positions(fx, bands[-1][1])
    ranks = []
    for lvl, text in bands:
        nums = _numbers(text)
        rfx = {}
        for k, v in fx.items():
            if k in pos:
                if pos[k] < len(nums):
                    rfx[k] = nums[pos[k]]
            elif k in pct_keys:
                rfx[k] = v
        ranks.append(Rank(spell=spell, lvl=lvl, fx=rfx))
    return ranks


def _apply_bands(b: Buff, group: list[CampBuff]) -> None:
    """Give a camp buff level-band ranks from the camp object whose top band matches most of its
    fx values (none matched or a single band: unchanged)."""
    best, best_n = None, 0
    for camp in group:
        if len(camp.bands) < 2:
            continue
        n = len(_positions(b.fx, camp.bands[-1][1]))
        if n > best_n:
            best, best_n = camp, n
    if not best:
        return
    b.ranks = band_ranks(b.id, b.fx, best.bands)
    b.lvl = best.bands[0][0]


def _class_buffs(buffs: dict[int, Buff]) -> dict[str, list[Buff]]:
    by_name: dict[str, list[Buff]] = {}
    for b in buffs.values():
        if b.cat == "CLASS":
            by_name.setdefault(b.name, []).append(b)
    return by_name


def apply_camping(buffs: dict[int, Buff], unclassified: list[Buff],
                  camps: list[CampBuff]) -> list[str]:
    """Mark camp buffs (all ranks, matched by name); return camp buff names with no match.

    A camp buff whose object lists level bands gets one rank per band (see band_ranks) and
    lvl = the lowest band's level.

    Run after curated merges: the exclusive class buff's current `excl` is copied as-is.
    When several camp objects share a buff name, each camp spell picks the exclusive
    class buff whose fx keys overlap its own (ties/no overlap: first listed exclusive).
    """
    everything = list(buffs.values()) + list(unclassified)
    classes = _class_buffs(buffs)
    groups: dict[str, list[CampBuff]] = {}
    for camp in camps:
        groups.setdefault(camp.buff_name, []).append(camp)
    unmatched: list[str] = []
    for name, group in groups.items():
        matched = [b for b in everything if b.name == name]
        if not matched:
            unmatched.append(name)
            continue
        exclusives = [c.exclusive_with for c in group if c.exclusive_with in classes]
        exclusives = list(dict.fromkeys(exclusives))
        for b in matched:
            old_default = f"{b.cat}:{b.name}"
            b.cat = "CAMPING"
            if exclusives:
                pick = next((e for e in exclusives
                             if any(set(c.fx) & set(b.fx) for c in classes[e])), exclusives[0])
                b.excl = classes[pick][0].excl
            elif b.excl in ("", old_default):
                b.excl = f"CAMPING:{b.name}"
            _apply_bands(b, group)
            for camp in group:
                note = f"{camp.profession} {camp.skill}"
                if not any(x.kind == "camping" and x.name == camp.object_name and x.note == note
                           for x in b.sources):
                    b.sources.append(Source(kind="camping", name=camp.object_name, note=note))
    return unmatched


def unresolved_exclusives(buffs: dict[int, Buff], camps: list[CampBuff]) -> list[tuple[str, str]]:
    """(camp buff name, exclusive name) pairs where no CLASS buff has that exclusive name."""
    classes = _class_buffs(buffs)
    out: list[tuple[str, str]] = []
    for c in camps:
        pair = (c.buff_name, c.exclusive_with)
        if c.exclusive_with and c.exclusive_with not in classes and pair not in out:
            out.append(pair)
    return out


def parse_finder(data: dict) -> dict[int, str]:
    return {int(i["i"]): i.get("t") or "" for i in data.get("items", [])}


def crosscheck(buffs: dict[int, Buff], finder: dict[int, str]) -> list[int]:
    have = {item for b in buffs.values() for item in b.items}
    return sorted(i for i, text in finder.items()
                  if INCREASES_RE.search(text) and i not in have)


def fetch_site(http_get) -> tuple[str, dict]:
    """http_get(url, headers) -> response text. One GET per URL."""
    headers = {"User-Agent": USER_AGENT}
    camp_html = http_get(f"{BASE}/camping/", headers)
    cons_html = http_get(f"{BASE}/consumables/", headers)
    m = FINDER_RE.search(cons_html)
    if not m:
        raise ValueError("consumables page: no finder-en-*.json asset found")
    return camp_html, json.loads(http_get(BASE + m.group(0), headers))
