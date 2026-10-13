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
local function E(id, cat, name, fx, status)
  return {id=id, cat=cat, name=name, fx=fx, status=status}
end
local cat = {order={"CLASS"}, CLASS={
  E(1, "CLASS", "Alpha", {STR=10}, "ACTIVE"),
  E(2, "CLASS", "Bravo", {STR=20, CRIT=2}, "CAN_ADD"),
}}
ns.PlayerState.Get = function() return st end
ns.Catalog.Build = function() return cat end
"""


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
    assert "Missing buffs: 1" in lines
    assert "Bravo" in lines


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


def test_popover_rows(addon):
    a = addon()
    a.load_addon()
    a.run(FIXTURE)
    a.run("ns.UI.Popover:Toggle()")
    a.run("""
      local lines, used = ns.UI.Popover:GetLines()
      local names, subs = {}, {}
      for i = 1, used do
        local b = lines[i]
        if b.fbKind == "item" then
          names[#names + 1] = b.name:GetText()
          subs[#subs + 1] = b.sub:GetText()
        end
      end
      __ns.__names, __ns.__subs = names, subs
    """)
    names = list(a.eval("__ns.__names").values())
    subs = list(a.eval("__ns.__subs").values())
    star = "|TInterface" + BS + "TargetingFrame" + BS + "UI-RaidTargetingIcon_1:0|t"
    # CAN_ADD first; both are the best in their (own) group, so both carry the raid-star marker
    assert names == [star + " Bravo", star + " Alpha"]
    assert subs[0] == "+20 Strength, +2% Critical strike"
