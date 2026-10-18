"""ViewModel tests. Fixture: WARRIOR spec 2, weights AP=1, ratio apPerStr=2.

Catalog: 1 Apple (s1, ACTIVE, STR 5), 2 Bravo (s2, CAN_ADD, STR 20), 3 Zulu (s3, UNAVAILABLE),
         6 Rage / 7 Haste (burst potions).
Bags: buff 2 -> 2 items, buff 6 -> 0, buff 7 -> 3.
Sets: 1 "Main" (active) picks s1=1, s2=2, s3=3, s9=99 (unknown buff), burst {6, 7}; 2 "Alt" (empty).
"""

HEAD = """
ns.Weights = {WARRIOR = {{AP=1}, {AP=1}, {AP=1}}}
ns.DB = {}
ns.Buffs = {[1]={name='Apple'}, [2]={name='Bravo'}, [3]={name='Zulu'}, [6]={name='Rage'}, [7]={name='Haste'}}
ns.Slots = {s1={order=1}, s2={order=2}, s3={order=3}}
local bags = {[2]=2, [6]=0, [7]=3}
ns.Bags.CountBuff = function(_, b) return bags[b.__id] or 0 end
for id, b in pairs(ns.Buffs) do b.__id = id end
local sets = {[1]={name='Main', picks=PICKS, burst=BURST}, [2]={name='Alt', picks={}, burst={}}}
ns.Sets.List = function() return {1, 2} end
ns.Sets.Get = function(_, id) return sets[id] end
ns.Sets.Active = function() return ACTID, sets[ACTID] end
local function E(id, cat, name, excl, fx, status, burst)
  return {id=id, cat=cat, name=name, excl=excl, fx=fx, status=status, burst=burst}
end
local list = {
  E(1, "FOOD", "Apple", "s1", {STR=5}, "ACTIVE"),
  E(2, "ELIXIR", "Bravo", "s2", {STR=20}, "CAN_ADD"),
  E(3, "ELIXIR", "Zulu", "s3", {STR=1}, "UNAVAILABLE"),
  E(6, "POTION", "Rage", nil, {AP=100}, "CAN_ADD", true),
  E(7, "POTION", "Haste", nil, {AP=50}, "CAN_ADD", true),
}
local cat = {order = {}}
for _, e in ipairs(list) do
  if not cat[e.cat] then cat[e.cat] = {}; table.insert(cat.order, e.cat) end
  table.insert(cat[e.cat], e)
end
local st = {class="WARRIOR", spec=2, level=60, stale=STALE, active={[1]=true},
  stats={STR=110, AP=220}, unknownAuras={}, ratios={apPerStr=2, hpPerSta=10, manaPerInt=15}}
__ns.__vm = ns.ViewModel:Build(st, cat)
"""

MAIN = "{s1=1, s2=2, s3=3, s9=99}"


def build(addon, picks=MAIN, burst="{6, 7}", active="1", stale="false", lang=None):
    a = addon(mocks={"UnitClass": lambda unit=None: ("Warrior", "WARRIOR", 1)})
    if lang:
        a.run("ns.SetLanguage('%s')" % lang)
    a.run(HEAD.replace("PICKS", picks).replace("BURST", burst).replace("ACTID", active)
          .replace("STALE", stale))
    return a, a.eval("__ns.__vm")


def test_list_is_set_rows_active_first(addon):
    a, vm = build(addon)
    rows = [(r["buffId"], r["status"]) for r in vm["list"].values()]
    assert rows == [(1, "ACTIVE"), (2, "MISSING"), (3, "UNAVAILABLE"), (99, "UNAVAILABLE")]
    bravo = vm["list"][2]
    assert bravo["bagCount"] == 2 and bravo["valueText"] == "+20 Strength"
    assert a.errors() == []


