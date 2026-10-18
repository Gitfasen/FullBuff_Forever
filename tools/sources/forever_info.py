"""Camping buffs and a consumables cross-check from wowclassicforever.info."""
import json
import re
from dataclasses import dataclass, field

from tools.model import Buff, Rank, Source

BASE = "https://wowclassicforever.info"
USER_AGENT = "FullBuff-build"
SCRIPT_RE = re.compile(r'<script type="application/json"[^>]*>(.*?)</script>', re.S)
# "finder-en-<hash>.json" only; "finder-en-tips-<hash>.json" is a different file.
FINDER_RE = re.compile(r"/assets/consumables/finder-en-[0-9a-f]+\.json")
INCREASES_RE = re.compile(r"increase[sd]", re.I)


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


_ALL_STATS = ("STR", "AGI", "STA", "INT", "SPI")
# fx key(s) -> phrase in a camp band's description; the first group is the value.
_BAND_PHRASES = (
    (("ARMOR",), re.compile(r"(\d+) Armor", re.I)),
    (_ALL_STATS, re.compile(r"(\d+) increase to all stats", re.I)),
    (("STAT_PCT",), re.compile(r"(\d+)% increased stats", re.I)),
    (("MP5",), re.compile(r"regenerate (\d+) Mana every 5 sec", re.I)),
    (("AP",), re.compile(r"(\d+) increased (?:melee )?Attack Power", re.I)),
    (("STR",), re.compile(r"(\d+) increased Strength", re.I)),
    (("AGI",), re.compile(r"(\d+) increased Agility", re.I)),
    (("STA",), re.compile(r"(\d+) increased Stamina", re.I)),
    (("INT",), re.compile(r"(\d+) increased Intellect", re.I)),
    (("SPI",), re.compile(r"(\d+) increased Spirit", re.I)),
    (("CRIT", "SPELL_CRIT"), re.compile(r"(\d+)% increased critical strike", re.I)),
)
COOLDOWN_RE = re.compile(r"All camping features share a cooldown of[^.]*\.?", re.I)


def parse_band(text: str) -> dict[str, int]:
    """fx values stated in one camp band's description, found by phrase (the shared-cooldown
    sentence is ignored; resistances and other effects are not fx)."""
    text = COOLDOWN_RE.sub("", text)
    out: dict[str, int] = {}
    for keys, rx in _BAND_PHRASES:
        m = rx.search(text)
        if m:
            for k in keys:
                out.setdefault(k, int(m.group(1)))
    return out


def band_ranks(spell: int, fx: dict[str, float], bands) -> list[Rank]:
    """One rank per level band (same spell id). Each band's fx comes from the phrases in its
    text; a key absent from a band's text is absent from that rank. A key no band mentions
    keeps the buff's own value in every rank."""
    parsed = [(lvl, parse_band(text)) for lvl, text in bands]
    ranks = []
    for lvl, found in parsed:
        rfx = {}
        for k, v in fx.items():
            if any(k in f for _, f in parsed):
                if k in found:
                    rfx[k] = found[k]
            else:
                rfx[k] = v
        ranks.append(Rank(spell=spell, lvl=lvl, fx=rfx))
    return ranks


def _matches(fx: dict[str, float], top_text: str) -> int:
    found = parse_band(top_text)
    return sum(1 for k, v in fx.items() if found.get(k) == v)


def _apply_bands(b: Buff, group: list[CampBuff]) -> None:
    """Give a camp buff level-band ranks from the camp object whose top band matches most of its
    fx values (none matched or a single band: unchanged)."""
    best, best_n = None, 0
    for camp in group:
        if len(camp.bands) < 2:
            continue
        n = _matches(b.fx, camp.bands[-1][1])
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
