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
    a.fire_event("PLAYER_ENTERING_WORLD", True, False)
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


def test_spec_ignored_before_entering_world(addon):
    # Before PLAYER_ENTERING_WORLD the talent snapshot may be incomplete: no switching.
    a = boot(addon)
    a.run("ns.Sets:Create('One'); ns.Sets:Create('Two'); ns.Sets:BindSpec(2, 1); ns.Sets:BindSpec(3, 2)")
    a.run("ns.Events:Fire('FULLBUFF_STATE')")  # spec 1, pre-PEW
    assert a.eval("(ns.Sets:Active())") == 1
    a.fire_event("PLAYER_ENTERING_WORLD", True, False)
    a.run("SPEC = 2; ns.Events:Fire('FULLBUFF_STATE')")
    assert a.eval("(ns.Sets:Active())") == 3
    assert a.errors() == []


def test_spec_after_entering_world_same_spec_as_before(addon):
    # The pre-PEW snapshot must not be remembered as "already seen".
    a = boot(addon)
    a.run("ns.Sets:Create('One'); ns.Sets:BindSpec(2, 1)")
    a.run("ns.Events:Fire('FULLBUFF_STATE')")
    assert a.eval("(ns.Sets:Active())") == 1
    a.fire_event("PLAYER_ENTERING_WORLD", True, False)
    a.run("ns.Events:Fire('FULLBUFF_STATE')")
    assert a.eval("(ns.Sets:Active())") == 2


# --- Resolve / Pick by buff slot ---
RESOLVE = "ns.Buffs = {[10]={name='A', excl='slotA'}, [11]={name='B', excl='slotA'}, [20]={name='F', excl='slotB'}}"


def test_resolve_maps_picks_to_buff_slots(addon):
    a = boot(addon)
    a.run(RESOLVE)
    r = a.eval("ns.Sets:Resolve({picks={OLD=10, slotB=false, gone=99}})")
    assert dict(r) == {"slotA": 10, "slotB": False, "gone": 99}
    # duplicates: the first by saved-key order wins
    r = a.eval("ns.Sets:Resolve({picks={OLD=10, slotA=10}})")
    assert dict(r) == {"slotA": 10}
    assert dict(a.eval("ns.Sets:Resolve({picks={}})")) == {}
    assert dict(a.eval("ns.Sets:Resolve(nil)")) == {}


def test_pick_removes_keys_resolving_to_same_slot(addon):
    a = boot(addon)
    a.run(RESOLVE)
    a.run("ns.Sets:Get(1).picks = {OLD=10, slotB=20}")
    a.run("ns.Sets:Pick(1, 'slotA', 10)")
    assert dict(a.eval("ns.Sets:Get(1).picks")) == {"slotA": 10, "slotB": 20}
    a.run("ns.Sets:Get(1).picks.OLD2 = 11; ns.Sets:Pick(1, 'slotA', false)")
    assert dict(a.eval("ns.Sets:Get(1).picks")) == {"slotA": False, "slotB": 20}


# --- auto ("Main" follows recommendations until edited) ---
def test_main_is_auto_and_follows_recommendations(addon):
    a = boot(addon)
    assert a.eval("ns.Sets:Get(1).auto") is True
    a.fire_event("PLAYER_ENTERING_WORLD", True, False)
    # a level-up changes the recommendation in slotA from 11 to 10
    a.run("ns.Scoring.MarkRecommended = function(_, cat) for _, c in ipairs(cat.order) do "
          "for _, e in ipairs(cat[c]) do if e.id == 10 or e.id == 21 then e.recommended = true end end end end")
    a.run("ns.Events:Fire('FULLBUFF_STATE')")
    assert dict(a.eval("ns.Sets:Get(1).picks")) == {"slotA": 10, "slotB": 21}
    assert a.errors() == []


def test_auto_waits_for_entering_world(addon):
    a = boot(addon)
    a.run("ns.Scoring.MarkRecommended = function() end; ns.Events:Fire('FULLBUFF_STATE')")
    assert dict(a.eval("ns.Sets:Get(1).picks")) == {"slotA": 11, "slotB": 20}


def test_pick_clears_auto_burst_does_not(addon):
    a = boot(addon)
    a.fire_event("PLAYER_ENTERING_WORLD", True, False)
    a.run("ns.Sets:AddBurst(1, 30); ns.Sets:MoveBurst(1, 30, 1); ns.Sets:RemoveBurst(1, 30)")
    assert a.eval("ns.Sets:Get(1).auto") is True
    a.run("ns.Sets:Pick(1, 'slotA', 10)")
    assert a.eval("ns.Sets:Get(1).auto") is None
    a.run("ns.Events:Fire('FULLBUFF_STATE')")
    assert dict(a.eval("ns.Sets:Get(1).picks")) == {"slotA": 10, "slotB": 20}


