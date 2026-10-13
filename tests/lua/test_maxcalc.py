"""MaxCalc tests. Every expected number is worked out by hand in the comments.

Common fixture (unless a test overrides it):
  WARRIOR spec 1, weights AP=1, HP=0.5, ARMOR=0.1, CRIT=10
  ratios apPerStr=2, critPerAgi=0.04, hpPerSta=10, manaPerInt=15 (apPerAgi nil)
  stats STR 100, AGI 50, STA 80, INT 20, SPI 30, AP 200, ARMOR 1000, HP 800, CRIT 5.0
  RelevantStats -> STR (AP), AGI (CRIT, ARMOR x2), STA (HP), AP, ARMOR, HP, CRIT
"""
import pytest

WEIGHTS = "ns.Weights = {WARRIOR = {{AP=1, HP=0.5, ARMOR=0.1, CRIT=10}, {AP=1}, {AP=1}}}"

BASE_STATS = dict(STR=100, AGI=50, STA=80, INT=20, SPI=30, AP=200, ARMOR=1000, HP=800, CRIT=5.0)


def lua_tbl(d):
    return "{" + ", ".join("%s=%r" % (k, v) for k, v in d.items()) + "}"


def make_state(stats=None, active=(), stale=False, unknown=None):
    s = dict(BASE_STATS)
    s.update(stats or {})
    act = "{" + ", ".join("[%d]=true" % i for i in active) + "}"
    unk = "{" + ", ".join("[%d]=%r" % (k, v) for k, v in (unknown or {}).items()) + "}"
    return ("{class='WARRIOR', spec=1, level=60, stale=%s, stats=%s, active=%s, unknownAuras=%s,"
            " ratios={apPerStr=2, critPerAgi=0.04, hpPerSta=10, manaPerInt=15}}"
            % ("true" if stale else "false", lua_tbl(s), act, unk))


ENTRY_FN = """
local function E(id, cat, name, excl, fx, status, burst)
  return {id=id, cat=cat, name=name, excl=excl, fx=fx, status=status or "CAN_ADD", burst=burst}
end
"""


def compute(addon, state, entries, db=None):
    """entries: Lua list body of E(...) calls. Groups them by cat into a catalog."""
    a = addon()
    a.run(WEIGHTS)
    if db is not None:
        a.run("ns.DB = %s" % db)
    a.run("__ns.__st = %s" % state)
    a.run(ENTRY_FN + """
local list = {%s}
local cat = {order = {}}
for _, e in ipairs(list) do
  if not cat[e.cat] then cat[e.cat] = {}; table.insert(cat.order, e.cat) end
  table.insert(cat[e.cat], e)
end
__ns.__cat = cat
""" % entries)
    # Compute runs Scoring:MarkRecommended itself (R3).
    a.run("__ns.__res = ns.MaxCalc:Compute(__ns.__st, __ns.__cat)")
    res = a.eval("__ns.__res")
    rows = {}
    order = []
    for r in res["rows"].values():
        rows[r["stat"]] = (r["current"], r["max"], r["diff"])
        order.append(r["stat"])
    missing = [m["id"] for m in res["missing"].values()]
    return a, res, rows, order, missing


def pct(*pairs):
    vals = [min(c / m, 1) for c, m in pairs if m > 0]
    return sum(vals) / len(vals) * 100 if vals else 100


