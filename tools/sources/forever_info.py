"""Camping buffs and a consumables cross-check from wowclassicforever.info."""
import json
import re
from dataclasses import dataclass

from tools.model import Buff, Source

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
            camp = CampBuff(buff["name"], obj["name"], obj["profession"], int(obj["skill"]),
                            exclusive.get("name") if exclusive else None)
            if camp not in seen:
                seen.add(camp)
                result.append(camp)
    return result


def apply_camping(buffs: dict[int, Buff], unclassified: list[Buff],
                  camps: list[CampBuff]) -> list[str]:
    """Mark camp buffs (all ranks, matched by name); return camp buff names with no match.

    Run after curated merges: the exclusive class buff's current `excl` is copied as-is.
    """
    everything = list(buffs.values()) + list(unclassified)
    class_excl: dict[str, str] = {}
    for b in buffs.values():
        if b.cat == "CLASS" and b.name not in class_excl:
            class_excl[b.name] = b.excl
    excl_set: set[int] = set()  # camp buffs whose excl was already set in this call
    unmatched: list[str] = []
    for camp in camps:
        matched = [b for b in everything if b.name == camp.buff_name]
        if not matched:
            if camp.buff_name not in unmatched:
                unmatched.append(camp.buff_name)
            continue
        note = f"{camp.profession} {camp.skill}"
        for b in matched:
            old_default = f"{b.cat}:{b.name}"
            b.cat = "CAMPING"
            if camp.exclusive_with in class_excl and id(b) not in excl_set:
                b.excl = class_excl[camp.exclusive_with]
                excl_set.add(id(b))
            elif id(b) not in excl_set and b.excl in ("", old_default):
                b.excl = f"CAMPING:{b.name}"
            if not any(s.kind == "camping" and s.name == camp.object_name and s.note == note
                       for s in b.sources):
                b.sources.append(Source(kind="camping", name=camp.object_name, note=note))
    return unmatched


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
