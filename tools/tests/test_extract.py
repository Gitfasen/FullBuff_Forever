"""extract_buffs tests on small in-memory tables built from real DB2 rows."""
from tools.extract import extract_buffs


def eff(spell, aura, value, misc=0, effect=6, trigger=0):
    return {"SpellID": str(spell), "Effect": str(effect), "EffectAura": str(aura),
            "EffectBasePointsF": str(value), "EffectMiscValue_0": str(misc),
            "EffectTriggerSpell": str(trigger)}


def tables(spells, effects, durations, items=(), class_sets=None, levels=None, enchants=()):
    """spells: {id: name}; durations: {spell_id: seconds}; items: (id, class, sub, inv, reqlevel, [spell ids])."""
    t = {
        "SpellName": [{"ID": str(i), "Name_lang": n} for i, n in spells.items()],
        "SpellEffect": effects,
        "SpellDuration": [{"ID": str(i + 1), "Duration": str(s * 1000)} for i, s in enumerate(durations.values())],
        "SpellMisc": [{"SpellID": str(sp), "DifficultyID": "0", "DurationIndex": str(i + 1)}
                      for i, sp in enumerate(durations)],
        "SpellClassOptions": [{"SpellID": str(s), "SpellClassSet": str(c)} for s, c in (class_sets or {}).items()],
        "SpellLevels": [{"SpellID": str(s), "DifficultyID": "0", "SpellLevel": str(lv)}
                        for s, lv in (levels or {}).items()],
        "Item": [], "ItemSparse": [], "ItemEffect": [], "ItemXItemEffect": [],
        "SpellItemEnchantment": list(enchants),
    }
    n = 0
    for iid, cls, sub, inv, req, sp_ids in items:
        t["Item"].append({"ID": str(iid), "ClassID": str(cls), "SubclassID": str(sub), "InventoryType": str(inv)})
        t["ItemSparse"].append({"ID": str(iid), "RequiredLevel": str(req)})
        for sp in sp_ids:
            n += 1
            t["ItemEffect"].append({"ID": str(n), "TriggerType": "0", "SpellID": str(sp)})
            t["ItemXItemEffect"].append({"ItemEffectID": str(n), "ItemID": str(iid)})
    return t


def test_mongoose_elixir_agi_crit():
    t = tables({17538: "Elixir of the Mongoose"},
               [eff(17538, 29, 25, misc=1), eff(17538, 290, 2)],
               {17538: 3600}, items=[(13452, 0, 2, 0, 46, [17538])])
    buffs, unclassified = extract_buffs(t, {17538})
    b = buffs[17538]
    assert b.fx == {"AGI": 25, "CRIT": 2}
    assert (b.cat, b.dur, b.burst, b.lvl, b.items, b.new) == ("ELIXIR", 3600, False, 46, [13452], False)
    assert b.excl == "ELIXIR:Elixir of the Mongoose"
    assert unclassified == []


def test_potion_is_burst():
    t = tables({17528: "Mighty Rage"}, [eff(17528, 29, 60, misc=0)], {17528: 30},
               items=[(13442, 0, 1, 0, 46, [17528])])
    b = extract_buffs(t, set())[0][17528]
    assert b.cat == "POTION" and b.burst is True


def test_food_eating_dropped_well_fed_kept():
    t = tables({433: "Food", 19705: "Well Fed"},
               [eff(433, 84, 17), eff(433, 35, 0, effect=64, trigger=19705) | {"EffectAura": "0"},
                eff(19705, 29, 2, misc=2), eff(19705, 29, 2, misc=4)],
               {433: 30, 19705: 900}, items=[(21023, 0, 5, 0, 40, [433])])
    buffs, _ = extract_buffs(t, set())
    assert 433 not in buffs
    w = buffs[19705]
    assert (w.cat, w.fx, w.items, w.dur) == ("FOOD", {"STA": 2, "SPI": 2}, [21023], 900)


def test_class_buff_ranks_grouped():
    t = tables({1243: "Power Word: Fortitude", 1244: "Power Word: Fortitude"},
               [eff(1243, 29, 3, misc=2), eff(1244, 29, 8, misc=2)],
               {1243: 1800, 1244: 1800}, class_sets={1243: 6, 1244: 6}, levels={1243: 1, 1244: 12})
    buffs, _ = extract_buffs(t, set())
    assert list(buffs) == [1244]
    b = buffs[1244]
    assert (b.cls, b.cat, b.lvl, b.fx) == ("PRIEST", "CLASS", 1, {"STA": 8})
    assert [(r.spell, r.lvl) for r in b.ranks] == [(1243, 1), (1244, 12)]
    assert b.ranks[0].fx == {"STA": 3}


def test_totem_excluded():
    t = tables({8076: "Strength of Earth Totem"}, [eff(8076, 29, 8, misc=0)], {8076: 120},
               class_sets={8076: 11})
    buffs, unclassified = extract_buffs(t, set())
    assert buffs == {} and unclassified == []


def test_passive_zero_duration_excluded():
    t = tables({5000: "Toughness"}, [eff(5000, 22, 10, misc=1)], {5000: 0}, class_sets={5000: 4})
    buffs, unclassified = extract_buffs(t, set())
    assert buffs == {} and unclassified == []


def test_weapon_oil_via_enchant():
    ench = [{"ID": "2628", "Duration": "1800", "Effect_0": "5", "EffectArg_0": "5", "EffectPointsMin_0": "36",
             "Effect_1": "0", "EffectArg_1": "0", "EffectPointsMin_1": "0",
             "Effect_2": "0", "EffectArg_2": "0", "EffectPointsMin_2": "0"}]
    t = tables({25122: "Brilliant Wizard Oil"}, [eff(25122, 0, 1800, misc=2628, effect=54)],
               {25122: 0}, items=[(20749, 0, 6, 0, 45, [25122])], enchants=ench)
    b = extract_buffs(t, set())[0][25122]
    assert (b.cat, b.fx, b.enchant, b.dur) == ("WEAPON", {"INT": 36}, 2628, 1800)


def test_unknown_item_class_unclassified():
    t = tables({9000: "Odd Buff"}, [eff(9000, 29, 5, misc=0)], {9000: 300},
               items=[(9001, 15, 0, 0, 10, [9000])])
    buffs, unclassified = extract_buffs(t, set())
    assert buffs == {}
    assert [(b.id, b.cat, b.items) for b in unclassified] == [(9000, None, [9001])]


def test_long_buff_without_item_or_class_unclassified():
    t = tables({7000: "Dire Maul Buff"}, [eff(7000, 99, 140)], {7000: 7200})
    buffs, unclassified = extract_buffs(t, set())
    assert buffs == {} and [b.id for b in unclassified] == [7000]


def test_new_flag_uses_era_ids():
    t = tables({1: "A", 2: "B"}, [eff(1, 29, 5, misc=0), eff(2, 29, 5, misc=0)], {1: 60, 2: 60},
               items=[(10, 0, 1, 0, 1, [1]), (11, 0, 1, 0, 1, [2])])
    buffs, _ = extract_buffs(t, {1})
    assert buffs[1].new is False and buffs[2].new is True