def test_no_active_buffs_max_equals_current_plus_best(addon):
    # food group: A {STR=10} (score 20) beats B {STR=5}; elixir C {AGI=20}.
    # STR 100 -> 110 (+10); AGI 50 -> 70 (+20)
    # AP 200 + 10*2 = 220; CRIT 5 + 20*0.04 = 5.8; ARMOR 1000 + 20*2 = 1040
    # STA/HP unchanged. missing sorted by category order: ELIXIR (C) before FOOD (A)
    _, res, rows, order, missing = compute(addon, make_state(), """
      E(1, "FOOD", "Food A", "food", {STR=10}),
      E(2, "FOOD", "Food B", "food", {STR=5}),
      E(3, "ELIXIR", "Elixir C", "elixir", {AGI=20}),
    """)
    assert order == ["STR", "AGI", "STA", "AP", "ARMOR", "HP", "CRIT"]
    assert rows["STR"] == (100, 110, 10)
    assert rows["AGI"] == (50, 70, 20)
    assert rows["STA"] == (80, 80, 0)
    assert rows["AP"] == (200, 220, 20)
    assert rows["ARMOR"] == (1000, 1040, 40)
    assert rows["HP"] == (800, 800, 0)
    assert rows["CRIT"] == (5.0, 5.8, pytest.approx(0.8))
    assert missing == [3, 1] and res["missingCount"] == 2
    # mean(100/110, 50/70, 1, 200/220, 1000/1040, 1, 5/5.8) * 100
    assert res["percentOfMax"] == pytest.approx(
        pct((100, 110), (50, 70), (80, 80), (200, 220), (1000, 1040), (800, 800), (5, 5.8)))
    assert res["stale"] is False


def test_active_flat_subtracted_not_double_counted(addon):
    # Food A {STR=10} is ACTIVE: stats STR 110, AP 220 already include it.
    # base STR = 110 - 10 = 100; max = 100 + 10 = 110 -> diff 0, AP diff 0.
    _, res, rows, _, missing = compute(addon, make_state({"STR": 110, "AP": 220}, active=[1]), """
      E(1, "FOOD", "Food A", "food", {STR=10}, "ACTIVE"),
      E(2, "FOOD", "Food B", "food", {STR=5}),
    """)
    assert rows["STR"] == (110, 110, 0)
    assert rows["AP"] == (220, 220, 0)
    assert missing == [] and res["missingCount"] == 0
    assert res["percentOfMax"] == pytest.approx(100)


def test_kings_percent_applied_to_primary(addon):
    # Not active: Kings {STAT_PCT=10} + food {STR=10}
    # STR (100+10)*1.1 = 121 (+21) -> AP 200 + 42 = 242
    # AGI 50*1.1 = 55 (+5) -> CRIT 5 + 0.2 = 5.2, ARMOR 1000 + 10 = 1010
    # STA 80*1.1 = 88 (+8) -> HP 800 + 80 = 880
    entries = """
      E(20, "CLASS", "Kings", "kings", {STAT_PCT=10}, %s),
      E(1, "FOOD", "Food A", "food", {STR=10}),
    """
    _, _, rows, _, missing = compute(addon, make_state(), entries % '"CAN_ADD"')
    assert rows["STR"] == (100, 121, 21)
    assert rows["AGI"] == (50, 55, 5)
    assert rows["STA"] == (80, 88, 8)
    assert rows["AP"] == (200, 242, 42)
    assert rows["CRIT"] == (5.0, 5.2, pytest.approx(0.2))
    assert rows["ARMOR"] == (1000, 1010, 10)
    assert rows["HP"] == (800, 880, 80)
    assert missing == [20, 1]
    # Kings ACTIVE: stats STR 110, AGI 55, STA 88 (and derived AP 220, CRIT 5.2, ARMOR 1010, HP 880)
    # base STR = 110/1.1 - 0 = 100 -> max (100+10)*1.1 = 121 (+11) -> AP 220 + 22 = 242
    st = make_state({"STR": 110, "AGI": 55, "STA": 88, "AP": 220, "CRIT": 5.2, "ARMOR": 1010,
                     "HP": 880}, active=[20])
    _, _, rows, _, missing = compute(addon, st, entries % '"ACTIVE"')
    assert rows["STR"] == (110, 121, 11)
    assert rows["AGI"] == (55, 55, 0)
    assert rows["AP"] == (220, 242, 22)
    assert rows["CRIT"] == (5.2, 5.2, 0)
    assert missing == [1]


