"""Sets: per-character storage, CRUD, spec binding. PlayerState/Catalog/Scoring are stubbed."""

SETUP = """
SPEC = 1
ns.PlayerState.Get = function() return {class='WARRIOR', level=60, spec=SPEC} end
ns.Catalog.Build = function(_, st)
  return {order={'FLASK','FOOD'},
    FLASK={{id=10, excl='slotA'}, {id=11, excl='slotA'}},
    FOOD={{id=20, excl='slotB'}, {id=21, excl='slotB'}, {id=30, excl='slotC', burst=true}}}
end
ns.Scoring.MarkRecommended = function(_, cat)
  for _, id in ipairs({11, 20, 30}) do
    for _, c in ipairs(cat.order) do for _, e in ipairs(cat[c]) do
      if e.id == id then e.recommended = true end end end
  end
end
ns.CharDB = {}
ns.DB = {lang='en'}
"""


def boot(addon, lang="en"):
    a = addon()
    a.run(SETUP)
    if lang != "en":
        a.run("ns.DB.lang = %r; ns.SetLanguage(%r)" % (lang, lang))
    a.run("ns.Events:Fire('FULLBUFF_LOADED')")
    return a


def test_first_load_creates_main_from_recommendations(addon):
    a = boot(addon)
    assert a.eval("ns.Sets:List()[1]") == 1 and a.eval("#ns.Sets:List()") == 1
    sid, s = a.eval("{ns.Sets:Active()}")[1], a.eval("select(2, ns.Sets:Active())")
    assert sid == 1 and s["name"] == "Main"
    assert dict(s["picks"]) == {"slotA": 11, "slotB": 20}
    assert len(s["burst"]) == 0
    assert a.errors() == []


def test_main_name_ukrainian(addon):
    a = boot(addon, "uk")
    assert a.eval("select(2, ns.Sets:Active()).name") == "Основний"


def test_copy_duplicates_without_binding(addon):
    a = boot(addon)
    a.run("ns.Sets:BindSpec(1, 2); ns.Sets:AddBurst(1, 30)")
    new = a.eval("ns.Sets:Copy(1)")
    assert new == 2
    s = a.eval("ns.Sets:Get(2)")
    assert s["name"] == "Main (copy)" and s["spec"] is None
    assert dict(s["picks"]) == {"slotA": 11, "slotB": 20} and list(s["burst"].values()) == [30]
    a.run("ns.Sets:Pick(2, 'slotA', 10); ns.Sets:AddBurst(2, 31)")
    assert a.eval("ns.Sets:Get(1).picks.slotA") == 11 and a.eval("#ns.Sets:Get(1).burst") == 1
    assert a.eval("ns.Sets:Get(1).spec") == 2
    assert a.eval("(ns.Sets:Active())") == 1


def test_delete_active_activates_other(addon):
    a = boot(addon)
    a.run("ns.Sets:Create('B'); ns.Sets:SetActive(1); ns.Sets:Delete(1)")
    assert a.eval("(ns.Sets:Active())") == 2
    assert a.eval("#ns.Sets:List()") == 1


def test_delete_last_recreates_main(addon):
    a = boot(addon)
    a.run("ns.Sets:Delete(1)")
    assert a.eval("#ns.Sets:List()") == 1
    sid = a.eval("(ns.Sets:Active())")
    assert a.eval("ns.Sets:Get(%d).name" % sid) == "Main"
    assert dict(a.eval("ns.Sets:Get(%d).picks" % sid)) == {"slotA": 11, "slotB": 20}


def test_bind_spec_unique(addon):
    a = boot(addon)
    a.run("ns.Sets:Create('B'); ns.Sets:BindSpec(1, 2); ns.Sets:BindSpec(2, 2)")
    assert a.eval("ns.Sets:Get(1).spec") is None and a.eval("ns.Sets:Get(2).spec") == 2
    a.run("ns.Sets:BindSpec(2, nil)")
    assert a.eval("ns.Sets:Get(2).spec") is None


def test_spec_change_switches_set(addon):
    a = boot(addon)
    a.run("ns.Sets:Create('B'); ns.Sets:BindSpec(2, 3)")
    a.run("ns.Events:Fire('FULLBUFF_STATE')")  # spec 1 seen, no binding
    assert a.eval("(ns.Sets:Active())") == 1
    a.run("SPEC = 3; ns.Events:Fire('FULLBUFF_STATE')")
    assert a.eval("(ns.Sets:Active())") == 2
    a.run("ns.Sets:SetActive(1); ns.Events:Fire('FULLBUFF_STATE')")  # same spec: no re-switch
    assert a.eval("(ns.Sets:Active())") == 1
    a.run("SPEC = 2; ns.Events:Fire('FULLBUFF_STATE')")  # unbound spec keeps active
    assert a.eval("(ns.Sets:Active())") == 1
    assert a.errors() == []


def test_pick_false_and_nil(addon):
    a = boot(addon)
    a.run("ns.Sets:Pick(1, 'slotA', false)")
    assert a.eval("ns.Sets:Get(1).picks.slotA") is False
    a.run("ns.Sets:Pick(1, 'slotA', 10)")
    assert a.eval("ns.Sets:Get(1).picks.slotA") == 10
    a.run("ns.Sets:Pick(1, 'slotA', nil)")
    assert a.eval("ns.Sets:Get(1).picks.slotA") is None


def test_burst_add_remove_move_no_duplicates(addon):
    a = boot(addon)
    a.run("for _, b in ipairs({1, 2, 3, 2}) do ns.Sets:AddBurst(1, b) end")
    burst = lambda: list(a.eval("ns.Sets:Get(1).burst").values())
    assert burst() == [1, 2, 3]
    a.run("ns.Sets:MoveBurst(1, 3, -1)")
    assert burst() == [1, 3, 2]
    a.run("ns.Sets:MoveBurst(1, 1, -1); ns.Sets:MoveBurst(1, 2, 1); ns.Sets:MoveBurst(1, 9, 1)")
    assert burst() == [1, 3, 2]
    a.run("ns.Sets:MoveBurst(1, 1, 5)")
    assert burst() == [3, 2, 1]
    a.run("ns.Sets:RemoveBurst(1, 2); ns.Sets:RemoveBurst(1, 99)")
    assert burst() == [3, 1]


def test_mutations_fire_event(addon):
    a = boot(addon)
    a.run("n = 0; ns.Events:On('FULLBUFF_SET', function() n = n + 1 end)")
    calls = ["Create('B')", "Copy(1)", "Rename(1, 'X')", "Pick(1, 's', 5)", "AddBurst(1, 7)",
             "AddBurst(1, 8)", "MoveBurst(1, 8, -1)", "RemoveBurst(1, 7)", "BindSpec(1, 2)",
             "SetActive(2)", "Delete(3)"]
    for i, c in enumerate(calls, 1):
        a.run("ns.Sets:" + c)
        assert a.eval("n") == i, c
    assert a.errors() == []
