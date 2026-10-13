"""extract_buffs tests on small in-memory tables built from real DB2 rows."""
from tools.extract import extract_buffs


def eff(spell, aura, value, misc=0, effect=6, trigger=0, period=0):
    return {"SpellID": str(spell), "Effect": str(effect), "EffectAura": str(aura),
            "EffectBasePointsF": str(value), "EffectMiscValue_0": str(misc),
            "EffectTriggerSpell": str(trigger), "EffectAuraPeriod": str(period)}


def tables(spells, effects, durations, items=(), class_sets=None, levels=None, enchants=(), learn=None,
           attrs=None, class_masks=None):
    """spells: {id: name}; durations: {spell_id: seconds};
    items: (id, class, sub, inv, reqlevel, [spell ids][, item name]);
    learn: {spell_id: AcquireMethod} trainer rows on a class skill line (default: every class_sets spell, 0);
    attrs: {spell_id: SpellMisc.Attributes_0}; class_masks: {spell_id: SkillLineAbility.ClassMask}."""
    learn = dict(learn if learn is not None else {s: 0 for s in (class_sets or {})})
    for s in class_masks or {}:
        learn.setdefault(s, 0)
    t = {
        "SpellName": [{"ID": str(i), "Name_lang": n} for i, n in spells.items()],
        "SpellEffect": effects,
        "SpellDuration": [{"ID": str(i + 1), "Duration": str(s * 1000)} for i, s in enumerate(durations.values())],
        "SpellMisc": [{"SpellID": str(sp), "DifficultyID": "0", "DurationIndex": str(i + 1),
                       "Attributes_0": str((attrs or {}).get(sp, 0))}
                      for i, sp in enumerate(durations)],
        "SpellClassOptions": [{"SpellID": str(s), "SpellClassSet": str(c)} for s, c in (class_sets or {}).items()],
        "SpellLevels": [{"SpellID": str(s), "DifficultyID": "0", "SpellLevel": str(lv)}
                        for s, lv in (levels or {}).items()],
        "Item": [], "ItemSparse": [], "ItemEffect": [], "ItemXItemEffect": [],
        "SpellItemEnchantment": list(enchants),
        "SkillLine": [{"ID": "1", "CategoryID": "7"}],
        "SkillLineAbility": [{"Spell": str(s), "SkillLine": "1", "AcquireMethod": str(a),
                              "ClassMask": str((class_masks or {}).get(s, 0))}
                             for s, a in learn.items()],
    }
    n = 0
    for iid, cls, sub, inv, req, sp_ids, *name in items:
        t["Item"].append({"ID": str(iid), "ClassID": str(cls), "SubclassID": str(sub), "InventoryType": str(inv)})
        t["ItemSparse"].append({"ID": str(iid), "RequiredLevel": str(req), "Display_lang": name[0] if name else ""})
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
    assert b.fx == {"AGI": 25, "CRIT": 2, "SPELL_CRIT": 2}  # aura 290 = all crit
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


def test_debuff_with_only_negative_stats_not_extracted():
    t = tables({700: "Demoralizing Shout"}, [eff(700, 99, -300)], {700: 30}, class_sets={700: 4})
    buffs, unclassified = extract_buffs(t, set())
    assert buffs == {} and unclassified == []


def test_mixed_positive_negative_keeps_only_positives():
    t = tables({701: "Trade-off"}, [eff(701, 29, 20, misc=0), eff(701, 29, -10, misc=3), eff(701, 22, 0, misc=1)],
               {701: 60}, items=[(702, 0, 1, 0, 1, [701])])
    assert extract_buffs(t, set())[0][701].fx == {"STR": 20}


def test_class_buff_ignores_unlearnable_npc_copies():
    # 23948 is an NPC copy of Power Word: Fortitude (class set 6, no trainer row, weaker).
    t = tables({10938: "Power Word: Fortitude", 23948: "Power Word: Fortitude"},
               [eff(10938, 29, 70, misc=2), eff(23948, 29, 54, misc=2)],
               {10938: 3600, 23948: 3600}, class_sets={10938: 6, 23948: 6},
               levels={10938: 60, 23948: 60}, learn={10938: 0})
    buffs, unclassified = extract_buffs(t, set())
    assert list(buffs) == [10938] and buffs[10938].fx == {"STA": 70}
    assert [r.spell for r in buffs[10938].ranks] == [10938]
    assert unclassified == []


def test_never_learned_rune_spell_not_a_class_buff():
    t = tables({403215: "Commanding Shout"}, [eff(403215, 29, 2, misc=2)], {403215: 300},
               class_sets={403215: 4}, learn={403215: 3})
    assert extract_buffs(t, set()) == ({}, [])


