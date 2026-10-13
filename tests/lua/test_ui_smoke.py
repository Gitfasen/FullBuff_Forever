import re
"""Smoke tests: UI files load against the permissive frame mock and do not raise."""


def test_ui_loads_and_toggles_twice(addon):
    a = addon()
    a.load_addon()
    a.run("ns.UI.Launcher:Create()")
    a.run("ns.UI.Popover:Toggle()")
    assert a.eval("FullBuffPopover:IsShown()") is True
    a.run("ns.UI.Popover:Toggle()")
    assert a.eval("FullBuffPopover:IsShown()") is False
    assert a.errors() == []


def test_popover_in_special_frames_once_and_detail_placeholder(addon):
    a = addon()
    a.load_addon()
    a.run("ns.UI.Popover:Toggle(); ns.UI.Popover:Toggle()")
    assert a.eval("(function() local n = 0 for _, v in ipairs(UISpecialFrames) do "
                  "if v == 'FullBuffPopover' then n = n + 1 end end return n end)()") == 1
    a.run("ns.UI.OpenDetail(123)")  # placeholder must not raise


def test_state_event_refreshes_without_error(addon):
    a = addon()
    a.load_addon()
    a.run("ns.UI.Popover:Toggle()")
    a.run("ns.PlayerState:Refresh()")
    a.flush_timers()
    assert a.errors() == []


def test_drag_refused_in_combat_and_saved_otherwise(addon):
    a = addon()
    a.load_addon()
    a.run("""
      ns.UI.Launcher:Create()
      local b = ns.UI.Launcher:GetFrame()
      local moved = 0
      b.StartMoving = function() moved = moved + 1 end
      InCombatLockdown = function() return true end
      b:GetScript("OnDragStart")(b)
      __ns.__moved_combat = moved
      InCombatLockdown = function() return false end
      b:GetScript("OnDragStart")(b)
      b:GetScript("OnDragStop")(b)
      __ns.__moved_ok = moved
    """)
    assert a.eval("__ns.__moved_combat") == 0
    assert a.eval("__ns.__moved_ok") == 1
    assert a.eval("ns.DB.launcher ~= nil") is True


FIXTURE = """
ns.Weights = {WARRIOR = {{AP=1}}}
local st = {class="WARRIOR", spec=1, level=60, stale=false, active={[1]=true},
  stats={STR=110, AP=220}, unknownAuras={}, ratios={apPerStr=2, hpPerSta=10, manaPerInt=15}}
local function E(id, cat, name, excl, fx, status, burst)
  return {id=id, cat=cat, name=name, excl=excl, fx=fx, status=status, burst=burst}
end
local cat = {order={"CLASS", "POTION"},
  CLASS={
    E(1, "CLASS", "Alpha", "s1", {STR=10}, "ACTIVE"),
    E(2, "CLASS", "Bravo", "s2", {STR=20, CRIT=2}, "CAN_ADD"),
  },
  POTION={E(6, "POTION", "Rage", nil, {AP=100}, "CAN_ADD", true)}}
ns.PlayerState.Get = function() return st end
ns.Catalog.Build = function() return cat end
ns.Buffs = {[1]={name="Alpha"}, [2]={name="Bravo", bags=2}, [3]={name="Gone"}, [6]={name="Rage", bags=0}}
ns.Slots = {s1={order=1}, s2={order=2}}
ns.Bags.CountBuff = function(_, b) return b.bags or 0 end
ns.CharDB.sets = {
  [1] = {name="Main", picks={s1=1, s2=2}, burst={6}},
  [2] = {name="Empty", picks={s1=false}, burst={}},
}
ns.CharDB.activeSet = 1
ns.ViewModel:Invalidate()
"""

CHECK = "|TInterface" + chr(92) + "RaidFrame" + chr(92) + "ReadyCheck-Ready:0|t"


def popover_lines(a):
    a.run("""
      local lines, used = ns.UI.Popover:GetLines()
      local out = {}
      for i = 1, used do
        local b = lines[i]
        out[#out + 1] = {kind = b.fbKind, id = b.fbId, name = b.name:GetText(), sub = b.sub:GetText(),
                         c2 = b.c2:GetText()}
      end
      __ns.__lines = out
    """)
    return list(a.eval("__ns.__lines").values())


BS = chr(92)  # a single backslash
SINGLE = re.compile("Interface" + re.escape(BS) + "(?!" + re.escape(BS) + ")")