def test_burst_block_and_badge(addon):
    a, vm = build(addon)
    assert [(b["name"], b["bagCount"]) for b in vm["burst"].values()] == [("Rage", 0), ("Haste", 3)]
    # MISSING Bravo + burst Rage without bags; UNAVAILABLE rows are not counted
    assert vm["badge"] == 2
    assert list(vm["tooltip"]["missing"].values()) == ["Bravo", "Rage"]
    assert vm["tooltip"]["setName"] == "Main" and vm["header"]["setName"] == "Main"
    assert 0 <= vm["tooltip"]["progress"] <= 100


def test_header_rows_use_set_picks(addon):
    # Bravo (STR 20) is picked and missing: the maximum reaches 110 - 0 + 20 = 130 vs. Apple only
    a, vm = build(addon)
    str_row = [r for r in vm["header"]["rows"].values() if r["stat"] == "STR"][0]
    assert str_row["current"] == 110 and str_row["max"] == 130 and str_row["diff"] == 20
    a, vm = build(addon, picks="{s1=1}", burst="{}")
    str_row = [r for r in vm["header"]["rows"].values() if r["stat"] == "STR"][0]
    assert str_row["max"] == str_row["current"]


def test_empty_set_flag(addon):
    a, vm = build(addon, picks="{s1=false}", burst="{}")
    assert vm["empty"] is True and len(vm["list"]) == 0 and vm["badge"] == 0
    a, vm = build(addon, picks="{}", burst="{6}")
    assert vm["empty"] is False  # burst buffs alone make the set non-empty
    a, vm = build(addon)
    assert vm["empty"] is False


def test_sets_listed_with_active(addon):
    a, vm = build(addon, active="2")
    got = [(s["id"], s["name"], s["active"]) for s in vm["sets"].values()]
    assert got == [(1, "Main", False), (2, "Alt", True)]
    assert vm["header"]["setName"] == "Alt" and vm["empty"] is True


def test_no_categories_or_only_missing(addon):
    a, vm = build(addon)
    assert vm["sections"] is None  # the category view is gone
    assert vm["list"][1]["status"] == "ACTIVE"  # ACTIVE rows are always listed


def test_no_active_set_does_not_raise(addon):
    a, vm = build(addon, active="nil")
    assert vm["empty"] is True and vm["header"]["setName"] == ""
    assert a.errors() == []


def test_stale_flag_in_header(addon):
    a, vm = build(addon, stale="true")
    assert vm["header"]["stale"] is True
    a, vm = build(addon)
    h = vm["header"]
    assert h["stale"] is False and h["level"] == 60 and h["class"] == "Warrior"
    assert h["specName"] == "Specialization 2"
    assert h["rows"][1]["stat"] == "STR"
    assert h["rows"][1]["label"] == "Strength"


def test_value_text_format(addon):
    a = addon()
    f = lambda fx: a.eval("ns.ViewModel.FormatFx(%s)" % fx)
    assert f("{AGI=25, CRIT=2}") == "+25 Agility, +2% Critical strike"
    assert f("{STAT_PCT=10}") == "+10% All stats"
    assert f("{HP=1.5}") == "+1.5 Health"
    assert f("{STR=1, AGI=2, STA=3, INT=4, SPI=5}") == "+1 Strength, +2 Agility, +3 Stamina, +4 Intellect, …"
    assert f("{}") == ""


def test_spec_name_from_state_and_hint_when_not_auto(addon):
    a, _ = build(addon)
    vm = a.eval("""ns.ViewModel:Build({class='WARRIOR', spec=2, specName='Fury', specAuto=false, level=60,
      active={}, stats={}, ratios={}}, {order={}})""")
    assert vm["header"]["specName"] == "Fury"
    assert vm["header"]["specHint"] == "Pick the specialization used to rank buffs."
    vm = a.eval("ns.ViewModel:Build({class='WARRIOR', spec=2, specAuto=true, level=60, active={}, stats={},"
                " ratios={}}, {order={}})")
    assert vm["header"]["specName"] == "Specialization 2" and vm["header"]["specHint"] is None
