BUFFS = """
ns.Buffs = {
  [100] = {name="Rank Buff", cat="CLASS", fx={STA=10}, lvl=1, ranks={{spell=101, lvl=1, fx={STA=5}}, {spell=100, lvl=10, fx={STA=10}}}},
  [200] = {name="Food A", cat="FOOD", fx={STR=8}, lvl=10, aura=999},
  [201] = {name="Food B", cat="FOOD", fx={STR=12}, lvl=30, aura=999},
  [202] = {name="Food C", cat="FOOD", fx={STR=20}, lvl=50, aura=999},
  [300] = {name="Oil", cat="WEAPON", fx={SPELL_DMG=8}, lvl=1, enchant=1803},
}
"""


def make(addon, mocks=None, buffs=True):
    a = addon(mocks=mocks)
    if buffs:
        a.run(BUFFS)
    return a


def trees(p1, p2, p3):
    return lambda i: (0, "n", "", "", "DAMAGER", 0, (p1, p2, p3)[i - 1])


def aura(**kw):
    return lambda unit, i, flt: [kw][i - 1] if i == 1 else None


def auras(*items):
    return lambda unit, i, flt: items[i - 1] if i <= len(items) else None


def test_spec_from_most_points(addon):
    a = make(addon, {"GetSpecializationInfo": trees(5, 31, 10)})
    s = a.eval("ns.PlayerState:Refresh()")
    assert s["spec"] == 2 and s["specAuto"] is True


def test_spec_override_wins(addon):
    a = make(addon, {"GetSpecializationInfo": trees(5, 31, 10)})
    a.run("ns.CharDB = {specOverride = 3}")
    s = a.eval("ns.PlayerState:Refresh()")
    assert s["spec"] == 3


def test_low_points_spec_auto_false(addon):
    a = make(addon, {"GetSpecializationInfo": trees(3, 4, 2)})
    s = a.eval("ns.PlayerState:Refresh()")
    assert s["spec"] == 1 and s["specAuto"] is False


def test_stats_and_ratios(addon):
    a = make(addon, {
        "UnitStat": lambda unit, i: (0, 10 * i, 0, 0),
        "UnitAttackPower": lambda unit: (100, 20, -5),
        "GetSpellBonusDamage": lambda school: school * 10,
        "GetAttackPowerForStat": lambda stat, v: 2 if stat == 1 else 1,
        "GetCritChanceFromAgility": lambda unit: 4.0,
        "GetSpellCritChanceFromIntellect": lambda unit: 5.0,
    })
    s = a.eval("ns.PlayerState:Refresh()")
    st = s["stats"]
    assert st["STR"] == 10 and st["SPI"] == 50 and st["AP"] == 115 and st["SPELL_DMG"] == 70
    r = s["ratios"]
    assert r["apPerStr"] == 2 and r["apPerAgi"] == 1
    assert r["critPerAgi"] == 4.0 / 20 and r["spellCritPerInt"] == 5.0 / 40
    assert r["hpPerSta"] == 10 and r["manaPerInt"] == 15
    assert s["class"] == "WARRIOR" and s["level"] == 60


def test_missing_ratio_api_gives_nil(addon):
    a = make(addon, {"GetAttackPowerForStat": None, "GetCritChanceFromAgility": None,
                     "GetSpellCritChanceFromIntellect": None, "GetHitModifier": None})
    s = a.eval("ns.PlayerState:Refresh()")
    r = s["ratios"]
    assert r["apPerStr"] is None and r["apPerAgi"] is None
    assert r["critPerAgi"] is None and r["spellCritPerInt"] is None
    assert r["hpPerSta"] == 10
    assert s["stats"]["HIT"] is None


def test_active_matches_lower_rank(addon):
    a = make(addon, {"C_UnitAuras.GetAuraDataByIndex": auras({"spellId": 101, "name": "R1"})})
    s = a.eval("ns.PlayerState:Refresh()")
    assert s["active"][100] is True and s["activeAura"][100] == 101
    assert len(list(s["unknownAuras"].keys())) == 0


def test_unknown_aura_recorded(addon):
    a = make(addon, {"C_UnitAuras.GetAuraDataByIndex": auras({"spellId": 4242, "name": "Mystery"})})
    s = a.eval("ns.PlayerState:Refresh()")
    assert s["unknownAuras"][4242] == "Mystery"
    assert s["active"][4242] is None


def test_weapon_enchant_active(addon):
    a = make(addon, {"GetWeaponEnchantInfo": lambda: (True, 1000, 0, 1803, False, 0, 0, None)})
    s = a.eval("ns.PlayerState:Refresh()")
    assert s["active"][300] is True