def single_backslash_lines(text):
    return [n for n, line in enumerate(text.splitlines(), 1) if SINGLE.search(line)]


def test_scanner_detects_single_backslash():
    bad = 'local x = "Interface' + BS + 'Icons' + BS + 'X"'
    good = 'local x = "Interface' + BS * 2 + 'Icons' + BS * 2 + 'X"'
    assert single_backslash_lines(bad) == [1]
    assert single_backslash_lines(good) == []
    assert single_backslash_lines('local x = "Interface/Icons/X"') == []


def test_no_single_backslash_texture_paths():
    from harness import ADDON_DIR
    bad = []
    for f in ADDON_DIR.rglob("*.lua"):
        for n in single_backslash_lines(f.read_text(encoding="utf-8")):
            bad.append("%s:%d" % (f.name, n))
    assert bad == []


def test_launcher_texture_and_tooltip(addon):
    a = addon()
    a.load_addon()
    a.run(FIXTURE)
    a.run("ns.UI.Launcher:Create()")
    assert a.eval("ns.UI.Launcher:GetFrame() ~= nil")
    a.run("""
      local b = ns.UI.Launcher:GetFrame()
      b:GetScript("OnEnter")(b)
    """)
    lines = list(a.eval("GameTooltip.__lines").values())
    assert lines[0] == "FullBuff"
    assert any(l.startswith("Current / maximum | ") and l.endswith("%") for l in lines)
    assert "Missing buffs: 2" in lines  # Bravo + burst Rage (no bags)
    assert "Bravo" in lines and "Rage" in lines


def test_launcher_icon_path_exact(addon):
    a = addon()
    a.run("""
      __ns.__tex = {}
      local orig = CreateFrame
      CreateFrame = function(...)
        local f = orig(...)
        local ct = f.CreateTexture
        f.CreateTexture = function(self, ...)
          local t = ct(self, ...)
          local st = t.SetTexture
          t.SetTexture = function(s, path) table.insert(__ns.__tex, path); return st(s, path) end
          return t
        end
        return f
      end
    """)
    a.load_addon()  # FULLBUFF_LOADED creates the launcher
    paths = list(a.eval("__ns.__tex").values())
    assert "Interface\\Icons\\Spell_Holy_WordFortitude" in paths


def test_popover_set_rows_marks(addon):
    a = addon()
    a.load_addon()
    a.run(FIXTURE)
    a.run("ns.UI.Popover:Toggle()")
    lines = popover_lines(a)
    items = [l for l in lines if l["kind"] == "item"]
    # ACTIVE first with a check mark, then MISSING with its bag count; no stars
    assert [l["name"] for l in items] == [CHECK + " Alpha", "Bravo"]
    assert items[0]["sub"] == "+10 Strength"
    assert items[1]["sub"] == "+20 Strength, +2% Critical strike  in bags ×2"
    burst = [l for l in lines if l["kind"] == "burst"]
    assert [(l["name"], l["c2"]) for l in burst] == [("Rage", "|cffff2020×0|r")]
    assert any(l["name"] == "Potions & trinkets" for l in lines)
    assert a.errors() == []


def test_popover_burst_with_bags_is_plain(addon):
    a = addon()
    a.load_addon()
    a.run(FIXTURE)
    a.run("ns.Buffs[6].bags = 3; ns.ViewModel:Invalidate(); ns.UI.Popover:Toggle()")
    burst = [l for l in popover_lines(a) if l["kind"] == "burst"]
    assert burst[0]["c2"] == "×3"


def test_popover_unavailable_row(addon):
    a = addon()
    a.load_addon()
    a.run(FIXTURE)
    a.run("ns.CharDB.sets[1].picks.zz = 3; ns.ViewModel:Invalidate(); ns.UI.Popover:Toggle()")
    items = [l for l in popover_lines(a) if l["kind"] == "item"]
    last = items[-1]
    assert last["name"] == "Gone" and last["id"] is None
    assert last["sub"] == "unavailable — pick a replacement in settings"


def test_popover_empty_set_button_opens_options(addon):
    a = addon()
    a.load_addon()
    a.run(FIXTURE)
    a.run("ns.CharDB.activeSet = 2; ns.ViewModel:Invalidate(); ns.UI.Popover:Toggle()")
    lines = popover_lines(a)
    assert any(l["kind"] == "empty" and l["name"] == "Set is empty — configure it in settings"
               for l in lines)
    assert not [l for l in lines if l["kind"] in ("item", "burst")]
    a.run("""
      __ns.__opened = 0
      ns.UI.OpenOptions = function() __ns.__opened = __ns.__opened + 1 end
      local lines, used = ns.UI.Popover:GetLines()
      for i = 1, used do
        if lines[i].fbKind == "options" then lines[i]:GetScript("OnClick")(lines[i]) end
      end
    """)
    assert a.eval("__ns.__opened") == 1


