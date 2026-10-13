"""Extract stat buffs from DB2 table rows into Buff records."""
from collections import defaultdict

from tools.model import Buff, Rank

APPLY_EFFECTS = {6, 35, 65}
PRIMARY = {0: "STR", 1: "AGI", 2: "STA", 3: "INT", 4: "SPI"}
# Auras that map straight to a stat key.  290 (MOD_CRIT_PCT) is not in the
# original rule list but carries e.g. the +2% crit of Elixir of the Mongoose.
SIMPLE_AURAS = {
    137: "STAT_PCT", 99: "AP", 124: "RAP", 135: "HEAL", 142: "ARMOR_PCT",
    34: "HP", 35: "MANA", 85: "MP5", 84: "HP5", 52: "CRIT", 290: "CRIT",
    57: "SPELL_CRIT", 71: "SPELL_CRIT", 54: "HIT", 55: "SPELL_HIT",
}
ITEM_MOD = {3: "AGI", 4: "STR", 5: "INT", 6: "SPI", 7: "STA"}
CLASS_SETS = {
    3: "MAGE", 4: "WARRIOR", 5: "WARLOCK", 6: "PRIEST", 7: "DRUID",
    8: "ROGUE", 9: "HUNTER", 10: "PALADIN", 11: "SHAMAN",
}
CONSUMABLE_CATS = {1: "POTION", 2: "ELIXIR", 3: "FLASK", 4: "SCROLL", 5: "FOOD", 6: "WEAPON"}
BURST_MAX = 600
ENCHANT_EFFECT = 54
TRIGGER_DEPTH = 2


def _i(row: dict, key: str) -> int:
    v = row.get(key)
    return int(float(v)) if v not in (None, "") else 0


def _spell_fx(effects: list[dict]) -> dict[str, float]:
    fx: dict[str, float] = defaultdict(float)
    for r in effects:
        if _i(r, "Effect") not in APPLY_EFFECTS:
            continue
        aura, misc = _i(r, "EffectAura"), _i(r, "EffectMiscValue_0")
        val = int(float(r.get("EffectBasePointsF") or 0))
        if aura == 29:
            for k in ([0, 1, 2, 3, 4] if misc == -1 else [misc]):
                if k in PRIMARY:
                    fx[PRIMARY[k]] += val
        elif aura == 13:
            if misc & 126:
                fx["SPELL_DMG"] += val
        elif aura == 22:
            if misc == 1:
                fx["ARMOR"] += val
        elif aura in SIMPLE_AURAS:
            fx[SIMPLE_AURAS[aura]] += val
    return dict(fx)


def _item_category(item: dict | None) -> str | None:
    if item is None:
        return None
    cls, sub, inv = _i(item, "ClassID"), _i(item, "SubclassID"), _i(item, "InventoryType")
    if inv == 12 or cls in (2, 4):
        return "TRINKET"
    if cls == 0:
        return CONSUMABLE_CATS.get(sub)
    if cls == 12:
        return "QUEST"
    return None


