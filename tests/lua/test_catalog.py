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


def test_lvl_zero_and_nil_have_no_requirement_at_level_1(addon):
    a = build(addon, "{class='WARRIOR', level=1, active={}}")
    a.run("""ns.Buffs[70] = {name='W0', cat='WORLD', fx={STA=1}, lvl=0}
    ns.Buffs[71] = {name='C10', cat='CAMPING', fx={STA=1}, lvl=10}
    ns.Buffs[72] = {name='Cnil', cat='CAMPING', fx={STA=1}}""")
    get = "(function() for _, x in ipairs(ns.Catalog:Build(ns.__s)[%r]) do if x.id == %d then return x.status end end end)()"
    assert a.eval(get % ("WORLD", 70)) == "CAN_ADD"
    assert a.eval(get % ("CAMPING", 72)) == "CAN_ADD"
    assert a.eval(get % ("CAMPING", 71)) == "UNAVAILABLE"
    assert a.eval(get % ("FOOD", 31)) == "CAN_ADD"
    assert a.eval(get % ("FOOD", 32)) == "UNAVAILABLE"


def test_unknown_category_skipped(addon):
    a = build(addon, S)
    a.run("ns.Buffs[80] = {name='X', cat='order', fx={STA=1}} ns.Buffs[81] = {name='Y', cat='BOGUS', fx={STA=1}}")
    assert a.eval("ns.Catalog:Build(ns.__s).BOGUS") is None
    assert a.eval("type(ns.Catalog:Build(ns.__s).order[1])") == "string"


def test_real_data_build_valid_statuses_and_categories(addon):
    a = addon()
    a.run("ns.__s = {class='WARRIOR', level=60, active={}}")
    bad = a.eval("""(function()
      local c = ns.Catalog:Build(ns.__s)
      local known = {}
      for _, k in ipairs(ns.Catalog.CATEGORIES) do known[k] = true end
      local ok = {ACTIVE=true, CAN_ADD=true, UNAVAILABLE=true}
      if #c.order == 0 then return 'empty order' end
      for _, cat in ipairs(c.order) do
        if not known[cat] or not c[cat] or #c[cat] == 0 then return 'bad cat ' .. cat end
        for _, e in ipairs(c[cat]) do
          if not ok[e.status] then return 'bad status ' .. e.id end
        end
      end
      return false
    end)()""")
    assert bad is False, bad


FORT = """
ns.Buffs = {
  [10938] = {name="Power Word: Fortitude", cat="CLASS", cls="PRIEST", fx={STA=54}, lvl=1, excl="CLASS:Fort", ranks={
     {spell=1243, lvl=1, fx={STA=3}}, {spell=1244, lvl=12, fx={STA=8}}, {spell=1245, lvl=24, fx={STA=20}},
     {spell=2791, lvl=36, fx={STA=32}}, {spell=10937, lvl=48, fx={STA=43}}, {spell=10938, lvl=60, fx={STA=54}}}},
}
"""


def fort(addon, aura, level=60):
    a = build(addon, "{class='WARRIOR', level=%d, active={[10938]=true}, activeAura={[10938]=%d}}"
              % (level, aura), FORT)
    return a, a.eval("ns.Catalog:Build(ns.__s).CLASS[1]")


def test_active_lower_rank_is_upgrade_with_active_rank_fx(addon):
    # rank 3 (STA 20) active, rank 6 (STA 54) available at 60 -> upgrade available
    _, e = fort(addon, 1245)
    assert e["status"] == "CAN_ADD" and e["rankSpell"] == 10938
    assert e["fx"]["STA"] == 54 and e["activeFx"]["STA"] == 20


def test_active_top_rank_stays_active(addon):
    _, e = fort(addon, 10938)
    assert e["status"] == "ACTIVE" and e["activeFx"]["STA"] == 54


def test_active_rank_at_best_for_level_stays_active(addon):
    # level 30: best rank allowed is rank 4 (lvl 36 - 10 slack); rank 4 active -> ACTIVE
    _, e = fort(addon, 2791, level=30)
    assert e["status"] == "ACTIVE" and e["activeFx"]["STA"] == 32