def test_shared_aura_picked_by_points(addon):
    a = make(addon, {"C_UnitAuras.GetAuraDataByIndex":
                     auras({"spellId": 999, "name": "Well Fed", "points": [0, 12]})})
    s = a.eval("ns.PlayerState:Refresh()")
    assert s["active"][201] is True and s["active"][200] is None and s["active"][202] is None
    assert s["activeAura"][201] == 999


def test_shared_aura_falls_back_to_level(addon):
    # no points -> highest tier with lvl <= player level (60 -> tier C)
    a = make(addon, {"C_UnitAuras.GetAuraDataByIndex": auras({"spellId": 999, "name": "Well Fed"})})
    s = a.eval("ns.PlayerState:Refresh()")
    assert s["active"][202] is True and s["active"][201] is None
    # unmatched points at level 35 -> tier B
    b = make(addon, {"UnitLevel": lambda unit: 35, "C_UnitAuras.GetAuraDataByIndex":
                     auras({"spellId": 999, "name": "Well Fed", "points": [77]})})
    s = b.eval("ns.PlayerState:Refresh()")
    assert s["active"][201] is True and s["active"][202] is None


def test_secret_points_keeps_snapshot_stale(addon):
    a = make(addon, {"C_UnitAuras.GetAuraDataByIndex": auras({"spellId": 101, "name": "R1"})})
    a.run("ns.PlayerState:Refresh()")
    a.mock("issecretvalue", lambda v: v == 12)
    a.mock("C_UnitAuras.GetAuraDataByIndex",
           auras({"spellId": 999, "name": "Well Fed", "points": [12]}))
    s = a.eval("ns.PlayerState:Refresh()")
    assert s["stale"] is True and s["active"][100] is True and s["active"][201] is None


def test_rap_per_agi_by_class(addon):
    for cls, want in (("HUNTER", 2), ("WARRIOR", 1), ("ROGUE", 1), ("MAGE", 0)):
        a = make(addon, {"UnitClass": lambda unit, c=cls: (c.title(), c, 1)})
        assert a.eval("ns.PlayerState:Refresh()")["ratios"]["rapPerAgi"] == want


def test_secret_ratio_keeps_snapshot_stale(addon):
    for name in ("GetAttackPowerForStat", "GetCritChanceFromAgility", "GetSpellCritChanceFromIntellect"):
        a = make(addon, {"issecretvalue": lambda v: v == 777, name: lambda *args: 777})
        s = a.eval("ns.PlayerState:Refresh()")
        assert s["stale"] is True, name


def test_combat_keeps_snapshot_stale(addon):
    a = make(addon, {"C_UnitAuras.GetAuraDataByIndex": auras({"spellId": 101, "name": "R1"})})
    a.run("ns.PlayerState:Refresh()")
    a.mock("InCombatLockdown", lambda: True)
    a.mock("C_UnitAuras.GetAuraDataByIndex", auras())
    a.mock("UnitStat", lambda unit, i: (0, 999, 0, 0))
    s = a.eval("ns.PlayerState:Refresh()")
    assert s["stale"] is True and s["active"][100] is True and s["stats"]["STR"] == 100
    a.mock("InCombatLockdown", lambda: False)
    s = a.eval("ns.PlayerState:Refresh()")
    assert s["stale"] is False and s["active"][100] is None and s["stats"]["STR"] == 999


def test_secret_value_keeps_snapshot_stale(addon):
    a = make(addon, {"C_UnitAuras.GetAuraDataByIndex": auras({"spellId": 101, "name": "R1"})})
    a.run("ns.PlayerState:Refresh()")
    a.mock("issecretvalue", lambda v: v == 555)
    a.mock("C_UnitAuras.GetAuraDataByIndex", auras({"spellId": 555, "name": "X"}))
    s = a.eval("ns.PlayerState:Refresh()")
    assert s["stale"] is True and s["active"][100] is True


def test_refresh_fires_event_and_events_debounce(addon):
    a = make(addon)
    a.run("n = 0; ns.Events:On('FULLBUFF_STATE', function() n = n + 1 end)")
    a.fire_event("UNIT_AURA", "target")
    a.flush_timers()
    assert a.eval("n") == 0
    a.fire_event("UNIT_AURA", "player")
    a.fire_event("PLAYER_LEVEL_UP")
    a.fire_event("PLAYER_EQUIPMENT_CHANGED")
    a.flush_timers()
    assert a.eval("n") == 1
    assert a.errors() == []
