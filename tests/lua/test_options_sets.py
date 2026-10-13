"""Options: Sets editor (SlotModel, BurstModel, panel widgets)."""

SETUP = """
ns.PlayerState.Get = function() return {class='WARRIOR', level=60, spec=1} end
ns.Buffs = {
  [10] = {name='Elixir A'}, [11] = {name='Elixir B'}, [12] = {name='Elixir C'},
  [20] = {name='Food A'}, [40] = {name='Gated'},
  [30] = {name='Potion', burst=true, items={900}}, [31] = {name='Trinket', burst=true},
  [32] = {name='Burst gated', burst=true}, [33] = {name='Another', burst=true},
}
ns.Slots = {
  slotA = {name={en='Elixir slot', uk='Слот еліксирів'}, order=1},
  slotB = {name={en='Food slot', uk='Слот їжі'}, order=2},
  slotC = {name={en='Gated slot', uk='Закритий слот'}, order=3},
  slotD = {name={en='Old slot', uk='Старий слот'}, order=4},
}
ns.Catalog.Build = function(_, st)
  return {order={'FLASK','FOOD','POTION'},
    FLASK={{id=10, name='Elixir A', excl='slotA', status='CAN_ADD', fx={AGI=10}},
           {id=11, name='Elixir B', excl='slotA', status='ACTIVE', fx={AGI=5}},
           {id=12, name='Elixir C', excl='slotA', status='CAN_ADD', fx={AGI=1}}},
    FOOD={{id=20, name='Food A', excl='slotB', status='CAN_ADD', fx={STA=3}},
          {id=40, name='Gated', excl='slotC', status='UNAVAILABLE', fx={STA=9}}},
    POTION={{id=30, name='Potion', burst=true, status='CAN_ADD'},
            {id=31, name='Trinket', burst=true, status='ACTIVE'},
            {id=33, name='Another', burst=true, status='CAN_ADD'},
            {id=32, name='Burst gated', burst=true, status='UNAVAILABLE'}}}
end
ns.Scoring.MarkRecommended = function(_, cat)
  for _, c in ipairs(cat.order) do for _, e in ipairs(cat[c]) do
    e.recommended = (e.id == 10 or e.id == 20) or nil end end
end
ns.Bags.CountBuff = function(_, b) return b and b.items and 3 or 0 end
"""


def boot(addon, lang="en"):
    a = addon()
    a.load_addon()
    a.run(SETUP)
    a.run("ns.CharDB.sets = nil; ns.CharDB.activeSet = nil; ns.CharDB.nextSetId = nil")
    if lang != "en":
        a.run("ns.SetLanguage(%r)" % lang)
    a.run("ns.Sets:EnsureDefault()")
    return a


def panel(a):
    a.run("__ns.p = __settings.categories[1].frame; __ns.p.__scripts.OnShow(__ns.p); "
          "__ns.fired = 0; ns.Events:On('FULLBUFF_SET', function() __ns.fired = __ns.fired + 1 end)")


def click(a, expr):
    a.run("local b = %s; b.__scripts.OnClick(b)" % expr)


def radio(slot, buff):
    key = "false" if buff is False else str(buff)
    return ("(function() for _, r in ipairs(ns.Options.radios) do if r:IsShown() and r.fbSlot == %r and "
            "r.fbBuff == %s then return r end end end)()" % (slot, key))


def burst_widget(pool, buff):
    return ("(function() for _, c in ipairs(ns.Options.%s) do if c:IsShown() and c.fbBuff == %d "
            "then return c end end end)()" % (pool, buff))


def test_slot_model_groups_and_star(addon):
    a = boot(addon)
    m = a.eval("ns.Options:SlotModel(1)")
    assert [s["slot"] for s in m.values()] == ["slotA", "slotB"]
    s = m[1]
    assert s["name"] == "Elixir slot"
    assert [o["buffId"] for o in s["options"].values()] == [10, 11, 12]  # recommended, then name
    assert s["options"][1]["recommended"] is True and s["options"][2]["recommended"] is not True
    assert s["options"][2]["active"] is True and s["options"][2]["valueText"] == "+5 Agility"
    assert s["picked"] == 10