def test_set_dropdown_switches_active(addon):
    a = addon()
    a.load_addon()
    a.run(FIXTURE)
    a.run("ns.UI.Popover:Toggle()")
    btn = "ns.UI.Popover:GetSetButton()"
    assert a.eval(btn + ":GetText()") == "Set: Main"
    a.run("%s:GetScript('OnClick')(%s)" % (btn, btn))
    assert a.eval("(ns.Sets:Active())") == 2
    assert a.eval(btn + ":GetText()") == "Set: Empty"
    assert any(l["kind"] == "empty" for l in popover_lines(a))
    a.run("%s:GetScript('OnClick')(%s)" % (btn, btn))  # wraps around
    assert a.eval("(ns.Sets:Active())") == 1
    assert a.errors() == []


def test_launcher_tooltip_set_name(addon):
    a = addon()
    a.load_addon()
    a.run(FIXTURE)
    a.run("ns.UI.Launcher:Create(); local b = ns.UI.Launcher:GetFrame(); b:GetScript('OnEnter')(b)")
    lines = list(a.eval("GameTooltip.__lines").values())
    assert "Set: Main" in lines


def test_bags_and_set_events_rebuild_view_model(addon):
    a = addon()
    a.load_addon()
    a.run(FIXTURE)
    a.run("ns.UI.Launcher:Create(); ns.UI.Popover:Toggle()")
    a.run("""
      __builds = 0
      local build = ns.ViewModel.Build
      ns.ViewModel.Build = function(...) __builds = __builds + 1 return build(...) end
      ns.Buffs[2].bags = 5
    """)
    a.run("ns.Events:Fire('FULLBUFF_BAGS')")
    assert a.eval("__builds") == 1
    assert [l for l in popover_lines(a) if l["kind"] == "item"][1]["sub"].endswith("×5")
    a.run("ns.Sets:SetActive(2)")
    assert a.eval("__builds") == 2


def test_active_row_highlighted_not_dimmed(addon):
    a = addon()
    a.load_addon()
    a.run(FIXTURE)
    a.run("ns.UI.Popover:Toggle()")
    a.run("""
      local lines, used = ns.UI.Popover:GetLines()
      for i = 1, used do
        local b = lines[i]
        if b.fbKind == "item" and b.fbId == 1 then
          __ns.__alpha = b:GetAlpha()
          __ns.__r, __ns.__g, __ns.__b = b.name:GetTextColor()
        end
      end
    """)
    assert a.eval("__ns.__alpha") == 1
    r, g, b = a.eval("__ns.__r"), a.eval("__ns.__g"), a.eval("__ns.__b")
    assert g > r and g > b  # green: "already have it"


def test_libs_do_not_reference_questie():
    from harness import ADDON_DIR
    hits = [str(f.relative_to(ADDON_DIR)) for f in (ADDON_DIR / "Libs").rglob("*")
            if f.is_file() and "questie" in f.read_text(encoding="utf-8", errors="ignore").lower()]
    assert hits == []


def test_viewmodel_built_once_per_state_change(addon):
    a = addon()
    a.load_addon()
    a.run("ns.UI.Launcher:Create(); ns.UI.Popover:Toggle(); ns.UI.OpenDetail(10157)")
    a.run("""
      __builds, __catalogs = 0, 0
      local build, cat = ns.ViewModel.Build, ns.Catalog.Build
      ns.ViewModel.Build = function(...) __builds = __builds + 1 return build(...) end
      ns.Catalog.Build = function(...) __catalogs = __catalogs + 1 return cat(...) end
    """)
    a.run("ns.PlayerState:Refresh()")
    a.run("ns.UI.Launcher:Refresh(); ns.UI.Popover:Refresh()")  # e.g. a tooltip re-read
    assert a.eval("__builds") == 1
    assert a.eval("__catalogs") == 1  # launcher, popover and detail card share it
    a.run("ns.SetLanguage('uk')")
    assert a.eval("__builds") == 2
    a.run("ns.Options:SetShowAllStats(true)")
    assert a.eval("__builds") == 3
    assert a.errors() == []
