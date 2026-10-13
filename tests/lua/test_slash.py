"""Slash commands, options panel logic, language switch, hidden categories."""
import re


def loaded(addon, **kw):
    a = addon(**kw)
    a.load_addon()
    return a


def msgs(a):
    return list(a.eval("(function() local t = {} for i, m in ipairs(DEFAULT_CHAT_FRAME.__messages) "
                       "do t[i] = m end return t end)()").values())


def test_lang_uk_switches_strings(addon):
    a = loaded(addon)
    a.run("SlashCmdList.FULLBUFF('lang uk')")
    assert a.eval("ns.DB.lang") == "uk"
    assert a.eval("ns.L.OPT_LANGUAGE") != "Language"
    assert re.search("[Ѐ-ӿ]", a.eval("ns.L.OPT_LANGUAGE"))
    a.run("SlashCmdList.FULLBUFF('lang en')")
    assert a.eval("ns.L.OPT_LANGUAGE") == "Language"
    assert a.errors() == []


def test_lang_invalid_prints_usage(addon):
    a = loaded(addon)
    a.run("SlashCmdList.FULLBUFF('lang xx')")
    m = msgs(a)
    assert any("/fullbuff lang" in x for x in m)
    assert a.eval("ns.DB.lang") == "en"
    a.run("SlashCmdList.FULLBUFF('bogus')")
    assert any("/fullbuff debug" in x for x in msgs(a))


def test_slash_registered_and_toggle(addon):
    a = loaded(addon)
    assert a.eval("SLASH_FULLBUFF1") == "/fullbuff"
    a.run("SlashCmdList.FULLBUFF('')")
    assert a.eval("FullBuffPopover:IsShown()") is True
    a.run("FullBuff_OnCompartmentClick()")
    assert a.eval("FullBuffPopover:IsShown()") is False
    assert a.errors() == []


def test_debug_lists_unknown_auras(addon):
    a = loaded(addon)
    a.run("""
      local s = ns.PlayerState:Get()
      s.unknownAuras = {[4242] = "Mystery Brew"}
      s.stale = true
      SlashCmdList.FULLBUFF('debug')
    """)
    m = "\n".join(msgs(a))
    assert "4242" in m and "Mystery Brew" in m
    assert "stale" in m.lower()
    a.run("ns.PlayerState:Get().stale = false; DEFAULT_CHAT_FRAME.__messages = {}; SlashCmdList.FULLBUFF('debug')")
    assert "stale: no" in "\n".join(msgs(a)).lower()


def test_reset_clears_position(addon):
    a = loaded(addon)
    a.run("""
      ns.UI.Launcher:Create()
      ns.DB.launcher = {point='CENTER', relPoint='CENTER', x=5, y=6}
      ns.DB.collapsed = {FOOD = true}
      SlashCmdList.FULLBUFF('reset')
    """)
    assert a.eval("ns.DB.launcher") is None
    assert a.eval("next(ns.DB.collapsed) == nil") is True
    assert a.errors() == []


def test_hidden_category_excluded_from_viewmodel(addon):
    a = loaded(addon)
    a.run("""
      ns.PlayerState:Get()
      local function cats() local t = {} for _, s in ipairs(ns.ViewModel:Build().sections) do t[s.cat] = true end return t end
      __ns.before = cats()
      ns.DB.hiddenCats = {FOOD = true}
      __ns.after = cats()
      __ns.badgeHidden = ns.ViewModel:Build().badge
      ns.DB.hiddenCats = {}
      __ns.badgeShown = ns.ViewModel:Build().badge
    """)
    assert a.eval("__ns.before.FOOD") is True
    assert a.eval("__ns.after.FOOD") is None
    assert a.eval("__ns.badgeHidden") == a.eval("__ns.badgeShown")


def test_options_setters_recompute_and_apply(addon):
    a = loaded(addon)
    a.run("ns.UI.Launcher:Create()")
    a.run("""
      __ns.fired = 0
      ns.Events:On("FULLBUFF_STATE", function() __ns.fired = __ns.fired + 1 end)
      ns.Options:SetSpecOverride(2)
    """)
    assert a.eval("ns.CharDB.specOverride") == 2
    assert a.eval("ns.PlayerState:Get().spec") == 2
    assert a.eval("__ns.fired") >= 1
    a.run("ns.Options:SetSpecOverride(nil)")
    assert a.eval("ns.CharDB.specOverride") is None
    a.run("ns.Options:SetWeight('AP', 3)")
    assert a.eval("ns.DB.weightOverrides.WARRIOR[ns.PlayerState:Get().spec].AP") == 3
    a.run("ns.Options:SetWeight('AP', nil)")
    assert a.eval("ns.DB.weightOverrides.WARRIOR[ns.PlayerState:Get().spec].AP") is None
    a.run("ns.Options:SetShowAllStats(true)")
    assert a.eval("ns.DB.showAllStats") is True
    a.run("ns.Options:SetCategoryHidden('FOOD', true)")
    assert a.eval("ns.DB.hiddenCats.FOOD") is True
    a.run("ns.Options:SetCategoryHidden('FOOD', false)")
    assert a.eval("ns.DB.hiddenCats.FOOD") is None
    a.run("ns.Options:SetScale(9)")
    assert a.eval("ns.DB.scale") == 2.0
    assert a.eval("ns.UI.Launcher:GetFrame().__scale") == 2.0
    a.run("ns.Options:SetScale(0.1)")
    assert a.eval("ns.DB.scale") == 0.5
    assert a.errors() == []