def test_slot_model_keeps_unavailable_pick(addon):
    a = boot(addon)
    a.run("ns.Sets:Pick(1, 'slotD', 99); ns.Sets:Pick(1, 'slotC', 40)")
    m = a.eval("ns.Options:SlotModel(1)")
    by = {s["slot"]: s for s in m.values()}
    assert set(by) == {"slotA", "slotB", "slotC", "slotD"}
    o = by["slotD"]["options"][1]
    assert o["buffId"] == 99 and o["unavailable"] is True and by["slotD"]["picked"] == 99
    assert by["slotC"]["options"][1]["unavailable"] is True and by["slotC"]["options"][1]["name"] == "Gated"


def test_slot_model_hides_level_gated(addon):
    a = boot(addon)
    slots = [s["slot"] for s in a.eval("ns.Options:SlotModel(1)").values()]
    assert "slotC" not in slots and "slotD" not in slots


def test_burst_model_order(addon):
    a = boot(addon)
    a.run("ns.Sets:AddBurst(1, 33); ns.Sets:AddBurst(1, 30)")
    m = list(a.eval("ns.Options:BurstModel(1)").values())
    assert [b["buffId"] for b in m] == [33, 30, 31]  # tracked in user order, then the rest by name; 32 gated
    assert [b["tracked"] for b in m] == [True, True, False]
    assert m[1]["bagCount"] == 3 and m[0]["bagCount"] == 0 and m[0]["name"] == "Another"


def test_burst_model_marks_unavailable_tracked(addon):
    a = boot(addon)
    a.run("ns.Sets:AddBurst(1, 32); ns.Sets:AddBurst(1, 30)")
    by = {b["buffId"]: b for b in a.eval("ns.Options:BurstModel(1)").values()}
    assert by[32]["unavailable"] is True and by[32]["tracked"] is True
    assert by[30]["unavailable"] is not True and by[31]["unavailable"] is not True
    panel(a)
    lbl = a.eval("ns.Options.burstChecks and (function() for _, c in ipairs(ns.Options.burstChecks) do "
                 "if c:IsShown() and c.fbBuff == 32 then return c.fbLabel:GetText() end end end)()")
    assert lbl == "Burst gated  (Unavailable)"


def test_option_text_uses_marks(addon):
    a = boot(addon)
    panel(a)
    star = "|TInterface" + chr(92) + "TargetingFrame" + chr(92) + "UI-RaidTargetingIcon_1:0|t"
    tick = "|TInterface" + chr(92) + "RaidFrame" + chr(92) + "ReadyCheck-Ready:0|t"
    assert a.eval("ns.UI.MARK_STAR") == star and a.eval("ns.UI.MARK_CHECK") == tick
    def label(buff):
        return a.eval("(function() for _, r in ipairs(ns.Options.radios) do if r:IsShown() and r.fbSlot == 'slotA' "
                      "and r.fbBuff == %d then return r.fbLabel:GetText() end end end)()" % buff)
    assert star in label(10) and tick not in label(10)
    assert tick in label(11) and star not in label(11)
    assert "Recommended" not in label(10) and "Active" not in label(11)


def test_rename_box_fits_scroll_child(addon):
    a = boot(addon)
    panel(a)
    click(a, "ns.Options.ui.rename")
    assert a.eval("ns.Options.ui.renameBox:IsShown()") is True
    pts = a.eval("(function() local p = {ns.Options.ui.renameBox:GetPoint()} return p[4] end)()")
    w = a.eval("ns.Options.ui.renameBox:GetWidth()")
    assert pts + w <= 580


def test_state_event_refreshes_open_panel(addon):
    a = boot(addon)
    panel(a)
    assert a.eval("(function() for _, r in ipairs(ns.Options.radios) do if r:IsShown() and "
                  "r.fbSlot == 'slotC' then return true end end return false end)()") is False
    a.run("local g = ns.Catalog.Build; ns.Catalog.Build = function(...) local c = g(...); "
          "c.FOOD[2].status = 'CAN_ADD'; return c end; ns.Events:Fire('FULLBUFF_STATE')")
    assert a.eval("(function() for _, r in ipairs(ns.Options.radios) do if r:IsShown() and "
                  "r.fbSlot == 'slotC' then return true end end return false end)()") is True
    assert a.errors() == []


def test_radio_click_picks(addon):
    a = boot(addon)
    panel(a)
    click(a, radio("slotA", 12))
    assert a.eval("ns.Sets:Get(1).picks.slotA") == 12
    assert a.eval("__ns.fired") >= 1
    assert a.eval(radio("slotA", 12) + ":GetChecked()") is True
    assert a.eval(radio("slotA", 10) + ":GetChecked()") is False
    assert a.errors() == []