def test_stat_pct_and_single_primary_pct_multiply(addon):
    # Kings {STAT_PCT=10} and {STR_PCT=10} in different groups (multiplicative):
    # STR 100*1.1*1.1 = 121 (+21) -> AP 242; AGI 55 (only STAT_PCT)
    _, _, rows, _, _ = compute(addon, make_state(), """
      E(20, "CLASS", "Kings", "kings", {STAT_PCT=10}),
      E(21, "WORLD", "Strength Pct", "strpct", {STR_PCT=10}),
    """)
    assert rows["STR"] == (100, 121, 21)
    assert rows["AGI"] == (50, 55, 5)
    assert rows["AP"] == (200, 242, 42)


def test_same_group_counts_once(addon):
    # A {AP=40} and B {AP=30} share "food": max AP = 200 + 40 = 240 (not 270)
    _, res, rows, _, missing = compute(addon, make_state(), """
      E(1, "FOOD", "Food A", "food", {AP=40}),
      E(2, "FOOD", "Food B", "food", {AP=30}),
    """)
    assert rows["AP"] == (200, 240, 40)
    assert missing == [1] and res["missingCount"] == 1


def test_camp_buff_and_class_buff_share_group(addon):
    # Camp buff {AP=60} ACTIVE (AP 260 = 200 + 60), Battle Shout {AP=100} CAN_ADD, same group.
    # Swap: max AP = 260 - 60 + 100 = 300 (+40); missing = Battle Shout only.
    _, res, rows, _, missing = compute(addon, make_state({"AP": 260}, active=[31]), """
      E(30, "CLASS", "Battle Shout", "shout", {AP=100}),
      E(31, "CAMPING", "Camp Shout", "shout", {AP=60}, "ACTIVE"),
    """)
    assert rows["AP"] == (260, 300, 40)
    assert missing == [30]


def test_active_percent_swapped_for_better_in_group(addon):
    # Lesser {STAT_PCT=5} ACTIVE: STR 105, AGI 52.5, STA 84, and derived from those +5%:
    # AP 200 + 5*2 = 210, HP 800 + 4*10 = 840, CRIT 5 + 2.5*0.04 = 5.1, ARMOR 1000 + 2.5*2 = 1005.
    # Greater {STAT_PCT=10} CAN_ADD same group is recommended.
    # base STR = 105/1.05 = 100 -> max 110 (+5) -> AP 210 + 10 = 220
    # base AGI = 52.5/1.05 = 50 -> max 55 (+2.5) -> CRIT 5.1 + 0.1 = 5.2, ARMOR 1005 + 5 = 1010
    # STA 84 -> 88 (+4) -> HP 840 + 40 = 880
    st = make_state({"STR": 105, "AGI": 52.5, "STA": 84, "AP": 210, "HP": 840, "CRIT": 5.1,
                     "ARMOR": 1005}, active=[40])
    _, _, rows, _, missing = compute(addon, st, """
      E(40, "SCROLL", "Lesser", "pct", {STAT_PCT=5}, "ACTIVE"),
      E(41, "CLASS", "Greater", "pct", {STAT_PCT=10}),
    """)
    assert rows["STR"] == (105, 110, 5)
    assert rows["AP"] == (210, 220, 10)
    assert rows["STA"] == (84, 88, 4)
    assert rows["HP"] == (840, 880, 40)
    assert rows["AGI"][1] == 55
    assert rows["CRIT"] == (5.1, 5.2, pytest.approx(0.1))
    assert rows["ARMOR"] == (1005, 1010, 5)
    assert missing == [41]