def extract_buffs(t: dict[str, list[dict]], era_spell_ids: set[int]) -> tuple[dict[int, Buff], list[Buff]]:
    """Return (classified buffs keyed by aura spell id, unclassified candidates)."""
    names = {_i(r, "ID"): r["Name_lang"] for r in t["SpellName"]}
    durations = {_i(r, "ID"): _i(r, "Duration") for r in t["SpellDuration"]}
    spell_dur: dict[int, int] = {}
    for r in t["SpellMisc"]:
        if _i(r, "DifficultyID") == 0:
            spell_dur[_i(r, "SpellID")] = max(0, durations.get(_i(r, "DurationIndex"), 0)) // 1000
    effects: dict[int, list[dict]] = defaultdict(list)
    for r in t["SpellEffect"]:
        effects[_i(r, "SpellID")].append(r)
    levels = {_i(r, "SpellID"): _i(r, "SpellLevel") for r in t.get("SpellLevels", [])
              if _i(r, "DifficultyID") == 0}
    class_set = {_i(r, "SpellID"): _i(r, "SpellClassSet") for r in t.get("SpellClassOptions", [])}
    enchants = {_i(r, "ID"): r for r in t.get("SpellItemEnchantment", [])}
    items = {_i(r, "ID"): r for r in t.get("Item", [])}
    sparse = {_i(r, "ID"): r for r in t.get("ItemSparse", [])}
    item_effect = {_i(r, "ID"): r for r in t.get("ItemEffect", [])}

    fx_cache: dict[int, dict[str, float]] = {}

    def spell_fx(sid: int) -> dict[str, float]:
        if sid not in fx_cache:
            fx_cache[sid] = _spell_fx(effects.get(sid, []))
        return fx_cache[sid]

    def enchant_info(sid: int) -> tuple[int | None, dict[str, float]]:
        """Temporary weapon enchant (Effect 54): (enchant id, stats)."""
        for r in effects.get(sid, []):
            if _i(r, "Effect") != ENCHANT_EFFECT:
                continue
            eid = _i(r, "EffectMiscValue_0")
            ench = enchants.get(eid, {})
            fx: dict[str, float] = defaultdict(float)
            for n in range(3):
                etype, arg = _i(ench, f"Effect_{n}"), _i(ench, f"EffectArg_{n}")
                if etype == 5 and arg in ITEM_MOD:
                    fx[ITEM_MOD[arg]] += _i(ench, f"EffectPointsMin_{n}")
                elif etype == 3:
                    for k, v in spell_fx(arg).items():
                        fx[k] += v
            return eid, dict(fx)
        return None, {}

    def make(sid: int, cat, fx, lvl, item_ids, **kw) -> Buff:
        name = names.get(sid, "")
        dur = dur_of(sid)
        return Buff(id=sid, name=name, cat=cat, fx=fx, dur=dur, lvl=lvl, excl=f"{cat}:{name}",
                    items=item_ids, burst=0 < dur < BURST_MAX, new=sid not in era_spell_ids, **kw)

    def dur_of(sid: int) -> int:
        """Spell duration in seconds; temp weapon enchants carry theirs on the enchant."""
        dur = spell_dur.get(sid, 0)
        if dur <= 0:
            eid, _ = enchant_info(sid)
            if eid is not None:
                dur = max(0, _i(enchants.get(eid, {}), "Duration"))
        return dur

    def excluded(sid: int) -> bool:
        return "Totem" in names.get(sid, "") or dur_of(sid) <= 0

    # on-use (TriggerType 0) item spells -> items
    use_items: dict[int, list[int]] = defaultdict(list)
    for r in t.get("ItemXItemEffect", []):
        eff = item_effect.get(_i(r, "ItemEffectID"))
        if eff and _i(eff, "TriggerType") == 0 and _i(eff, "SpellID"):
            use_items[_i(eff, "SpellID")].append(_i(r, "ItemID"))

    # aura spell -> items, following EffectTriggerSpell up to TRIGGER_DEPTH
    aura_items: dict[int, list[int]] = defaultdict(list)
    for root, item_ids in use_items.items():
        frontier, seen = [root], {root}
        for _depth in range(TRIGGER_DEPTH + 1):
            nxt = []
            for sid in frontier:
                if spell_fx(sid) or enchant_info(sid)[0] is not None:
                    for iid in item_ids:
                        if iid not in aura_items[sid]:
                            aura_items[sid].append(iid)
                for r in effects.get(sid, []):
                    trig = _i(r, "EffectTriggerSpell")
                    if trig and trig not in seen:
                        seen.add(trig)
                        nxt.append(trig)
            frontier = nxt

    buffs: dict[int, Buff] = {}
    unclassified: list[Buff] = []

    for sid, item_ids in aura_items.items():
        if excluded(sid):
            continue
        eid, efx = enchant_info(sid)
        fx = efx if eid is not None else spell_fx(sid)
        if not fx:
            continue
        classified = [(iid, c) for iid in item_ids if (c := _item_category(items.get(iid)))]
        if eid is not None:
            cat, ids = "WEAPON", item_ids
        elif classified:
            cat = classified[0][1]
            ids = [iid for iid, c in classified if c == cat]
        else:
            cat, ids = None, item_ids
        if cat == "FOOD" and set(fx) <= {"HP5", "MP5"} and dur_of(sid) <= 60:
            continue  # eating effect, not the Well Fed buff
        lvl = min((_i(sparse.get(iid, {}), "RequiredLevel") for iid in ids), default=0)
        buff = make(sid, cat, fx, lvl, ids, enchant=eid)
        if cat:
            buffs[sid] = buff
        else:
            unclassified.append(buff)

    # class buffs, grouped by (class, name)
    groups: dict[tuple[str, str], list[int]] = defaultdict(list)
    for sid, cset in class_set.items():
        if cset in CLASS_SETS and sid not in aura_items and not excluded(sid) and spell_fx(sid):
            groups[(CLASS_SETS[cset], names.get(sid, ""))].append(sid)
    for (cls, _name), sids in groups.items():
        sids.sort(key=lambda s: (levels.get(s, 0), s))
        top = sids[-1]
        ranks = [Rank(s, levels.get(s, 0), spell_fx(s)) for s in sids]
        buffs[top] = make(top, "CLASS", spell_fx(top), ranks[0].lvl, [], cls=cls, ranks=ranks)

    # long buffs with no item and no class: world candidates for curated overrides
    for sid in effects:
        if sid in aura_items or class_set.get(sid) in CLASS_SETS:
            continue
        if dur_of(sid) >= BURST_MAX and not excluded(sid) and spell_fx(sid):
            unclassified.append(make(sid, None, spell_fx(sid), 0, []))
    return buffs, unclassified
