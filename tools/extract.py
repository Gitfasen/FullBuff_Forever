"""Extract stat buffs from DB2 table rows into Buff records."""
import re
from collections import defaultdict

from tools.model import BURST_MAX, Buff, Rank

APPLY_EFFECTS = {6, 35, 65}
AREA_AURA_EFFECTS = {35, 65}
PRIMARY = {0: "STR", 1: "AGI", 2: "STA", 3: "INT", 4: "SPI"}
# Auras that map straight to a stat key.
SIMPLE_AURAS = {
    99: "AP", 124: "RAP", 135: "HEAL", 142: "ARMOR_PCT",
    34: "HP", 35: "MANA", 85: "MP5", 84: "HP5", 52: "CRIT",
    57: "SPELL_CRIT", 71: "SPELL_CRIT", 54: "HIT", 55: "SPELL_HIT",
}
# 290 (MOD_CRIT_PCT) is crit with all spells and attacks: Forever's own texts say so
# (Slip'kik's Savvy, Songflower Serenade, Rallying Cry, caster Elixir of the Owl).
MULTI_AURAS = {290: ("CRIT", "SPELL_CRIT")}
ARMOR_AURAS = {22, 674}   # MOD_RESISTANCE / Forever's armor aura (Mark of the Wild); misc 1 = armor
# MOD_TOTAL_STAT_PERCENTAGE / MOD_PERCENT_STAT: misc -1 = all stats, 0..4 = one stat
PCT_STAT_AURAS = {137, 80}
AURA_ARMOR_PCT = 101      # MOD_RESISTANCE_PCT; misc 1 = armor
AURA_PERIODIC_ENERGIZE = 24
AURA_MAX_POWER = 418
POWER_MANA = 0
AURA_TRIGGER_WITH_VALUE = 227  # PERIODIC_TRIGGER_SPELL_WITH_VALUE: bp is the triggered spell's value
TARGET_CASTER = 1
TARGET_PET = 5            # ImplicitTarget: the caster's pet (Intimidation, Blessing of the Black Book)
ATTR0_PASSIVE = 0x40      # SpellMisc.Attributes_0
# Test / placeholder / deprecated spells and items, e.g. "(DNT) ... - TEST RAID SPELL",
# "Test Sharpen Blade", "ALEX BUG TEST ITEM", "Deprecated Reed Pipe".
JUNK_RE = re.compile(r"\(DNT\)|\[(?:DNT|PH)\]|\bTEST\b|^Test\b|^Copy of\b|^Deprecated\b")
CLASS_SKILL_CATEGORY = 7  # SkillLine.CategoryID of class skill lines
NEVER_LEARNED = 3         # SkillLineAbility.AcquireMethod (e.g. Season of Discovery rune spells)
ITEM_MOD = {3: "AGI", 4: "STR", 5: "INT", 6: "SPI", 7: "STA"}
CLASS_SETS = {
    3: "MAGE", 4: "WARRIOR", 5: "WARLOCK", 6: "PRIEST", 7: "DRUID",
    8: "ROGUE", 9: "HUNTER", 10: "PALADIN", 11: "SHAMAN",
}
CLASS_MASKS = {1: "WARRIOR", 2: "PALADIN", 4: "HUNTER", 8: "ROGUE", 16: "PRIEST", 64: "SHAMAN",
               128: "MAGE", 256: "WARLOCK", 1024: "DRUID"}
CONSUMABLE_CATS = {1: "POTION", 2: "ELIXIR", 3: "FLASK", 4: "SCROLL", 5: "FOOD", 6: "WEAPON"}
CONSUMABLE_OTHER = 8
# temporary weapon enchant: 54 (classic), 360 (Forever imbues: Rockbiter Weapon, "Imbue ..." items)
ENCHANT_EFFECTS = {54, 360}
TRIGGER_DEPTH = 2


def _i(row: dict, key: str) -> int:
    v = row.get(key)
    return int(float(v)) if v not in (None, "") else 0


def _positive(fx: dict[str, float]) -> dict[str, float]:
    """Keep only buffing (> 0) entries; debuffs carry negative values."""
    return {k: v for k, v in fx.items() if v > 0}


def _spell_fx(effects: list[dict]) -> dict[str, float]:
    fx: dict[str, float] = defaultdict(float)
    for r in effects:
        if _i(r, "Effect") not in APPLY_EFFECTS or _i(r, "ImplicitTarget_0") == TARGET_PET:
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
        elif aura in ARMOR_AURAS:
            if misc == 1:
                fx["ARMOR"] += val
        elif aura in PCT_STAT_AURAS:
            if misc == -1:
                fx["STAT_PCT"] += val
            elif misc in PRIMARY:
                fx[PRIMARY[misc] + "_PCT"] += val
        elif aura == AURA_ARMOR_PCT:
            if misc == 1:
                fx["ARMOR_PCT"] += val
        elif aura == AURA_PERIODIC_ENERGIZE:
            period = _i(r, "EffectAuraPeriod")
            if misc == POWER_MANA and period > 0:
                fx["MP5"] += val * 5000 / period
        elif aura == AURA_MAX_POWER:
            if misc == POWER_MANA:
                fx["MANA"] += val
        elif aura in MULTI_AURAS:
            for k in MULTI_AURAS[aura]:
                fx[k] += val
        elif aura in SIMPLE_AURAS:
            fx[SIMPLE_AURAS[aura]] += val
    return _positive(fx)


