"""Map pin logic (ns.Pins) against the recording HereBeDragons mock."""

SETUP = """
ns.Buffs = {[1] = {name="Strength"}, [2] = {name="Might"}}
ns.Sources = {
  [1] = {
    {kind="vendor", name="Bob", mapID=1429, x=0.25, y=0.5},
    {kind="quest", name="A Quest"},
    {kind="drop", name="Wolf", mapID=1411, x=0.1, y=0.2},
  },
  [2] = {{kind="vendor", name="Al", mapID=1429, x=0.3, y=0.4}},
}
"""


def boot(addon):
    a = addon()
    a.load_addon()
    a.run(SETUP)
    return a


def calls(a, fn=None):
    out = [dict(c) for c in a.eval("__hbd.calls").values()]
    return [c for c in out if fn is None or c["fn"] == fn]


def keys(a):
    return sorted(v["key"] for v in a.eval("ns.Pins:List()").values())


def test_pin_all_adds_each_location(addon):
    a = boot(addon)
    assert a.eval("ns.Pins:AddAll(1)") == 2
    for fn in ("AddWorldMapIconMap", "AddMinimapIconMap"):
        cs = calls(a, fn)
        assert sorted((c["mapID"], c["x"], c["y"]) for c in cs) == [(1411, 0.1, 0.2), (1429, 0.25, 0.5)]
    assert keys(a) == ["1:1", "1:3"]


def test_single_add_and_non_pinnable_refused(addon):
    a = boot(addon)
    assert a.eval("ns.Pins:Add(1, 2)") is False  # quest without coordinates
    assert a.eval("ns.Pins:Add(1, 9)") is False  # no such source
    assert a.eval("ns.Pins:Add(99, 1)") is False
    assert calls(a) == []
    assert a.eval("ns.Pins:Add(1, 1)") is True
    assert a.eval("ns.Pins:Add(1, 1)") is True  # idempotent: old drawing replaced
    assert keys(a) == ["1:1"]
    assert len(calls(a, "AddWorldMapIconMap")) == 2
    assert len(calls(a, "RemoveWorldMapIcon")) == 1


def test_pins_persist_and_restore(addon):
    a = boot(addon)
    a.run("ns.Pins:Add(1, 1); ns.Pins:Add(2, 1)")
    assert a.eval("ns.CharDB.pins['1:1'] ~= nil and ns.CharDB.pins['2:1'] ~= nil") is True
    # simulate /reload: fresh state, same saved table contents
    b = addon()
    b.run("FullBuffCharDB = {pins = {['1:1'] = true, ['2:1'] = true, ['7:1'] = true, ['1:2'] = true}}")
    b.run(SETUP)
    b.load_addon()  # FULLBUFF_LOADED restores the saved pins
    assert len(calls(b, "AddWorldMapIconMap")) == 2
    assert len(calls(b, "AddMinimapIconMap")) == 2
    # entries whose source is gone or not pinnable are dropped
    assert keys(b) == ["1:1", "2:1"]
    assert b.eval("ns.CharDB.pins['7:1']") is None
    assert b.eval("ns.CharDB.pins['1:2']") is None


def test_restore_on_entering_world(addon):
    a = boot(addon)
    a.run("ns.CharDB.pins['1:1'] = true")
    a.fire_event("PLAYER_ENTERING_WORLD", False, False)
    assert len(calls(a, "AddWorldMapIconMap")) == 1


def test_clear_removes_all(addon):
    a = boot(addon)
    a.run("ns.Pins:AddAll(1)")
    a.run("ns.Pins:Clear()")
    assert len(a.eval("ns.Pins:List()")) == 0
    assert a.eval("next(ns.CharDB.pins)") is None
    assert len(calls(a, "RemoveWorldMapIcon")) == 2
    assert len(calls(a, "RemoveMinimapIcon")) == 2


def test_remove_single_and_right_click(addon):
    a = boot(addon)
    a.run("ns.Pins:AddAll(1)")
    a.run("ns.Pins:Remove('1:1')")
    assert keys(a) == ["1:3"]
    # right click on a drawn pin icon removes it; left click does not
    a.run("""
      local icon = ns.Pins:GetIcon('1:3', 'world')
      icon:GetScript('OnMouseUp')(icon, 'LeftButton')
      __ns.__after_left = #ns.Pins:List()
      icon:GetScript('OnMouseUp')(icon, 'RightButton')
    """)
    assert a.eval("__ns.__after_left") == 1
    assert len(a.eval("ns.Pins:List()")) == 0