def test_settings_category_and_open(addon):
    a = loaded(addon)
    assert a.eval("#__settings.categories") == 1
    assert a.eval("__settings.categories[1].name") == "FullBuff"
    assert a.eval("__settings.categories[1].registered") is True
    a.run("ns.UI.OpenOptions()")
    assert a.eval("__settings.opened[1]") == 1
    # panel shows and rebuilds without errors, also in Ukrainian
    a.run("local f = __settings.categories[1].frame; f.__scripts.OnShow(f); ns.SetLanguage('uk'); f.__scripts.OnShow(f)")
    assert a.errors() == []


def test_no_settings_api_is_guarded(addon):
    printed = []
    a = addon(mocks={"Settings": None, "print": lambda *args: printed.append(args)})
    a.load_addon()
    a.run("ns.UI.OpenOptions(); ns.UI.OpenOptions()")
    assert a.errors() == []
    assert len(printed) == 1


def test_weight_override_changes_recommendation(addon):
    a = loaded(addon)
    a.run("""
      ns.Weights = {WARRIOR = {{AP=1}, {AP=1}, {AP=1}}}
      local function E(id, name, fx)
        return {id=id, cat="FOOD", name=name, excl="food", fx=fx, status="CAN_ADD"}
      end
      local function rec()
        local cat = {order = {"FOOD"}, FOOD = {E(1, "A", {AP=10}), E(2, "B", {HIT=10})}}
        local st = {class="WARRIOR", spec=1, level=60, active={}, stats={AP=100, HIT=0},
                    unknownAuras={}, ratios={apPerStr=2, hpPerSta=10, manaPerInt=15}}
        local vm = ns.ViewModel:Build(st, cat)
        for _, it in ipairs(vm.sections[1].items) do if it.recommended then return it.id end end
      end
      __ns.r1 = rec()
      ns.Options:SetWeight('HIT', 5)
      __ns.r2 = rec()
    """)
    assert a.eval("__ns.r1") == 1 and a.eval("__ns.r2") == 2


def test_show_all_stats_changes_rows(addon):
    a = loaded(addon)
    a.run("""
      __ns.n1 = #ns.ViewModel:Build().header.rows
      ns.Options:SetShowAllStats(true)
      __ns.n2 = #ns.ViewModel:Build().header.rows
    """)
    assert a.eval("__ns.n2") > a.eval("__ns.n1")


def test_weight_rejects_nonfinite(addon):
    a = loaded(addon)
    a.run("ns.Options:SetWeight('AP', 2); ns.Options:SetWeight('AP', tonumber('1e999'))")
    assert a.eval("ns.DB.weightOverrides.WARRIOR[1].AP") == 2
    assert a.errors() == []


def test_build_failure_reported_and_safe(addon):
    printed = []
    a = addon(mocks={"print": lambda *args: printed.append(args)})
    a.mock("CreateFrame", None)  # make Build throw on first widget
    a.load_addon()
    assert len(a.errors()) >= 1
    assert len(printed) >= 1
    a.run("ns.UI.OpenOptions()")
    assert len(printed) >= 2
    a.run("ns.Events:Fire('FULLBUFF_LANGUAGE', 'uk'); ns.Options:Refresh()")
    assert a.eval("#__settings.categories") == 0


def test_slash_does_not_assign_blizzard_slashcmdlist():
    from harness import ADDON_DIR
    src = (ADDON_DIR / "Core" / "Slash.lua").read_text(encoding="utf-8")
    assert not re.search(r"^\s*SlashCmdList\s*=", src, re.M)


def test_compartment_right_click_opens_options(addon):
    a = loaded(addon)
    a.run("FullBuff_OnCompartmentClick('FullBuff', 'RightButton')")
    assert a.eval("__settings.opened[1]") == 1
    assert a.eval("FullBuffPopover and FullBuffPopover:IsShown() or false") is False
    a.run("FullBuff_OnCompartmentClick('FullBuff', 'LeftButton')")
    assert a.eval("FullBuffPopover:IsShown()") is True
    assert a.errors() == []


def test_unused_saved_defaults_removed(addon):
    a = loaded(addon)
    for key in ("spec", "categories", "weights"):
        assert a.eval("ns.Defaults.DB.%s" % key) is None
        assert a.eval("ns.DB.%s" % key) is None
