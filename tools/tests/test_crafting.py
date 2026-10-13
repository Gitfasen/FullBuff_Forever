from tools.model import Buff, Source
from tools.sources.crafting import attach_craft_sources


def buff(items):
    return Buff(id=1, name="b", cat=None, fx={}, dur=1, lvl=1, excl="", items=items,
                burst=False, new=False)


def tables(skill_line="171", skill_name="Alchemy", recipe=False):
    t = {
        "SpellEffect": [{"SpellID": "11450", "Effect": "24", "EffectItemType": "8951",
                         "EffectTriggerSpell": "0"}],
        "SkillLineAbility": [{"Spell": "11450", "SkillLine": skill_line,
                              "TrivialSkillLineRankLow": "215"}],
        "SkillLine": [{"ID": skill_line, "DisplayName_lang": skill_name}],
        "ItemXItemEffect": [], "ItemEffect": [], "ItemSparse": [],
    }
    if recipe:
        t["ItemXItemEffect"] = [{"ItemID": "9999", "ItemEffectID": "5"}]
        t["ItemEffect"] = [{"ID": "5", "SpellID": "700"}]
        t["SpellEffect"].append({"SpellID": "700", "Effect": "36", "EffectItemType": "0",
                                 "EffectTriggerSpell": "11450"})
        t["ItemSparse"] = [{"ID": "9999", "RequiredSkillRank": "195"}]
    return t


def test_craft_source_from_create_item_spell():
    b = buff([8951])
    attach_craft_sources({1: b}, tables())
    assert b.sources == [Source(kind="craft", name="Alchemy", note="215")]


def test_recipe_required_rank_wins():
    b = buff([8951])
    attach_craft_sources({1: b}, tables(recipe=True))
    assert b.sources == [Source(kind="craft", name="Alchemy", note="195")]


def test_non_profession_skillline_ignored():
    b = buff([8951])
    attach_craft_sources({1: b}, tables(skill_line="6", skill_name="Frost"))
    assert b.sources == []


def test_craft_sources_idempotent():
    b = buff([8951])
    t = tables()
    attach_craft_sources({1: b}, t)
    attach_craft_sources({1: b}, t)
    assert len(b.sources) == 1