def test_learnable_class_spell_wins_over_item_link():
    # Arcane Intellect is also cast by a (deprecated) armor item; it is still a mage buff.
    t = tables({1459: "Arcane Intellect"}, [eff(1459, 29, 2, misc=3)], {1459: 3600},
               items=[(1912, 4, 0, 0, 1, [1459])], class_sets={1459: 3}, levels={1459: 1})
    b = extract_buffs(t, set())[0][1459]
    assert (b.cat, b.cls, b.items) == ("CLASS", "MAGE", [])


def test_test_and_dnt_spells_excluded():
    t = tables({7407: "Test Sharpen Blade", 1286253: "(DNT) Blessing of Might - TEST RAID SPELL"},
               [eff(7407, 99, 5), eff(1286253, 99, 112)], {7407: 3600, 1286253: 1800},
               items=[(6213, 0, 1, 0, 1, [7407])])
    assert extract_buffs(t, set()) == ({}, [])


def test_junk_named_item_ignored():
    t = tables({12686: "Enrage"}, [eff(12686, 99, 102)], {12686: 15},
               items=[(17122, 12, 0, 0, 1, [12686], "ALEX BUG TEST ITEM")])
    assert extract_buffs(t, set()) == ({}, [])


def test_periodic_mana_is_mp5():
    t = tables({25290: "Blessing of Wisdom", 9: "Fast Mana"},
               [eff(25290, 24, 40, misc=0, period=5000), eff(9, 24, 10, misc=0, period=2000)],
               {25290: 3600, 9: 3600}, class_sets={25290: 10, 9: 10})
    buffs, _ = extract_buffs(t, set())
    assert buffs[25290].fx == {"MP5": 40} and buffs[9].fx == {"MP5": 25}


def test_periodic_rage_ignored():
    t = tables({5229: "Enrage"}, [eff(5229, 24, 20, misc=1, period=1000)], {5229: 3600},
               class_sets={5229: 11})
    assert extract_buffs(t, set()) == ({}, [])


def test_armor_aura_674_and_max_mana_418():
    t = tables({9885: "Mark of the Wild", 17627: "Distilled Wisdom"},
               [eff(9885, 674, 385, misc=1), eff(9885, 29, 16, misc=-1), eff(9885, 674, -10, misc=2),
                eff(17627, 418, 2000, misc=0), eff(17627, 418, 50, misc=2)],
               {9885: 3600, 17627: 7200}, class_sets={9885: 7}, items=[(13511, 0, 3, 0, 50, [17627])])
    buffs, _ = extract_buffs(t, set())
    assert buffs[9885].fx == {"ARMOR": 385, "STR": 16, "AGI": 16, "STA": 16, "INT": 16, "SPI": 16}
    assert buffs[17627].fx == {"MANA": 2000}


def test_crit_aura_290_is_melee_and_spell():
    t = tables({1304751: "Slip'kik's Savvy"}, [eff(1304751, 290, 3)], {1304751: 7200})
    assert extract_buffs(t, set())[1][0].fx == {"CRIT": 3, "SPELL_CRIT": 3}


def test_percent_stat_auras():
    # 137 / 80 with misc -1 = all stats; a single stat index = that stat's percent key.
    t = tables({20217: "Blessing of Kings", 1304753: "Mol'dar's Moxie", 1304782: "Sayge's Dark Fortune of Strength",
                9: "All Percent"},
               [eff(20217, 137, 10, misc=-1), eff(1304753, 137, 15, misc=2), eff(1304782, 80, 10, misc=0),
                eff(9, 80, 5, misc=-1)],
               {20217: 3600, 1304753: 7200, 1304782: 7200, 9: 7200}, class_sets={20217: 10})
    buffs, unclassified = extract_buffs(t, set())
    assert buffs[20217].fx == {"STAT_PCT": 10}
    assert {b.id: b.fx for b in unclassified} == {1304753: {"STA_PCT": 15}, 1304782: {"STR_PCT": 10},
                                                 9: {"STAT_PCT": 5}}


def test_armor_pct_aura_101():
    t = tables({1304771: "Sayge's Dark Fortune of Armor"}, [eff(1304771, 101, 10, misc=1)], {1304771: 7200})
    assert extract_buffs(t, set())[1][0].fx == {"ARMOR_PCT": 10}


def test_other_consumable_with_eating_effect_is_food():
    # Consumable subclass 8 ("Other") food: eating effect + separate on-use stat buff on one item.
    t = tables({470362: "Food", 470361: "Increased Spell Damage", 10667: "Rage of Ages"},
               [eff(470362, 84, 358), eff(470361, 13, 12, misc=126), eff(10667, 29, 25, misc=0)],
               {470362: 30, 470361: 600, 10667: 3600},
               items=[(232436, 0, 8, 0, 1, [470362, 470361]), (8410, 0, 8, 0, 1, [10667])])
    buffs, unclassified = extract_buffs(t, set())
    assert list(buffs) == [470361] and buffs[470361].cat == "FOOD"
    assert [b.id for b in unclassified] == [10667]