def test_armor_pct_and_derived_armor(addon):
    # Active {ARMOR_PCT=10}: ARMOR 1100. CAN_ADD {ARMOR=100} and elixir {AGI=10}.
    # armorBase = 1100/1.1 - 0 = 1000; max = (1000 + 100 + 10*2) * 1.1 = 1232 (+132)
    st = make_state({"ARMOR": 1100}, active=[50])
    _, _, rows, _, missing = compute(addon, st, """
      E(50, "ELIXIR", "Armor Pct", "armorpct", {ARMOR_PCT=10}, "ACTIVE"),
      E(51, "SCROLL", "Protection", "prot", {ARMOR=100}),
      E(52, "ELIXIR", "Agility", "agi", {AGI=10}),
    """)
    assert rows["ARMOR"] == (1100, 1232, 132)
    assert missing == [52, 51]


def test_burst_ignored(addon):
    # Burst potion {AP=500} CAN_ADD: never chosen -> max AP stays 200.
    _, res, rows, _, missing = compute(addon, make_state(), """
      E(60, "POTION", "Rage Potion", "potion", {AP=500}, "CAN_ADD", true),
    """)
    assert rows["AP"] == (200, 200, 0) and missing == []


def test_active_burst_stays_in_baseline(addon):
    # Burst potion {AP=500} ACTIVE: AP 700 = 200 + 500. Not subtracted, not re-added:
    # max AP = 700 - 0 + 0 = 700, diff 0 (never negative).
    _, _, rows, _, missing = compute(addon, make_state({"AP": 700}, active=[60]), """
      E(60, "POTION", "Rage Potion", "potion", {AP=500}, "ACTIVE", true),
    """)
    assert rows["AP"] == (700, 700, 0) and missing == []


def test_active_zero_score_buff_not_subtracted(addon):
    # Arcane Intellect {INT=31} ACTIVE on a Warrior: score 0 (no INT/MANA weight), so its group has
    # no chosen entry. It stays in the baseline: INT 51 -> 51, MANA 1000 -> 1000.
    st = make_state({"INT": 51, "MANA": 1000}, active=[70])
    _, _, rows, _, missing = compute(addon, st, """
      E(70, "CLASS", "Arcane Intellect", "int", {INT=31}, "ACTIVE"),
    """, db="{showAllStats=true}")
    assert rows["INT"] == (51, 51, 0)
    assert rows["MANA"] == (1000, 1000, 0)
    assert missing == []


def test_unknown_aura_not_subtracted(addon):
    # Unknown aura gives AP 50 (AP 250); nothing in the catalog -> max AP stays 250.
    _, res, rows, _, missing = compute(
        addon, make_state({"AP": 250}, unknown={12345: "Mystery"}), "")
    assert rows["AP"] == (250, 250, 0)
    assert missing == [] and res["percentOfMax"] == pytest.approx(100)


def test_derived_ap_from_str_delta(addon):
    # {STR=20} -> AP +40; {AGI=10} -> CRIT +0.4, ARMOR +20, AP +0 (apPerAgi nil);
    # {STA=10} -> HP +100
    _, _, rows, _, _ = compute(addon, make_state(), """
      E(1, "FOOD", "Str Food", "food", {STR=20}),
      E(2, "ELIXIR", "Agi Elixir", "elixir", {AGI=10}),
      E(3, "SCROLL", "Sta Scroll", "scroll", {STA=10}),
    """)
    assert rows["AP"] == (200, 240, 40)
    assert rows["CRIT"] == (5.0, 5.4, pytest.approx(0.4))
    assert rows["ARMOR"] == (1000, 1020, 20)
    assert rows["HP"] == (800, 900, 100)


def test_rounding_output_only(addon):
    # STR 104, AGI 51 with Kings: STR 114.4 -> 114 (+10);
    # AP 200 + 10.4*2 = 220.8 -> 221 (+21). Rounding STR first would give 200 + 10*2 = 220.
    # AGI 56.1 -> 56; CRIT 5 + 5.1*0.04 = 5.204 -> 5.2
    _, _, rows, _, _ = compute(addon, make_state({"STR": 104, "AGI": 51}), """
      E(20, "CLASS", "Kings", "kings", {STAT_PCT=10}),
    """)
    assert rows["STR"] == (104, 114, 10)
    assert rows["AP"] == (200, 221, 21)
    assert rows["AGI"] == (51, 56, 5)
    assert rows["CRIT"] == (5.0, 5.2, pytest.approx(0.2))