def test_copy_and_new_are_not_auto(addon):
    a = boot(addon)
    assert a.eval("ns.Sets:Get(ns.Sets:Copy(1)).auto") is None
    assert a.eval("ns.Sets:Get(ns.Sets:Create('X')).auto") is None


def test_auto_unchanged_recommendations_do_not_fire(addon):
    a = boot(addon)
    a.fire_event("PLAYER_ENTERING_WORLD", True, False)
    a.run("n = 0; ns.Events:On('FULLBUFF_SET', function() n = n + 1 end); ns.Events:Fire('FULLBUFF_STATE')")
    assert a.eval("n") == 0


# --- fix A: default picks prefer buffs from players (CLASS) ---
CLASSPREF = """
ns.Catalog.Build = function()
  return {order={'CLASS','CAMPING','SCROLL','FOOD'},
    CLASS={{id=10938, cat='CLASS', excl='STA', status='CAN_ADD', fx={s=5}},
           {id=21564, cat='CLASS', excl='STA', status='UNAVAILABLE', fx={s=50}},
           {id=10157, cat='CLASS', excl='INT', status='CAN_ADD', fx={s=3}},
           {id=23028, cat='CLASS', excl='INT', status='CAN_ADD', fx={s=4}},
           {id=99, cat='CLASS', excl='BURSTY', status='CAN_ADD', burst=true, fx={s=9}}},
    CAMPING={{id=1230124, cat='CAMPING', excl='STA', status='CAN_ADD', fx={s=20}},
             {id=1229513, cat='CAMPING', excl='INT', status='ACTIVE', fx={s=30}},
             {id=500, cat='CAMPING', excl='BURSTY', status='CAN_ADD', fx={s=1}}},
    SCROLL={{id=1000, cat='SCROLL', excl='STA', status='CAN_ADD', fx={s=40}}},
    FOOD={{id=20, cat='FOOD', excl='slotB', status='CAN_ADD', fx={s=1}}}}
end
ns.Scoring.Score = function(_, fx) return fx.s or 0 end
ns.Scoring.MarkRecommended = function(_, cat)
  local best = {}
  for _, c in ipairs(cat.order) do for _, e in ipairs(cat[c]) do
    e.recommended = nil
    if not e.burst and e.status ~= 'UNAVAILABLE' and (not best[e.excl] or e.fx.s > best[e.excl].fx.s) then best[e.excl] = e end
  end end
  for _, e in pairs(best) do e.recommended = true end
end
"""


def test_default_picks_prefer_class_buffs(addon):
    a = addon()
    a.run(SETUP)
    a.run(CLASSPREF)
    a.run("ns.Events:Fire('FULLBUFF_LOADED')")
    picks = dict(a.eval("ns.Sets:Get(1).picks"))
    # STA: Power Word: Fortitude over Scroll (40) and Boosted Stamina (20); Prayer unavailable
    # INT: the better class buff (23028) over the active camp buff; BURSTY: burst class
    # buff ignored -> recommendation; slotB: no class buff -> recommendation
    assert picks == {"STA": 10938, "INT": 23028, "BURSTY": 500, "slotB": 20}
    assert dict(a.eval("ns.Sets:Get(ns.Sets:Create('X')).picks")) == picks


# --- fix A: catch-up after PLAYER_ENTERING_WORLD without a new FULLBUFF_STATE ---
def test_entering_world_catches_up_without_state_event(addon):
    a = boot(addon)
    a.run("ns.PlayerState.Refresh = function() end")  # no FULLBUFF_STATE after PEW
    a.run("ns.Sets:Create('One'); ns.Sets:BindSpec(2, 1)")
    a.run("ns.Scoring.MarkRecommended = function(_, cat) for _, c in ipairs(cat.order) do "
          "for _, e in ipairs(cat[c]) do if e.id == 10 or e.id == 21 then e.recommended = true end end end end")
    a.fire_event("PLAYER_ENTERING_WORLD", True, False)
    assert a.eval("(ns.Sets:Active())") == 1  # debounced, not yet
    a.advance(0.6)
    assert a.eval("(ns.Sets:Active())") == 2
    assert dict(a.eval("ns.Sets:Get(1).picks")) == {"slotA": 10, "slotB": 21}
    # runs once: a later spec change still needs a state event
    a.run("n = 0; ns.Events:On('FULLBUFF_SET', function() n = n + 1 end)")
    a.advance(5)
    assert a.eval("n") == 0
    assert a.errors() == []