def test_effects_on_pet_ignored():
    # Intimidation / Blessing of the Black Book buff the pet (ImplicitTarget 5), not the player.
    pet = eff(19577, 290, 100) | {"ImplicitTarget_0": "5"}
    t = tables({19577: "Intimidation"}, [pet], {19577: 15}, class_sets={19577: 9})
    assert extract_buffs(t, set()) == ({}, [])


def _food_tiers(cls=0, sub=5, low=1):
    # Forever foods: "Nutritious Food" passes its value to a shared "Well Fed" template (bp 1)
    # through aura 227 (PERIODIC_TRIGGER_SPELL_WITH_VALUE).
    return tables({1248401: "Nutritious Food", 1248380: "Nutritious Food", 1131: "Food", 1248422: "Well Fed"},
                  [eff(1248401, 0, 0, effect=64, trigger=1131), eff(1248401, 227, 20, trigger=1248422),
                   eff(1248380, 0, 0, effect=64, trigger=1131), eff(1248380, 227, low, trigger=1248422),
                   eff(1131, 84, 358), eff(1248422, 29, 1, misc=0), eff(1248422, 29, 1, misc=2)],
                  {1248401: 10, 1248380: 10, 1131: 30, 1248422: 900},
                  items=[(20452, cls, sub, 0, 45, [1248401]), (2681, cls, sub, 0, 1, [1248380])])


def test_food_tiers_are_separate_buffs_with_own_value_level_and_items():
    buffs, unclassified = extract_buffs(_food_tiers(), {1248422})
    assert sorted(buffs) == [1248380, 1248401] and unclassified == []
    hi, lo = buffs[1248401], buffs[1248380]
    assert (hi.name, hi.cat, hi.fx) == ("Well Fed", "FOOD", {"STR": 20, "STA": 20})
    assert (hi.items, hi.lvl, hi.dur) == ([20452], 45, 900)
    assert (lo.fx, lo.items, lo.lvl) == ({"STR": 1, "STA": 1}, [2681], 1)
    assert hi.excl == lo.excl == "FOOD:Well Fed"
    assert hi.new is True and hi.burst is False


def test_food_tier_with_non_positive_value_dropped():
    buffs, _ = extract_buffs(_food_tiers(low=0), set())
    assert sorted(buffs) == [1248401]


def test_value_pass_through_only_for_food():
    # the same wiring on a potion keeps the template's own values under the template id
    buffs, _ = extract_buffs(_food_tiers(cls=0, sub=1), set())
    assert list(buffs) == [1248422] and buffs[1248422].fx == {"STR": 1, "STA": 1}
    assert buffs[1248422].cat == "POTION"


def test_short_mana_or_health_channel_dropped_in_any_category():
    # e.g. Drink 1135 on a non-food item, Dreamless Sleep, Second Wind, Dark Sacrifice
    t = tables({1135: "Drink", 15822: "Dreamless Sleep", 1277328: "Dark Sacrifice", 17627: "Distilled Wisdom"},
               [eff(1135, 24, 10, misc=0, period=1000), eff(15822, 84, 50), eff(1277328, 24, 320, period=3000),
                eff(17627, 418, 2000)],
               {1135: 30, 15822: 12, 1277328: 15, 17627: 7200},
               items=[(4696, 4, 0, 12, 1, [1135]), (12190, 0, 1, 0, 1, [15822]), (13511, 0, 3, 0, 50, [17627])],
               class_sets={1277328: 6})
    buffs, unclassified = extract_buffs(t, set())
    assert list(buffs) == [17627] and unclassified == []


def test_own_class_toggle_with_no_duration_is_class_buff():
    # Aspect of the Hawk: no duration, not passive, Effect 6 on the caster
    t = tables({13165: "Aspect of the Hawk", 25296: "Aspect of the Hawk"},
               [eff(13165, 124, 20) | {"ImplicitTarget_0": "1"}, eff(25296, 124, 120) | {"ImplicitTarget_0": "1"}],
               {13165: -1, 25296: -1}, class_sets={13165: 9, 25296: 9}, levels={13165: 10, 25296: 60})
    b = extract_buffs(t, set())[0][25296]
    assert (b.cat, b.cls, b.fx, b.dur, b.burst, b.lvl) == ("CLASS", "HUNTER", {"RAP": 120}, 0, False, 10)


