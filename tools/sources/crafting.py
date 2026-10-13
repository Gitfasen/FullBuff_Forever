"""Attach crafting (profession) sources to buffs from DB2 data."""
from tools.model import Buff, Source

# SkillLine IDs that are professions; other skill lines are ignored.
PROFESSIONS = {164, 165, 171, 185, 197, 202, 333, 129}
EFFECT_CREATE_ITEM = 24
EFFECT_LEARN_SPELL = 36


def _i(row: dict, key: str) -> int:
    v = row.get(key)
    return int(v) if v not in (None, "") else 0


def attach_craft_sources(buffs: dict[int, Buff], t: dict[str, list[dict]]) -> None:
    item_spells: dict[int, list[int]] = {}
    for r in t.get("SpellEffect", []):
        if _i(r, "Effect") == EFFECT_CREATE_ITEM and _i(r, "EffectItemType"):
            spells = item_spells.setdefault(_i(r, "EffectItemType"), [])
            if _i(r, "SpellID") not in spells:
                spells.append(_i(r, "SpellID"))

    abilities: dict[int, dict] = {}
    for r in t.get("SkillLineAbility", []):
        if _i(r, "SkillLine") in PROFESSIONS:
            abilities.setdefault(_i(r, "Spell"), r)

    names = {_i(r, "ID"): r["DisplayName_lang"] for r in t.get("SkillLine", [])}

    # learn-spell effects: taught spell -> spells whose effect teaches it
    teachers: dict[int, set[int]] = {}
    for r in t.get("SpellEffect", []):
        if _i(r, "Effect") == EFFECT_LEARN_SPELL and _i(r, "EffectTriggerSpell"):
            teachers.setdefault(_i(r, "EffectTriggerSpell"), set()).add(_i(r, "SpellID"))

    effect_spell = {_i(r, "ID"): _i(r, "SpellID") for r in t.get("ItemEffect", [])
                    if _i(r, "TriggerType") == 0}  # on-use only
    required = {_i(r, "ID"): _i(r, "RequiredSkillRank") for r in t.get("ItemSparse", [])}
    use_spell_items: dict[int, list[int]] = {}
    for r in t.get("ItemXItemEffect", []):
        sid = effect_spell.get(_i(r, "ItemEffectID"))
        if sid:
            use_spell_items.setdefault(sid, []).append(_i(r, "ItemID"))

    def rank_for(spell: int, ability: dict) -> int:
        ranks = [required[item] for teacher in teachers.get(spell, ())
                 for item in use_spell_items.get(teacher, ()) if required.get(item, 0) > 0]
        return min(ranks) if ranks else _i(ability, "TrivialSkillLineRankLow")

    for buff in buffs.values():
        seen = {(s.kind, s.name, s.note) for s in buff.sources}
        for item_id in buff.items:
            for spell in item_spells.get(item_id, ()):
                ability = abilities.get(spell)
                name = names.get(_i(ability, "SkillLine")) if ability else None
                if not name:
                    continue
                note = str(rank_for(spell, ability))
                if ("craft", name, note) not in seen:
                    seen.add(("craft", name, note))
                    buff.sources.append(Source(kind="craft", name=name, note=note))