def test_stale_passthrough_and_all_stats(addon):
    _, res, rows, order, _ = compute(addon, make_state(stale=True), "", db="{showAllStats=true}")
    assert res["stale"] is True
    assert order == ["STR", "AGI", "STA", "INT", "SPI", "AP", "ARMOR", "HP", "CRIT"]
    assert rows["INT"] == (20, 20, 0)


def test_percent_skips_zero_max_and_empty_is_100(addon):
    # HIT weighted but no HIT stat or buff: row (0, 0, 0) skipped in percent.
    a = addon()
    a.run("ns.Weights = {WARRIOR = {{HIT=1}, {}, {}}}")
    a.run("__ns.__st = {class='WARRIOR', spec=1, stats={}, ratios={}, active={}, stale=false}")
    res = a.eval("ns.MaxCalc:Compute(__ns.__st, {order={}})")
    r = res["rows"][1]
    assert (r["stat"], r["current"], r["max"], r["diff"]) == ("HIT", 0, 0, 0)
    assert res["percentOfMax"] == 100 and res["missingCount"] == 0


def test_active_lower_rank_subtracts_its_own_fx_and_counts_as_missing(addon):
    # Fortitude rank 3 (STA 20) active, rank 6 (STA 54) chosen. STA 80 includes the 20:
    # base 60 -> max 60 + 54 = 114; HP 800 - 0 + 34*10 = 1140 (derived from the STA delta).
    _, res, rows, _, missing = compute(addon, make_state(), """
      (function() local e = E(7, "CLASS", "Fortitude", "fort", {STA=54}, "CAN_ADD")
        e.activeFx = {STA=20}; return e end)(),
    """)
    assert rows["STA"][:2] == (80, 114)
    assert rows["HP"][:2] == (800, 1140)
    assert missing == [7]


def _healer(addon, entries):
    a = addon()
    a.run("ns.Weights = {PRIEST = {{HEAL=1, MP5=2.5}, {HEAL=1}, {HEAL=1}}}")
    a.run("__ns.__st = {class='PRIEST', spec=1, level=60, stale=false, active={}, unknownAuras={},"
          " stats={STR=30, AGI=30, STA=60, INT=150, SPI=150, HEAL=300}, ratios={hpPerSta=10, manaPerInt=15}}")
    a.run(ENTRY_FN + "__ns.__cat = {order={'CLASS'}, CLASS={%s}}" % entries)
    res = a.eval("ns.MaxCalc:Compute(__ns.__st, __ns.__cat)")
    return {r["stat"]: (r["current"], r["max"]) for r in res["rows"].values()}


def test_unreported_mp5_current_is_active_known_fx(addon):
    # The client reports no MP5: current = Blessing of Wisdom's 30 (active), the best
    # in its group, so max = 30 - 30 + 30 = 30, never 0.
    rows = _healer(addon, 'E(1, "CLASS", "Blessing of Wisdom", "wis", {MP5=30}, "ACTIVE")')
    assert rows["MP5"] == (30, 30)


def test_unreported_mp5_active_weaker_replaced_by_best(addon):
    # active 20 (lower blessing), best 30 in the same group; an unrelated active 5 stays
    # current 25 -> max 25 - 20 + 30 = 35
    rows = _healer(addon, """
      E(1, "CLASS", "Weak", "wis", {MP5=20}, "ACTIVE"),
      E(2, "CLASS", "Strong", "wis", {MP5=30}),
      E(3, "CLASS", "Other", "other", {MP5=5}, "ACTIVE", true),
    """)
    assert rows["MP5"] == (25, 35)


