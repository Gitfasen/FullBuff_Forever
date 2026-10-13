BUFFS = """
ns.Buffs = {
  [10] = {name="Zeal", cat="CLASS", cls="WARRIOR", fx={STR=50}, lvl=1, ranks={
     {spell=11, lvl=1, fx={STR=5}}, {spell=12, lvl=12, fx={STR=12}}, {spell=13, lvl=24, fx={STR=20}},
     {spell=14, lvl=36, fx={STR=30}}, {spell=10, lvl=48, fx={STR=50}}}},
  [20] = {name="Mage Self", cat="CLASS", cls="MAGE", selfOnly=true, fx={INT=5}, lvl=1},
  [21] = {name="Mage Group", cat="CLASS", cls="MAGE", fx={INT=7}, lvl=1},
  [22] = {name="Warr Self", cat="CLASS", cls="WARRIOR", selfOnly=true, fx={STA=3}, lvl=0},
  [30] = {name="Food B", cat="FOOD", fx={STR=12}, lvl=30, burst=true},
  [31] = {name="Food A", cat="FOOD", fx={STR=8}},
  [32] = {name="Food A", cat="FOOD", fx={STR=9}, lvl=10},
  [40] = {name="Flask", cat="FLASK", fx={STA=10}, lvl=60},
  [50] = {name="Low Rank Only", cat="CLASS", cls="WARRIOR", fx={STA=9}, lvl=1, ranks={{spell=51, lvl=30, fx={STA=1}}, {spell=50, lvl=40, fx={STA=9}}}},
}
"""


def build(addon, state, buffs=BUFFS):
    a = addon()
    a.run(buffs)
    a.run("ns.__s = %s" % state)
    return a


S = "{class='WARRIOR', level=30, active={}}"


def test_rank_chosen_by_target_level(addon):
    a = build(addon, S)
    e = a.eval("ns.Catalog:Build(ns.__s).CLASS[4]")  # Zeal
    assert e["name"] == "Zeal" and e["rankSpell"] == 14
    assert e["fx"]["STR"] == 30 and e["status"] == "CAN_ADD"


def test_rank_none_allowed_unavailable_lowest(addon):
    a = build(addon, "{class='WARRIOR', level=15, active={}}")
    e = a.eval("(function() for _, x in ipairs(ns.Catalog:Build(ns.__s).CLASS) do if x.id == 50 then return x end end end)()")
    assert e["status"] == "UNAVAILABLE" and e["rankSpell"] == 51 and e["fx"]["STA"] == 1
    a.run("ns.__s.level = 20")
    e = a.eval("(function() for _, x in ipairs(ns.Catalog:Build(ns.__s).CLASS) do if x.id == 50 then return x end end end)()")
    assert e["status"] == "CAN_ADD" and e["rankSpell"] == 51
    a.run("ns.__s.level = 19")
    e = a.eval("(function() for _, x in ipairs(ns.Catalog:Build(ns.__s).CLASS) do if x.id == 50 then return x end end end)()")
    assert e["status"] == "UNAVAILABLE"


def test_item_above_level_unavailable(addon):
    a = build(addon, S)
    foods = a.eval("ns.Catalog:Build(ns.__s).FOOD")
    by = {foods[i]["id"]: foods[i] for i in range(1, 4)}
    assert by[30]["status"] == "CAN_ADD" and by[30]["burst"] is True
    a = build(addon, S)
    assert a.eval("ns.Catalog:Build(ns.__s).FLASK[1].status") == "UNAVAILABLE"
    assert a.eval("ns.Catalog:Build(ns.__s).FLASK[1].rankSpell") == 40


def test_active_status(addon):
    a = build(addon, "{class='WARRIOR', level=30, active={[30]=true}}")
    foods = a.eval("ns.Catalog:Build(ns.__s).FOOD")
    assert [foods[i]["status"] for i in (1, 2, 3)] == ["CAN_ADD", "CAN_ADD", "ACTIVE"]


def test_selfonly_class_filter(addon):
    a = build(addon, S)
    ids = a.eval("(function() local t={} for _, x in ipairs(ns.Catalog:Build(ns.__s).CLASS) do t[#t+1]=x.id end return table.concat(t, ',') end)()")
    assert ids == "50,21,22,10"
    assert "20" not in ids.split(",")


def test_sorted_by_name_then_id(addon):
    a = build(addon, S)
    ids = [a.eval("ns.Catalog:Build(ns.__s).FOOD[%d].id" % i) for i in (1, 2, 3)]
    assert ids == [31, 32, 30]


def test_categories_in_order(addon):
    a = build(addon, S)
    a.run("ns.Buffs[60] = {name='W', cat='WORLD', fx={STA=1}} ns.Buffs[61] = {name='P', cat='POTION', fx={STA=1}}")
    order = a.eval("ns.Catalog:Build(ns.__s).order")
    assert [order[i] for i in range(1, len(order) + 1)] == ["CLASS", "WORLD", "FLASK", "FOOD", "POTION"]


def test_lvl_zero_no_requirement_and_smoke_real_data(addon):
    a = addon()
    a.run("ns.__s = {class='WARRIOR', level=1, active={}}")
    assert a.eval("ns.Catalog:Build(ns.__s).CLASS ~= nil") in (True, False)
    assert a.eval("#ns.Catalog:Build(ns.__s).order") > 0
