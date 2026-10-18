"""Detail model tests (ns.Detail:Model)."""

SETUP = """
ns.Weights = {WARRIOR = {{AP=1}}}
ns.Buffs = {
  [1] = {name="Strength", cat="ELIXIR", fx={STR=8, CRIT=2}, dur=5400, lvl=20, excl="E:Str"},
  [2] = {name="Strength", cat="SCROLL", fx={STR=9}, dur=1800, lvl=25, excl="E:Str"},
  [3] = {name="Might", cat="ELIXIR", fx={STR=12}, dur=3600, lvl=40, excl="E:Str"},
  [4] = {name="Lonely", cat="FOOD", fx={AGI=5}, dur=15, lvl=0, excl="F:Lonely"},
}
ns.Sources = {
  [1] = {
    {kind="vendor", name="Bob", mapID=1429, x=0.4562, y=0.5},
    {kind="drop", name="Wolf", mapID=1429, x=0.1, y=0.2},
    {kind="quest", name="A Quest"},
    {kind="craft", name="Alchemy", note="55"},
    {kind="npc", name="Eve"},
    {kind="object", name="Chest"},
    {kind="camping", name="Candle", note="herbalism 20"},
    {kind="vendor", name="NoCoords"},
  },
  [2] = {},
}
local st = {class="WARRIOR", spec=1, level=60, stale=false, active={},
  stats={STR=100, AP=200}, unknownAuras={}, ratios={apPerStr=2, hpPerSta=10, manaPerInt=15}}
ns.PlayerState.Get = function() return st end
__ns.__m = ns.Detail:Model(%d)
"""


def model(addon, bid, lang=None):
    a = addon()
    a.load_addon()
    if lang:
        a.run("ns.SetLanguage('%s')" % lang)
    a.run(SETUP % bid)
    return a, a.eval("__ns.__m")


def texts(m):
    return [s["text"] for s in m["sources"].values()]


def test_detail_lists_all_sources(addon):
    a, m = model(addon, 1)
    assert m["name"] == "Strength"
    assert texts(m) == [
        "Vendor: Bob (Zone1429 45.6, 50.0)",
        "Drop: Wolf",
        "Quest: A Quest",
        "Crafted: Alchemy 55",
        "NPC: Eve",
        "Object: Chest",
        "Camping: Candle (herbalism 20)",
        "Vendor: NoCoords",
    ]
    assert m["durText"] == "1 h 30 min"
    assert m["minLevel"] == 20
    assert list(m["fxLines"].values()) == ["+8 Strength", "+2% Critical strike"]


def test_no_sources_shows_unknown(addon):
    for bid in (2, 4):  # empty list and missing entry
        a, m = model(addon, bid)
        assert texts(m) == ["Source unknown"]
        assert m["sources"][1]["pinnable"] is False


def test_group_members_listed(addon):
    a, m = model(addon, 1)
    members = sorted(m["groupMembers"].values())
    # same-named members are told apart by their effect
    assert members == ["Might", "Strength (+9 Strength)"]
    a, m = model(addon, 4)
    assert len(m["groupMembers"]) == 0
    assert m["durText"] == "15 sec"


def test_non_coord_source_not_pinnable(addon):
    a, m = model(addon, 1)
    pin = [(s["pinnable"], s["index"]) for s in m["sources"].values()]
    assert pin == [(True, 1), (True, 2), (False, 3), (False, 4), (False, 5), (False, 6), (False, 7), (False, 8)]


def test_score_present_and_localized_uk(addon):
    a, m = model(addon, 1)
    assert m["score"] > 0
    a, m = model(addon, 1, lang="uk")
    assert m["sources"][1]["text"].startswith("Торговець: Bob (")
    assert m["durText"] == "1 год 30 хв"


def test_non_vendor_rows_carry_location(addon):
    a, m = model(addon, 1)
    locs = [s["loc"] for s in m["sources"].values()]
    assert locs[0] is None                    # vendor text already has it
    assert locs[1] == "Zone1429 10.0, 20.0"   # drop with coordinates
    assert locs[2:] == [None] * 6


def test_card_buttons_drive_pins(addon):
    a = addon()
    a.load_addon()
    a.run(SETUP % 1)
    a.run("ns.UI.OpenDetail(1)")
    assert a.eval("FullBuffDetail:IsShown()") is True
    a.run("""
      local card = ns.Detail:GetFrame()
      local btns = ns.Detail:GetButtons()
      local rows = ns.Detail:GetRows()
      __ns.__pinnable = rows[1].pin:IsShown() and rows[3].pin:IsShown() == false
      rows[1].pin:GetScript('OnClick')(rows[1].pin)
      __ns.__p1 = ns.Pins:Has('1:1')
      rows[1].pin:GetScript('OnClick')(rows[1].pin)
      __ns.__p2 = ns.Pins:Has('1:1')
      btns.pinAll:GetScript('OnClick')(btns.pinAll)
      __ns.__all = #ns.Pins:List()
      btns.clear:GetScript('OnClick')(btns.clear)
      __ns.__none = #ns.Pins:List()
      ns.UI.OpenDetail(3)  -- reopening with another buff must not raise
    """)
    assert a.eval("__ns.__pinnable") is True
    assert a.eval("__ns.__p1") is True and a.eval("__ns.__p2") is False
    assert a.eval("__ns.__all") == 2 and a.eval("__ns.__none") == 0
    assert a.errors() == []
    a.run("ns.SetLanguage('uk'); ns.Pins:AddAll(1)")
    assert a.errors() == []


def test_catalog_error_is_reported_then_falls_back(addon):
    a = addon()
    a.load_addon()
    a.run(SETUP % 1)
    a.run("ns.Catalog.Build = function() error('boom') end; ns.ViewModel:Invalidate()"
          "; __ns.__m2 = ns.Detail:Model(1)")
    assert a.eval("__ns.__m2.name") == "Strength"
    assert any("boom" in e for e in a.errors())


def test_card_in_special_frames_once(addon):
    a = addon()
    a.load_addon()
    a.run("ns.UI.OpenDetail(2367); ns.UI.OpenDetail(2374)")
    assert a.eval("(function() local n = 0 for _, v in ipairs(UISpecialFrames) do "
                  "if v == 'FullBuffDetail' then n = n + 1 end end return n end)()") == 1
    assert a.errors() == []


def test_group_members_text_capped_at_six(addon):
    a = addon()
    a.load_addon()
    names = "{" + ", ".join("'B%d'" % i for i in range(1, 10)) + "}"
    assert a.eval("ns.Detail.MembersText(%s)" % names) == "B1, B2, B3, B4, B5, B6, +3 more"
    assert a.eval("ns.Detail.MembersText({'A', 'B'})") == "A, B"
    a.run("ns.SetLanguage('uk')")
    assert a.eval("ns.Detail.MembersText(%s)" % names) == "B1, B2, B3, B4, B5, B6 і ще 3"


def test_model_has_no_unused_status(addon):
    a, m = model(addon, 1)
    assert m["status"] is None


def test_card_row_pin_opens_map_on_its_mapid(addon):
    a = addon()
    a.load_addon()
    a.run(SETUP % 1)
    a.run("ns.UI.OpenDetail(1)")
    a.run("local r = ns.Detail:GetRows()[1]; r.pin:GetScript('OnClick')(r.pin)")
    assert a.eval("WorldMapFrame:IsShown()") is True
    assert a.eval("__map.mapID") == a.eval("ns.Sources[1][1].mapID")