def test_pin_tooltip_has_buff_and_source(addon):
    a = boot(addon)
    a.run("ns.Pins:Add(1, 1)")
    a.run("local i = ns.Pins:GetIcon('1:1', 'minimap'); i:GetScript('OnEnter')(i)")
    lines = list(a.eval("GameTooltip.__lines").values())
    assert lines[0] == "Strength"
    assert lines[1] == "Vendor: Bob (Zone1429 25.0, 50.0)"


def test_nil_zone_name_and_no_hbd(addon):
    a = addon()
    a.mock("C_Map.GetMapInfo", "function() return nil end")
    a.run("__hbd.available = false")
    a.load_addon()
    a.run(SETUP)
    assert a.eval("ns.Pins:Add(1, 1)") is True  # still recorded, just not drawn
    assert calls(a) == []
    assert a.eval("ns.CharDB.pins['1:1'] ~= nil") is True
    assert a.errors() == []


def test_pin_stores_coords_and_restore_drops_moved_source(addon):
    a = boot(addon)
    a.run("ns.Pins:Add(1, 1); ns.Pins:Add(1, 3)")
    saved = a.eval("ns.CharDB.pins['1:1']")
    assert (saved["mapID"], saved["x"], saved["y"]) == (1429, 0.25, 0.5)
    # data update: source 1 of buff 1 is now somewhere else (index reused)
    a.run("ns.Sources[1][1] = {kind='vendor', name='Other', mapID=1453, x=0.6, y=0.7}")
    a.run("ns.Pins:Restore()")
    assert keys(a) == ["1:3"]
    assert a.eval("ns.CharDB.pins['1:1']") is None


def test_legacy_true_pin_upgraded_with_coords(addon):
    a = boot(addon)
    a.run("ns.CharDB.pins['2:1'] = true; ns.Pins:Restore()")
    assert keys(a) == ["2:1"]
    assert a.eval("ns.CharDB.pins['2:1'].mapID") == 1429


def test_add_opens_map_on_the_pins_map(addon):
    a = boot(addon)
    assert a.eval("WorldMapFrame:IsShown()") is False
    a.run("ns.Pins:Add(1, 3)")
    assert a.eval("WorldMapFrame:IsShown()") is True
    assert a.eval("__map.mapID") == 1411 and a.eval("__map.shows") == 1
    a.run("ns.Pins:Add(2, 1)")  # already open: only the map changes
    assert a.eval("__map.mapID") == 1429 and a.eval("__map.shows") == 1


def test_refused_add_does_not_open_map(addon):
    a = boot(addon)
    a.run("ns.Pins:Add(1, 2)")
    assert a.eval("WorldMapFrame:IsShown()") is False and a.eval("__map.mapID") is None


def test_pin_all_focuses_first_added_pin(addon):
    a = boot(addon)
    assert a.eval("ns.Pins:AddAll(1)") == 2
    assert list(a.eval("__map.mapIDs").values()) == [1429]  # source 1 is first; source 2 has no coords
    assert a.eval("WorldMapFrame:IsShown()") is True


def test_no_map_in_combat_but_pins_added(addon):
    a = boot(addon)
    a.run("InCombatLockdown = function() return true end")
    a.run("ns.Pins:Add(1, 1)")
    assert a.eval("ns.Pins:AddAll(1)") == 2
    assert a.eval("WorldMapFrame:IsShown()") is False and a.eval("__map.shows") == 0
    assert keys(a) == ["1:1", "1:3"]


def test_detail_card_buttons_focus_map(addon):
    a = boot(addon)
    a.run("ns.UI.OpenDetail(1)")
    a.run("local b = ns.Detail:GetButtons().pinAll; b:GetScript('OnClick')(b)")
    assert a.eval("__map.mapID") == 1429 and a.errors() == []


def test_map_error_is_swallowed(addon):
    a = boot(addon)
    a.run("WorldMapFrame.SetMapID = function() error('boom') end")
    assert a.eval("ns.Pins:Add(1, 1)") is True
    assert a.errors() == []
