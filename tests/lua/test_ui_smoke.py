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