def test_passive_and_area_toggles_excluded():
    t = tables({5000: "Passive Thing", 1032: "Devotion Aura"},
               [eff(5000, 99, 10) | {"ImplicitTarget_0": "1"}, eff(1032, 674, 505, misc=1, effect=35)],
               {5000: -1, 1032: -1}, class_sets={5000: 4, 1032: 10}, attrs={5000: 0x40})
    assert extract_buffs(t, set()) == ({}, [])


def test_shaman_imbue_effect_360_is_class_buff():
    # Forever Rockbiter Weapon: no class set; class from the trainer row's ClassMask (64 = shaman);
    # Effect 360 names the enchant, whose equip spell carries the attack power.
    ench = [{"ID": "1664", "Duration": "3600", "Effect_0": "3", "EffectArg_0": "16313", "EffectPointsMin_0": "0",
             "Effect_1": "0", "EffectArg_1": "0", "EffectPointsMin_1": "0",
             "Effect_2": "0", "EffectArg_2": "0", "EffectPointsMin_2": "0"}]
    t = tables({16316: "Rockbiter Weapon", 16313: "Rockbiter 7"},
               [eff(16316, 0, 1800, misc=1664, effect=360), eff(16313, 99, 72)],
               {16316: 0, 16313: 0}, levels={16316: 54}, enchants=ench, class_masks={16316: 64})
    b = extract_buffs(t, set())[0][16316]
    assert (b.cat, b.cls, b.fx, b.enchant, b.dur, b.burst) == ("CLASS", "SHAMAN", {"AP": 72}, 1664, 3600, False)


def test_item_imbue_effect_360_is_weapon():
    ench = [{"ID": "7000", "Duration": "1800", "Effect_0": "5", "EffectArg_0": "4", "EffectPointsMin_0": "8",
             "Effect_1": "0", "EffectArg_1": "0", "EffectPointsMin_1": "0",
             "Effect_2": "0", "EffectArg_2": "0", "EffectPointsMin_2": "0"}]
    t = tables({9100: "Imbue Striking"}, [eff(9100, 0, 0, misc=7000, effect=360)], {9100: 0},
               items=[(9101, 0, 8, 0, 20, [9100])], enchants=ench)
    b = extract_buffs(t, set())[0][9100]
    assert (b.cat, b.fx, b.enchant) == ("WEAPON", {"STR": 8}, 7000)


def test_food_tiers_carry_the_template_aura():
    buffs, _ = extract_buffs(_food_tiers(), set())
    assert buffs[1248401].aura == 1248422 and buffs[1248380].aura == 1248422


def test_plain_buffs_have_no_aura_and_are_not_self_only():
    t = tables({17538: "Elixir of the Mongoose"}, [eff(17538, 29, 25, misc=1)], {17538: 3600},
               items=[(13452, 0, 2, 0, 46, [17538])])
    b = extract_buffs(t, set())[0][17538]
    assert b.aura is None and b.self_only is False


def test_self_only_class_buffs():
    # caster-only effects (Inner Fire, armors, aspects) -> self_only; castable on others -> not
    t = tables({10952: "Inner Fire", 10938: "Power Word: Fortitude", 25289: "Battle Shout",
                25296: "Aspect of the Hawk"},
               [eff(10952, 22, 1395, misc=1) | {"ImplicitTarget_0": "1"},
                eff(10938, 29, 70, misc=2) | {"ImplicitTarget_0": "21"},
                eff(25289, 99, 139) | {"ImplicitTarget_0": "20"},
                eff(25296, 124, 120) | {"ImplicitTarget_0": "1"}],
               {10952: 600, 10938: 3600, 25289: 180, 25296: -1},
               class_sets={10952: 6, 10938: 6, 25289: 4, 25296: 9})
    buffs, _ = extract_buffs(t, set())
    assert {sid: b.self_only for sid, b in buffs.items()} == \
        {10952: True, 10938: False, 25289: False, 25296: True}


def test_class_imbue_is_self_only():
    ench = [{"ID": "1664", "Duration": "3600", "Effect_0": "3", "EffectArg_0": "16313", "EffectPointsMin_0": "0",
             "Effect_1": "0", "EffectArg_1": "0", "EffectPointsMin_1": "0",
             "Effect_2": "0", "EffectArg_2": "0", "EffectPointsMin_2": "0"}]
    t = tables({16316: "Rockbiter Weapon", 16313: "Rockbiter 7"},
               [eff(16316, 0, 1800, misc=1664, effect=360), eff(16313, 99, 72)],
               {16316: 0, 16313: 0}, levels={16316: 54}, enchants=ench, class_masks={16316: 64})
    assert extract_buffs(t, set())[0][16316].self_only is True