def test_not_used_radio_sets_false(addon):
    a = boot(addon)
    panel(a)
    click(a, radio("slotA", False))
    assert a.eval("ns.Sets:Get(1).picks.slotA") is False
    assert a.eval(radio("slotA", False) + ":GetChecked()") is True
    assert a.errors() == []


def test_burst_checkbox_and_move(addon):
    a = boot(addon)
    panel(a)
    click(a, burst_widget("burstChecks", 30))
    click(a, burst_widget("burstChecks", 33))
    assert list(a.eval("ns.Sets:Get(1).burst").values()) == [30, 33]
    click(a, burst_widget("burstDown", 30))
    assert list(a.eval("ns.Sets:Get(1).burst").values()) == [33, 30]
    click(a, burst_widget("burstUp", 30))
    assert list(a.eval("ns.Sets:Get(1).burst").values()) == [30, 33]
    click(a, burst_widget("burstChecks", 33))
    assert list(a.eval("ns.Sets:Get(1).burst").values()) == [30]
    assert a.errors() == []


def test_delete_uses_confirmation(addon):
    a = boot(addon)
    panel(a)
    a.run("ns.Sets:Copy(1)")
    click(a, "ns.Options.ui.delete")
    assert a.eval("#ns.Sets:List()") == 2  # not deleted yet
    assert a.eval("#__popups.shown") == 1
    assert a.eval("__popups.shown[1].which") == "FULLBUFF_DELETE_SET"
    a.run("__accept_popup()")
    assert a.eval("#ns.Sets:List()") == 1
    assert a.errors() == []


def test_new_set_becomes_edited_and_active(addon):
    a = boot(addon)
    panel(a)
    click(a, "ns.Options.ui.new")
    assert a.eval("#ns.Sets:List()") == 2
    assert a.eval("(ns.Sets:Active())") == 2
    assert a.eval("ns.Sets:Get(2).name") == "Main 2"
    click(a, "ns.Options.ui.copy")
    assert a.eval("(ns.Sets:Active())") == 3 and a.eval("ns.Sets:Get(3).name") == "Main 2 (copy)"
    assert a.errors() == []


def test_rename_enter_commits_escape_cancels(addon):
    a = boot(addon)
    panel(a)
    click(a, "ns.Options.ui.rename")
    assert a.eval("ns.Options.ui.renameBox:IsShown()") is True
    a.run("local b = ns.Options.ui.renameBox; b:SetText('Raid'); b.__scripts.OnEscapePressed(b)")
    assert a.eval("ns.Sets:Get(1).name") == "Main"
    assert a.eval("ns.Options.ui.renameBox:IsShown()") is False
    click(a, "ns.Options.ui.rename")
    a.run("local b = ns.Options.ui.renameBox; b:SetText('Raid'); b.__scripts.OnEnterPressed(b)")
    assert a.eval("ns.Sets:Get(1).name") == "Raid"
    assert a.eval("ns.Options.ui.renameBox:IsShown()") is False
    assert a.errors() == []


def test_switch_set_and_bind_spec(addon):
    a = boot(addon)
    panel(a)
    a.run("ns.Sets:Create('Second')")
    click(a, "(function() for _, b in ipairs(ns.Options.setButtons) do if b:IsShown() and b.fbSet == 2 "
             "then return b end end end)()")
    assert a.eval("(ns.Sets:Active())") == 2
    click(a, "ns.Options.ui.specs[2]")
    assert a.eval("ns.Sets:Get(2).spec") == 2
    click(a, "ns.Options.ui.specs[0]")
    assert a.eval("ns.Sets:Get(2).spec") is None
    assert a.errors() == []


def test_spec_labels_use_tree_names(addon):
    a = boot(addon)
    assert a.eval("ns.Options:SpecLabel(2)") == "Arms"
    a2 = addon(mocks={"GetSpecializationInfo": None, "GetTalentTabInfo": None})
    a2.load_addon()
    assert a2.eval("ns.Options:SpecLabel(2)") == "Specialization tree 2"


