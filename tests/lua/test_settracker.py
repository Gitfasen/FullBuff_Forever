"""SetTracker: set -> rows. Buffs/Slots/Bags/ViewModel are stubbed."""

SETUP = """
ns.Buffs = {[1]={name='One', items={100}}, [2]={name='Two', items={}}, [3]={name='Three', items={}},
  [4]={name='Four', items={}}, [5]={name='Five', items={200}}, [6]={name='Six', items={}}}
ns.Slots = {s1={name={en='S1',uk='S1'}, order=1}, s2={name={en='S2',uk='S2'}, order=2}}
ns.Bags.CountBuff = function(_, b) return b.items[1] == 100 and 7 or 0 end
ns.ViewModel.FormatFx = function(fx) return fx and fx.txt or '' end
ns.ViewModel.IconFor = function(sp) return 'icon' .. tostring(sp) end
CAT = {order={'FOOD'}, FOOD={
  {id=1, excl='s1', status='CAN_ADD', fx={txt='fx1'}, rankSpell=11},
  {id=2, excl='s2', status='ACTIVE', fx={txt='fx2'}, rankSpell=12},
  {id=3, excl='s1', status='UNAVAILABLE', rankSpell=13},
  {id=5, excl='zz', status='ACTIVE', fx={txt='fx5'}, rankSpell=15},
  {id=6, excl='s2', status='CAN_ADD', burst=true, fx={}, rankSpell=16},
}}
"""


def ev(addon, setlua):
    a = addon()
    a.run(SETUP)
    a.run("__ns.__r = ns.SetTracker:Evaluate({}, CAT, %s)" % setlua)
    return a, a.eval("__ns.__r")


def rows(r):
    return [(x["slot"], x["buffId"], x["status"]) for x in r["rows"].values()]


def test_statuses_and_order(addon):
    a, r = ev(addon, "{picks={s1=1, s2=2, zz=5}, burst={}}")
    assert rows(r) == [("s2", 2, "ACTIVE"), ("zz", 5, "ACTIVE"), ("s1", 1, "MISSING")]
    x = r["rows"][1]
    assert x["name"] == "Two" and x["valueText"] == "fx2" and x["icon"] == "icon12"
    assert r["missingCount"] == 1 and r["unavailableCount"] == 0
    assert a.errors() == []


def test_bag_count_on_missing_row(addon):
    _, r = ev(addon, "{picks={s1=1}, burst={}}")
    assert r["rows"][1]["bagCount"] == 7


def test_vanished_buff_unavailable_no_error(addon):
    a, r = ev(addon, "{picks={s1=999, s2=3}, burst={}}")
    got = {x["buffId"]: x for x in r["rows"].values()}
    assert got[999]["status"] == "UNAVAILABLE" and got[999]["name"] == "#999"
    assert got[999]["valueText"] == ""
    assert got[3]["status"] == "UNAVAILABLE"  # catalog entry UNAVAILABLE
    assert r["unavailableCount"] == 2 and r["missingCount"] == 0
    assert a.errors() == []


def test_buff_without_catalog_entry_unavailable(addon):
    _, r = ev(addon, "{picks={s1=4}, burst={}}")
    assert rows(r) == [("s1", 4, "UNAVAILABLE")]


def test_unknown_slot_kept(addon):
    _, r = ev(addon, "{picks={gone=2, s1=1}, burst={}}")
    assert rows(r) == [("gone", 2, "ACTIVE"), ("s1", 1, "MISSING")]
    # one buff picked under two keys: one row (first saved key; buff 1 has no slot)
    _, r = ev(addon, "{picks={gone=1, s1=1}, burst={}}")
    assert rows(r) == [("gone", 1, "MISSING")]


def test_pick_filed_under_buff_slot(addon):
    a = addon()
    a.run(SETUP)
    a.run("ns.Buffs[1].excl = 's1'; __ns.__r = ns.SetTracker:Evaluate({}, CAT, {picks={OLD=1, s1=1}, burst={}})")
    r = a.eval("__ns.__r")
    assert rows(r) == [("s1", 1, "MISSING")] and r["missingCount"] == 1


def test_missing_count_includes_zero_burst(addon):
    _, r = ev(addon, "{picks={s2=2}, burst={1, 5, 6}}")
    b = {x["buffId"]: x for x in r["burst"].values()}
    assert b[1]["bagCount"] == 7 and b[5]["bagCount"] == 0 and b[1]["name"] == "One"
    assert r["missingCount"] == 2  # burst 5 and 6 have no bags


def test_empty_set_rows_empty_and_zero_missing(addon):
    a, r = ev(addon, "{picks={s1=false}, burst={}}")
    assert len(r["rows"]) == 0 and r["missingCount"] == 0 and len(r["burst"]) == 0
    assert a.errors() == []


def test_burst_unknown_or_without_entry_unavailable_not_counted(addon):
    # 4 has no catalog entry, 77 is not in ns.Buffs; only 5 (no bags) counts as missing
    a, r = ev(addon, "{picks={}, burst={4, 77, 5}}")
    b = {x["buffId"]: x for x in r["burst"].values()}
    assert b[4]["unavailable"] is True and b[77]["unavailable"] is True and b[77]["name"] == "#77"
    assert b[5]["unavailable"] is not True
    assert r["missingCount"] == 1
    assert a.errors() == []


def test_rows_carry_slot_name(addon):
    _, r = ev(addon, "{picks={s1=1, gone=2}, burst={}}")
    names = {x["slot"]: x["slotName"] for x in r["rows"].values()}
    assert names == {"s1": "S1", "gone": "gone"}