# --- picks (buff sets) ---
def compute_picks(addon, entries, picks):
    a = addon()
    a.run(WEIGHTS)
    a.run("__ns.__st = %s" % make_state(active=(1,)))
    a.run(ENTRY_FN + """
local list = {%s}
local cat = {order = {}}
for _, e in ipairs(list) do
  if not cat[e.cat] then cat[e.cat] = {}; table.insert(cat.order, e.cat) end
  table.insert(cat[e.cat], e)
end
__ns.__res = ns.MaxCalc:Compute(__ns.__st, cat, %s)
""" % (entries, picks))
    res = a.eval("__ns.__res")
    return {r["stat"]: (r["current"], r["max"]) for r in res["rows"].values()}, res


def test_picks_override_recommendation(addon):
    # A {STR=10} is recommended; picking B {STR=5}: STR 100 -> 105
    rows, _ = compute_picks(addon, """
      E(1, "FOOD", "A", "food", {STR=10}),
      E(2, "FOOD", "B", "food", {STR=5}),""", "{food=2}")
    assert rows["STR"] == (100, 105)


def test_pick_not_used_keeps_active_buff(addon):
    # active A {STR=10} is inside the 100; group set to false -> A stays, max == current
    rows, res = compute_picks(addon, """
      E(1, "FOOD", "A", "food", {STR=10}, "ACTIVE"),
      E(2, "FOOD", "B", "food", {STR=5}),""", "{food=false}")
    assert rows["STR"] == (100, 100)
    assert res["missingCount"] == 0


def test_unavailable_pick_ignored(addon):
    rows, _ = compute_picks(addon, """
      E(1, "FOOD", "A", "food", {STR=10}, "UNAVAILABLE"),""", "{food=1}")
    assert rows["STR"] == (100, 100)


def test_burst_pick_ignored(addon):
    rows, _ = compute_picks(addon, """
      E(1, "FOOD", "A", "food", {STR=10}, "CAN_ADD", true),""", "{food=1}")
    assert rows["STR"] == (100, 100)


def test_empty_picks_max_equals_current(addon):
    rows, res = compute_picks(addon, """
      E(1, "FOOD", "A", "food", {STR=10}),
      E(2, "ELIXIR", "C", "elixir", {AGI=20}),""", "{}")
    assert all(c == m for c, m in rows.values())
    assert res["missingCount"] == 0


def test_pick_matched_by_id_not_slot_key(addon):
    rows, _ = compute_picks(addon, """
      E(1, "FOOD", "A", "food", {STR=10}),""", "{oldslot=1}")
    assert rows["STR"] == (100, 110)


def test_two_picks_in_one_group_best_counts(addon):
    rows, _ = compute_picks(addon, """
      E(1, "FOOD", "A", "food", {STR=10}),
      E(2, "FOOD", "B", "food", {STR=5}),""", "{s1=2, s2=1}")
    assert rows["STR"] == (100, 110)


def test_picked_active_entry_max_equals_current(addon):
    rows, res = compute_picks(addon, """
      E(1, "FOOD", "A", "food", {STR=10}, "ACTIVE"),""", "{food=1}")
    assert rows["STR"] == (100, 100)
    assert res["missingCount"] == 0


def test_picked_upgrade_replaces_active_lower_rank(addon):
    # lower rank active {STR=4} (in the 100); rank up fx {STR=10}: 100 - 4 + 10
    rows, _ = compute_picks(addon, """
      {id=1, cat="FOOD", name="A", excl="food", fx={STR=10}, activeFx={STR=4}, status="CAN_ADD"},""", "{food=1}")
    assert rows["STR"] == (100, 106)


def test_active_in_group_of_other_pick_is_swapped(addon):
    # active A {STR=10} is inside the 100; picking B {STR=5}: 100 - 10 + 5
    rows, _ = compute_picks(addon, """
      E(1, "FOOD", "A", "food", {STR=10}, "ACTIVE"),
      E(2, "FOOD", "B", "food", {STR=5}),""", "{food=2}")
    assert rows["STR"] == (100, 95)