def test_category_visibility_removed(addon):
    a = boot(addon)
    assert a.eval("ns.Options.SetCategoryHidden") is None
    assert a.eval("ns.Options.CATEGORIES") is None
    a.run("ns.DB.launcher = {point='CENTER', relPoint='CENTER', x=1, y=2}; ns.Options:ResetLayout()")
    assert a.eval("ns.DB.collapsed") is None
    for lang in ("en", "uk"):
        a.run("ns.SetLanguage(%r)" % lang)
        loc = "enUS" if lang == "en" else "ukUA"
        for key in ("OPT_CATEGORIES", "SHOW_ONLY_MISSING", "NO_BUFFS", "CATEGORY_FOOD"):
            assert a.eval("rawget(ns.Locales.%s, %r)" % (loc, key)) is None


def test_panel_builds_without_error(addon):
    for lang in ("en", "uk"):
        a = boot(addon, lang)
        panel(a)
        a.run("ns.Sets:Create('Two'); ns.Sets:Pick(1, 'slotD', 99); ns.Sets:AddBurst(1, 30)")
        a.run("ns.SetLanguage(%r); __ns.p.__scripts.OnShow(__ns.p)" % lang)
        assert a.errors() == []
    assert a.eval("ns.Options.ui.new:GetText()") == "Новий"


def test_pick_under_old_slot_key_matches_buff_slot(addon):
    # Elixir A (10) is saved under a slot key a data rebuild retired; its buff now
    # lives in slotA: the editor, the popover rows and the badge all agree.
    a = boot(addon)
    a.run("for id, b in pairs(ns.Buffs) do b.excl = ({[10]='slotA', [11]='slotA', [12]='slotA', "
          "[20]='slotB'})[id] end")
    a.run("ns.Sets:Get(1).picks = {OLD_A=10, slotA=10}; ns.Sets:Get(1).auto = nil")
    by = {s["slot"]: s for s in a.eval("ns.Options:SlotModel(1)").values()}
    assert "OLD_A" not in by and by["slotA"]["picked"] == 10
    vm = a.eval("ns.ViewModel:Build()")
    assert [r["buffId"] for r in vm["list"].values()] == [10]
    assert vm["badge"] == 1
    panel(a)
    assert a.eval(radio("slotA", 10) + ":GetChecked()") is True
    a.run("ns.Sets:Get(1).picks = {OLD_A=10}")
    click(a, radio("slotA", 10))
    assert dict(a.eval("ns.Sets:Get(1).picks")) == {"slotA": 10}
    click(a, radio("slotA", 12))
    assert dict(a.eval("ns.Sets:Get(1).picks")) == {"slotA": 12}
    assert a.errors() == []


def test_rename_box_positioned_on_first_open_and_relaid_after_escape(addon):
    a = boot(addon)
    panel(a)
    assert a.eval("ns.Options.ui.renameBox.__point") is None
    click(a, "ns.Options.ui.rename")
    assert a.eval("ns.Options.ui.renameBox.__point ~= nil") is True
    spec_y = a.eval("ns.Options.ui.specs[0].__point[5]")
    a.run("local b = ns.Options.ui.renameBox; b.__scripts.OnEscapePressed(b)")
    assert a.eval("ns.Options.ui.renameBox:IsShown()") is False
    # layout redone without the box row: the spec radios move back up by its height
    assert a.eval("ns.Options.ui.specs[0].__point[5]") == spec_y + 26
    click(a, "ns.Options.ui.rename")
    assert a.eval("ns.Options.ui.specs[0].__point[5]") == spec_y
    a.run("local b = ns.Options.ui.renameBox; b.__scripts.OnEditFocusLost(b)")
    assert a.eval("ns.Options.ui.specs[0].__point[5]") == spec_y + 26
    click(a, "ns.Options.ui.rename")
    a.run("local b = ns.Options.ui.renameBox; b:SetText('Main'); b.__scripts.OnEnterPressed(b)")
    assert a.eval("ns.Options.ui.specs[0].__point[5]") == spec_y + 26
    assert a.errors() == []


def test_auto_label_shown_for_auto_set(addon):
    for lang, text in (("en", "Follows recommendations (edit any slot to customize)"),
                       ("uk", "Слідує рекомендаціям (змініть будь-який слот, щоб налаштувати)")):
        a = boot(addon, lang)
        panel(a)
        assert a.eval("ns.Options.ui.autoLabel:IsShown()") is True
        assert a.eval("ns.Options.ui.autoLabel:GetText()") == text
        click(a, radio("slotA", 12))
        assert a.eval("ns.Options.ui.autoLabel:IsShown()") is False
        assert a.errors() == []
