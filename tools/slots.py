"""Conflict slots: stacking groups (`excl`) with names, merged across categories by curated.yaml."""
from tools.model import CATEGORIES, STAT_KEYS, Buff

STAT_NAMES = {
    "STR": ("Strength", "Сила"), "AGI": ("Agility", "Спритність"),
    "STA": ("Stamina", "Витривалість"), "INT": ("Intellect", "Інтелект"),
    "SPI": ("Spirit", "Дух"), "AP": ("Attack power", "Сила атаки"),
    "RAP": ("Ranged attack power", "Сила атаки дальнього бою"),
    "SPELL_DMG": ("Spell damage", "Шкода від заклять"), "HEAL": ("Healing", "Лікування"),
    "ARMOR": ("Armor", "Броня"), "HP": ("Health", "Здоров'я"), "MANA": ("Mana", "Мана"),
    "MP5": ("Mana regeneration", "Відновлення мани"),
    "HP5": ("Health regeneration", "Відновлення здоров'я"),
    "CRIT": ("Critical strike", "Критичний удар"),
    "SPELL_CRIT": ("Spell critical strike", "Критичний удар заклять"),
    "HIT": ("Hit", "Влучання"), "SPELL_HIT": ("Spell hit", "Влучання заклять"),
    "STAT_PCT": ("All stats %", "Усі характеристики %"),
    "ARMOR_PCT": ("Armor %", "Броня %"), "STR_PCT": ("Strength %", "Сила %"),
    "AGI_PCT": ("Agility %", "Спритність %"), "STA_PCT": ("Stamina %", "Витривалість %"),
    "INT_PCT": ("Intellect %", "Інтелект %"), "SPI_PCT": ("Spirit %", "Дух %"),
}
assert set(STAT_NAMES) == set(STAT_KEYS)

FIXED = {"FLASK": ("Flask", "Фляга"), "WEAPON": ("Weapon", "Зброя"), "FOOD:Well Fed": ("Food", "Їжа")}
PREFIX = {"ELIXIR": ("Elixir", "Еліксир"), "SCROLL": ("Scroll", "Сувій")}


def _auto_name(key: str, members: list[Buff]) -> dict[str, str]:
    if key in FIXED:
        en, uk = FIXED[key]
        return {"en": en, "uk": uk}
    head, _, tail = key.partition(":")
    if head in PREFIX and tail in STAT_NAMES:
        return {"en": f"{PREFIX[head][0]} — {STAT_NAMES[tail][0]}",
                "uk": f"{PREFIX[head][1]} — {STAT_NAMES[tail][1]}"}
    name = max(members, key=lambda b: (b.lvl, b.id)).name
    return {"en": name, "uk": name}


def apply_slots(buffs: dict[int, Buff], cur: dict) -> tuple[dict[str, dict], list[str]]:
    """Merge curated groups into slots (excl = slot id) and name every non-burst group."""
    warnings: list[str] = []
    curated: dict[str, dict[str, str]] = {}
    claimed: dict[str, str] = {}
    live = [b for b in buffs.values() if not b.burst]
    for entry in cur.get("slots") or []:
        sid = entry["id"]
        if any(b.excl == sid for b in live) or sid in curated:
            warnings.append(f"slot {sid}: id collides with an existing group or slot")
            continue
        curated[sid] = dict(entry["name"])
        for g in entry.get("groups") or []:
            if g in claimed:
                warnings.append(f"slot {sid}: group {g} already belongs to slot {claimed[g]}")
                continue
            hit = [b for b in live if b.excl == g]
            if not hit:
                warnings.append(f"slot {sid}: group {g} matches no buff")
            claimed[g] = sid
            for b in hit:
                b.excl = sid
    groups: dict[str, list[Buff]] = {}
    for b in buffs.values():
        if not b.burst:
            groups.setdefault(b.excl, []).append(b)
    rows = []
    for key, members in groups.items():
        name = curated.get(key) or _auto_name(key, members)
        cat_idx = min(CATEGORIES.index(b.cat) if b.cat in CATEGORIES else len(CATEGORIES)
                      for b in members)
        rows.append((cat_idx, name["en"], key, name))
    rows.sort(key=lambda r: (r[0], r[1], r[2]))
    return {key: {"name": name, "order": i + 1} for i, (_, _, key, name) in enumerate(rows)}, warnings


def prune_slots(slots: dict[str, dict], buffs: dict[int, Buff]) -> dict[str, dict]:
    """Keep only slots used by a final non-burst buff (call after unobtainable buffs are dropped)."""
    used = {b.excl for b in buffs.values() if not b.burst}
    return {k: v for k, v in slots.items() if k in used}