def _item_category(item: dict | None, has_eating: bool = False) -> str | None:
    """has_eating: the item also carries an eating/drinking effect (food among "Other" consumables)."""
    if item is None:
        return None
    cls, sub, inv = _i(item, "ClassID"), _i(item, "SubclassID"), _i(item, "InventoryType")
    if inv == 12 or cls in (2, 4):
        return "TRINKET"
    if cls == 0:
        if sub == CONSUMABLE_OTHER and has_eating:
            return "FOOD"
        return CONSUMABLE_CATS.get(sub)
    if cls == 12:
        return "QUEST"
    return None


def extract_buffs(t: dict[str, list[dict]], era_spell_ids: set[int]) -> tuple[dict[int, Buff], list[Buff]]:
    """Return (classified buffs keyed by aura spell id, unclassified candidates).

    Forever food tiers are keyed by their tier spell ("Nutritious Food"), see food_tiers().
    """
    names = {_i(r, "ID"): r["Name_lang"] for r in t["SpellName"]}
    durations = {_i(r, "ID"): _i(r, "Duration") for r in t["SpellDuration"]}
    spell_dur: dict[int, int] = {}
    attr0: dict[int, int] = {}
    for r in t["SpellMisc"]:
        if _i(r, "DifficultyID") == 0:
            spell_dur[_i(r, "SpellID")] = max(0, durations.get(_i(r, "DurationIndex"), 0)) // 1000
            attr0[_i(r, "SpellID")] = _i(r, "Attributes_0")
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
    class_lines = {_i(r, "ID") for r in t.get("SkillLine", [])
                   if _i(r, "CategoryID") == CLASS_SKILL_CATEGORY}
    # trainer-learnable class spells -> ClassMask; NPC copies of class spells have no such row
    learnable: dict[int, int] = {}
    for r in t.get("SkillLineAbility", []):
        if _i(r, "SkillLine") in class_lines and _i(r, "AcquireMethod") != NEVER_LEARNED:
            learnable[_i(r, "Spell")] = learnable.get(_i(r, "Spell"), 0) | _i(r, "ClassMask")

    fx_cache: dict[int, dict[str, float]] = {}

    def spell_fx(sid: int) -> dict[str, float]:
        if sid not in fx_cache:
            fx_cache[sid] = _spell_fx(effects.get(sid, []))
        return fx_cache[sid]

    def enchant_info(sid: int) -> tuple[int | None, dict[str, float]]:
        """Temporary weapon enchant (ENCHANT_EFFECTS): (enchant id, stats)."""
        for r in effects.get(sid, []):
            if _i(r, "Effect") not in ENCHANT_EFFECTS:
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
            return eid, _positive(fx)
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

    def bad_name(sid: int) -> bool:
        name = names.get(sid, "")
        return "Totem" in name or bool(JUNK_RE.search(name))

    def excluded(sid: int) -> bool:
        return bad_name(sid) or dur_of(sid) <= 0

    def channel(sid: int) -> bool:
        """Eating/drinking or mana/health channel (HP5/MP5 only, <= 60 s), not a stat buff."""
        fx = spell_fx(sid)
        return bool(fx) and set(fx) <= {"HP5", "MP5"} and 0 < dur_of(sid) <= 60

    def class_of(sid: int) -> str | None:
        """Class of a trainer-learnable class spell (class set, else the trainer row's ClassMask)."""
        if sid not in learnable:
            return None
        if class_set.get(sid) in CLASS_SETS:
            return CLASS_SETS[class_set[sid]]
        return CLASS_MASKS.get(learnable[sid])

    def class_fx(sid: int) -> dict[str, float]:
        """Stats of a class spell. No-duration toggles count when active (not passive),
        self-cast (Effect 6 on the caster) and not an area aura (Effect 35/65)."""
        eid, efx = enchant_info(sid)
        if eid is not None:
            return efx if dur_of(sid) > 0 else {}
        if dur_of(sid) > 0:
            return spell_fx(sid)
        rows = effects.get(sid, [])
        if attr0.get(sid, 0) & ATTR0_PASSIVE or any(_i(r, "Effect") in AREA_AURA_EFFECTS for r in rows):
            return {}
        return _spell_fx([r for r in rows if _i(r, "Effect") == 6
                          and _i(r, "ImplicitTarget_0") == TARGET_CASTER])

    # on-use (TriggerType 0) item spells -> items
    use_items: dict[int, list[int]] = defaultdict(list)
    for r in t.get("ItemXItemEffect", []):
        eff = item_effect.get(_i(r, "ItemEffectID"))
        iid = _i(r, "ItemID")
        if JUNK_RE.search(sparse.get(iid, {}).get("Display_lang") or ""):
            continue
        if eff and _i(eff, "TriggerType") == 0 and _i(eff, "SpellID"):
            use_items[_i(eff, "SpellID")].append(iid)

    # aura spell -> items, following EffectTriggerSpell up to TRIGGER_DEPTH
    aura_items: dict[int, list[int]] = defaultdict(list)
    # template aura -> {tier spell: (value, items)} handed over by AURA_TRIGGER_WITH_VALUE
    tiers: dict[int, dict[int, tuple[int, list[int]]]] = defaultdict(dict)
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
                    if (trig and _i(r, "Effect") in APPLY_EFFECTS
                            and _i(r, "EffectAura") == AURA_TRIGGER_WITH_VALUE):
                        value = int(float(r.get("EffectBasePointsF") or 0))
                        _v, have = tiers[trig].setdefault(sid, (value, []))
                        have.extend(i for i in item_ids if i not in have)
                    if trig and trig not in seen:
                        seen.add(trig)
                        nxt.append(trig)
            frontier = nxt

    eating_items = {iid for sid, ids in aura_items.items() if channel(sid) for iid in ids}

    def category(item_ids: list[int]) -> tuple[str | None, list[int]]:
        classified = [(iid, c) for iid in item_ids
                      if (c := _item_category(items.get(iid), iid in eating_items))]
        if not classified:
            return None, item_ids
        cat = classified[0][1]
        return cat, [iid for iid, c in classified if c == cat]

    def lvl_of(item_ids: list[int]) -> int:
        return min((_i(sparse.get(iid, {}), "RequiredLevel") for iid in item_ids), default=0)

    def food_tiers(sid: int) -> list[Buff]:
        """One FOOD Buff per tier spell passing its value to template `sid` (Forever foods):
        the value replaces every effect's base points of the template."""
        out = []
        for tier, (value, ids) in sorted(tiers.get(sid, {}).items()):
            cat, ids = category(ids)
            if cat != "FOOD":
                continue
            fx = _spell_fx([dict(r, EffectBasePointsF=str(value)) for r in effects.get(sid, [])])
            if not fx:
                continue  # zero / negative value
            name, dur = names.get(sid, ""), dur_of(sid)
            out.append(Buff(id=tier, name=name, cat="FOOD", fx=fx, dur=dur, lvl=lvl_of(ids),
                            excl=f"FOOD:{name}", items=ids, burst=0 < dur < BURST_MAX,
                            new=tier not in era_spell_ids))
        return out

    buffs: dict[int, Buff] = {}
    unclassified: list[Buff] = []

    for sid, item_ids in aura_items.items():
        if excluded(sid) or class_of(sid) or channel(sid):
            continue
        eid, efx = enchant_info(sid)
        fx = efx if eid is not None else spell_fx(sid)
        if not fx:
            continue
        if sid in tiers:
            tier_buffs = food_tiers(sid)
            for b in tier_buffs:
                buffs[b.id] = b
            if tier_buffs:
                continue  # the shared template itself only carries placeholder values
        cat, ids = ("WEAPON", item_ids) if eid is not None else category(item_ids)
        buff = make(sid, cat, fx, lvl_of(ids), ids, enchant=eid)
        if cat:
            buffs[sid] = buff
        else:
            unclassified.append(buff)

    # class buffs, grouped by (class, name)
    groups: dict[tuple[str, str], list[int]] = defaultdict(list)
    for sid in learnable:
        cls = class_of(sid)
        if cls and not bad_name(sid) and class_fx(sid) and not channel(sid):
            groups[(cls, names.get(sid, ""))].append(sid)
    for (cls, _name), sids in groups.items():
        sids.sort(key=lambda s: (levels.get(s, 0), s))
        top = sids[-1]
        ranks = [Rank(s, levels.get(s, 0), class_fx(s)) for s in sids]
        buffs[top] = make(top, "CLASS", class_fx(top), ranks[0].lvl, [], cls=cls, ranks=ranks,
                          enchant=enchant_info(top)[0])

    # long buffs with no item and no class: world candidates for curated overrides
    for sid in effects:
        if sid in aura_items or class_set.get(sid) in CLASS_SETS:
            continue
        if dur_of(sid) >= BURST_MAX and not excluded(sid) and spell_fx(sid):
            unclassified.append(make(sid, None, spell_fx(sid), 0, []))
    return buffs, unclassified
