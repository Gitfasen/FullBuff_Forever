"""ViewModel tests. Fixture: WARRIOR spec 1, weights AP=1, ratio apPerStr=2.

Catalog (all weighted entries are positive-score for a WARRIOR with AP=1):
  CLASS : 1 Alpha (ACTIVE, STR 10), 2 Bravo (CAN_ADD, STR 20), 3 Zulu (UNAVAILABLE)
  FOOD  : 4 Apple (CAN_ADD, STR 5), 5 Berry (CAN_ADD, STR 3)
  POTION: 6 Rage (CAN_ADD, burst, AP 100)
Recommended (MaxCalc marks): 2 Bravo, 4 Apple (excl food), 6 is burst.
"""

HEAD = """
ns.Weights = {WARRIOR = {{AP=1}, {AP=1}, {AP=1}}}
ns.DB = DBX
local function E(id, cat, name, excl, fx, status, burst)
  return {id=id, cat=cat, name=name, excl=excl, fx=fx, status=status, burst=burst}
end
local list = {
  E(1, "CLASS", "Alpha", nil, {STR=10}, "ACTIVE"),
  E(2, "CLASS", "Bravo", nil, {STR=20}, "CAN_ADD"),
  E(3, "CLASS", "Zulu", nil, {STR=1}, "UNAVAILABLE"),
  E(4, "FOOD", "Apple", "food", {STR=5}, "CAN_ADD"),
  E(5, "FOOD", "Berry", "food", {STR=3}, "CAN_ADD"),
  E(6, "POTION", "Rage", nil, {AP=100}, "CAN_ADD", true),
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


def build(addon, db="{}", stale="false", lang=None):
    a = addon(mocks={"UnitClass": lambda unit=None: ("Warrior", "WARRIOR", 1)})
    if lang:
        a.run("ns.SetLanguage('%s')" % lang)
    a.run(HEAD.replace("DBX", db).replace("STALE", stale))
    return a, a.eval("__ns.__vm")


def items(vm):
    return {s["cat"]: [(i["id"], i["status"], i["recommended"]) for i in s["items"].values()]
            for s in vm["sections"].values()}


def test_sections_missing_first(addon):
    a, vm = build(addon)
    it = items(vm)
    # CAN_ADD first, then UNAVAILABLE, ACTIVE last
    assert [i[0] for i in it["CLASS"]] == [2, 3, 1]
    # within CAN_ADD the recommended one leads (Apple, recommended, is listed before Berry)
    assert [i[0] for i in it["FOOD"]] == [4, 5]
    assert it["FOOD"][0][2] is True and it["FOOD"][1][2] is False
    sec = {s["cat"]: s for s in vm["sections"].values()}
    assert sec["CLASS"]["activeCount"] == 1 and sec["CLASS"]["total"] == 2
    assert sec["CLASS"]["collapsed"] is False
    assert sec["CLASS"]["title"] == "Class buffs"
    assert [s["cat"] for s in vm["sections"].values()] == ["CLASS", "FOOD", "POTION"]


def test_only_missing_filter(addon):
    a, vm = build(addon, db="{onlyMissing=true, collapsed={FOOD=true}}")
    it = items(vm)
    assert [i[0] for i in it["CLASS"]] == [2]
    assert "FOOD" in it and "POTION" in it
    sec = {s["cat"]: s for s in vm["sections"].values()}
    assert sec["FOOD"]["collapsed"] is True
    # activeCount/total are unaffected by the filter
    assert sec["CLASS"]["activeCount"] == 1 and sec["CLASS"]["total"] == 2


def test_only_missing_drops_empty_sections(addon):
    a = addon()
    a.run("ns.Weights = {WARRIOR = {{AP=1}}}; ns.DB = {onlyMissing=true}")
    a.run("""
local cat = {order={"CLASS"}, CLASS={{id=1, cat="CLASS", name="A", fx={STR=1}, status="ACTIVE"}}}
__ns.__vm = ns.ViewModel:Build({class="WARRIOR", spec=1, level=60, active={[1]=true}, stats={},
  unknownAuras={}, ratios={apPerStr=2}}, cat)""")
    assert len(a.eval("__ns.__vm.sections")) == 0


def test_badge_counts_can_add_non_burst(addon):
    a, vm = build(addon)
    # recommended CAN_ADD non-burst: Bravo (2) and Apple (4). Rage is burst, Alpha active.
    assert vm["badge"] == 2
    # MaxCalc order: category order (CLASS, FOOD)
    assert list(vm["tooltip"]["missing"].values()) == ["Bravo", "Apple"]
    assert 0 <= vm["tooltip"]["progress"] <= 100


def test_stale_flag_in_header(addon):
    a, vm = build(addon, stale="true")
    assert vm["header"]["stale"] is True
    a, vm = build(addon)
    h = vm["header"]
    assert h["stale"] is False and h["level"] == 60 and h["class"] == "Warrior"
    assert h["specName"] == "Specialization 2"
    assert h["rows"][1]["stat"] == "STR"
    assert h["rows"][1]["label"] == "Strength"


def test_section_titles_localized_uk(addon):
    a, vm = build(addon, lang="uk")
    titles = [s["title"] for s in vm["sections"].values()]
    assert titles[0] != "Class buffs" and any("Ѐ" <= c <= "ӿ" for c in titles[0])
    assert a.eval("ns.L.CATEGORY_CLASS") == titles[0]


def test_value_text_format(addon):
    a = addon()
    f = lambda fx: a.eval("ns.ViewModel.FormatFx(%s)" % fx)
    assert f("{AGI=25, CRIT=2}") == "+25 Agility, +2% Critical strike"
    assert f("{STAT_PCT=10}") == "+10% All stats"
    assert f("{HP=1.5}") == "+1.5 Health"
    assert f("{STR=1, AGI=2, STA=3, INT=4, SPI=5}") == "+1 Strength, +2 Agility, +3 Stamina, +4 Intellect, …"
    assert f("{}") == ""
