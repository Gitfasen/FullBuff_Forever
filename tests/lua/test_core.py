import pytest

CATEGORIES = "CLASS WORLD CAMPING FLASK ELIXIR FOOD SCROLL WEAPON QUEST TRINKET POTION".split()
STATS = ("STR AGI STA INT SPI AP RAP SPELL_DMG HEAL ARMOR HP MANA MP5 HP5 CRIT SPELL_CRIT HIT "
         "SPELL_HIT STAT_PCT ARMOR_PCT STR_PCT AGI_PCT STA_PCT INT_PCT SPI_PCT").split()
KINDS = "vendor drop quest craft npc object camping".split()
PLAIN = ("TITLE STATUS_ACTIVE STATUS_CAN_ADD STATUS_UNAVAILABLE RECOMMENDED SHOW_ONLY_MISSING "
         "STALE_AFTER_COMBAT SOURCE_UNKNOWN PIN PIN_ALL CLEAR_PINS WHERE_TO_GET DURATION MIN_LEVEL "
         "STACKS_WITH_NONE NOT_STACK_WITH SCORE OPT_SPEC OPT_SPEC_AUTO OPT_WEIGHTS OPT_CATEGORIES "
         "OPT_ALL_STATS OPT_SCALE OPT_RESET_POS OPT_LANGUAGE TOOLTIP_PROGRESS TOOLTIP_MISSING "
         "SPEC_HINT").split()


def test_isSecret_handles_missing_api(addon):
    a = addon(mocks={"issecretvalue": None})
    assert a.eval("ns.Compat.IsSecret(5)") is False


def test_isSecret_delegates_when_present(addon):
    a = addon(mocks={"issecretvalue": lambda v: v == 42})
    assert a.eval("ns.Compat.IsSecret(42)") is True
    assert a.eval("ns.Compat.IsSecret(1)") is False


def test_cannot_read_auras_in_combat(addon):
    a = addon(mocks={"InCombatLockdown": lambda: True})
    assert a.eval("ns.Compat.CanReadAuras()") is False
    b = addon(mocks={"InCombatLockdown": lambda: False})
    assert b.eval("ns.Compat.CanReadAuras()") is True


def test_debounce_coalesces(addon):
    a = addon()
    a.run("runs = 0; for i = 1, 3 do ns.Events:Debounce('k', 0.5, function() runs = runs + 1 end) end")
    assert a.eval("runs") == 0
    a.flush_timers()
    assert a.eval("runs") == 1
    a.run("ns.Events:Debounce('k', 0.5, function() runs = runs + 1 end)")
    a.flush_timers()
    assert a.eval("runs") == 2


def test_events_dispatch_game_and_internal(addon):
    a = addon()
    a.run("got = {}; ns.Events:On('PLAYER_REGEN_ENABLED', function(...) got[#got+1] = select('#', ...) end)"
          "; ns.Events:On('FULLBUFF_X', function(v) got[#got+1] = v end)")
    a.fire_event("PLAYER_REGEN_ENABLED")
    a.run("ns.Events:Fire('FULLBUFF_X', 'hi')")
    assert a.eval("got[1]") == 0
    assert a.eval("got[2]") == "hi"


def test_locale_fallback_to_english(addon):
    a = addon()
    a.run("ns.Locales.ukUA.TITLE = nil; ns.SetLanguage('uk')")
    assert a.eval("ns.L.TITLE") == a.eval("ns.Locales.enUS.TITLE")
    assert a.eval("ns.L.PIN") == a.eval("ns.Locales.ukUA.PIN")
    assert a.eval("ns.L.PIN") != a.eval("ns.Locales.enUS.PIN")


def test_set_language_stores_and_ignores_unknown(addon):
    a = addon()
    a.load_addon()
    a.run("ns.SetLanguage('uk')")
    assert a.eval("FullBuffDB.lang") == "uk"
    a.run("ns.SetLanguage('xx')")
    assert a.eval("FullBuffDB.lang") == "uk"
    a.run("ns.SetLanguage('en')")
    assert a.eval("ns.L.TITLE") == "FullBuff"


def test_ukrainian_and_english_have_same_keys(addon):
    a = addon()
    en = sorted(a.eval("(function() local t = {} for k in pairs(ns.Locales.enUS) do t[#t+1] = k end return t end)()").values())
    uk = sorted(a.eval("(function() local t = {} for k in pairs(ns.Locales.ukUA) do t[#t+1] = k end return t end)()").values())
    assert en == uk
    expected = (PLAIN + ["CATEGORY_" + c for c in CATEGORIES] + ["STAT_" + s for s in STATS]
                + ["SRC_" + k.upper() for k in KINDS])
    assert set(expected) <= set(en)


def test_ukrainian_strings_are_cyrillic(addon):
    a = addon()
    keys = list(a.eval("(function() local t = {} for k in pairs(ns.Locales.ukUA) do t[#t+1] = k end return t end)()").values())
    assert len(keys) > 50
    for key in keys:
        if key == "TITLE":
            continue
        val = a.eval("ns.Locales.ukUA['%s']" % key)
        assert any("Ѐ" <= ch <= "ӿ" for ch in val), key


def test_savedvars_nil_before_addon_loaded(addon):
    a = addon()
    assert a.eval("ns.DB") is None
    assert a.eval("FullBuffDB") is None


def test_savedvars_defaults_applied(addon):
    a = addon()
    a.load_addon()
    assert a.eval("ns.DB.lang") == "en"
    assert a.eval("ns.DB.scale") == 1
    assert a.eval("ns.DB.showAllStats") is False and a.eval("ns.DB.allStats") is None
    assert a.eval("type(ns.CharDB.pins)") == "table"
    assert a.eval("ns.DB == FullBuffDB and ns.CharDB == FullBuffCharDB")


def test_savedvars_keep_existing_and_fill_missing(addon):
    a = addon(mocks={"FullBuffDB": "{ lang = 'uk', scale = 1.5 }", "FullBuffCharDB": "{}"})
    a.load_addon()
    assert a.eval("ns.DB.scale") == 1.5
    assert a.eval("ns.DB.onlyMissing") is False
    assert a.eval("ns.L.PIN") == a.eval("ns.Locales.ukUA.PIN")


def test_other_addon_loaded_ignored(addon):
    a = addon()
    a.fire_event("ADDON_LOADED", "SomethingElse")
    assert a.eval("ns.DB") is None


def test_toc_header_and_files():
    from harness import toc_files, read_toc_header
    h = read_toc_header()
    assert h["Interface"] == "16001"
    assert h["SavedVariables"] == "FullBuffDB"
    files = toc_files()
    assert files.index("Core/Init.lua") < files.index("Core/Locale.lua") < files.index("Core/Compat.lua")
    assert files.index("Core/SavedVars.lua") < files.index("Data/Buffs.lua")


def test_debounce_respects_virtual_clock(addon):
    a = addon()
    a.run("fired = false; ns.Events:Debounce('k', 0.3, function() fired = true end)")
    a.advance(0.2)
    assert a.eval("fired") is False
    a.advance(0.1)
    assert a.eval("fired") is True
    assert a.eval("GetTime()") == pytest.approx(0.3)


def test_equal_delay_timers_are_fifo(addon):
    a = addon()
    a.run("order = {}; for i = 1, 5 do C_Timer.After(1, function() order[#order+1] = i end) end"
          "; C_Timer.After(0.5, function() order[#order+1] = 0 end)")
    a.flush_timers()
    assert list(a.eval("order").values()) == [0, 1, 2, 3, 4, 5]


def test_timers_queued_in_callbacks_run_within_window(addon):
    a = addon()
    a.run("hits = 0; C_Timer.After(1, function() hits = hits + 1; "
          "C_Timer.After(1, function() hits = hits + 1 end) end)")
    a.advance(1.5)
    assert a.eval("hits") == 1
    a.advance(0.5)
    assert a.eval("hits") == 2


def test_throwing_timer_does_not_drop_others(addon):
    a = addon()
    a.run("ran = 0; C_Timer.After(1, function() error('boom') end); "
          "C_Timer.After(2, function() ran = ran + 1 end)")
    with pytest.raises(Exception, match="boom"):
        a.flush_timers()
    assert a.eval("ran") == 1


def test_handler_error_is_isolated(addon):
    a = addon()
    a.run("ns.Events:On('FULLBUFF_T', function() error('bad') end)"
          "; ns.Events:On('FULLBUFF_T', function() ok = true end)"
          "; ns.Events:On('PLAYER_LOGIN', function() error('bad2') end)"
          "; ns.Events:On('PLAYER_LOGIN', function() ok2 = true end)")
    a.run("ns.Events:Fire('FULLBUFF_T')")
    a.fire_event("PLAYER_LOGIN")
    assert a.eval("ok") is True and a.eval("ok2") is True
    errs = a.errors()
    assert len(errs) == 2 and "bad" in errs[0] and "bad2" in errs[1]


def test_dotted_and_nested_mocks(addon):
    a = addon(mocks={
        "C_UnitAuras.GetAuraDataByIndex":
            lambda unit, i, f: {"spellId": 1, "points": [5]} if i == 1 else None,
        "C_Timer.After": lambda s, fn: None,
        "Brand.New.Thing": 7,
    })
    assert a.eval("C_UnitAuras.GetAuraDataByIndex('player', 1, 'HELPFUL').spellId") == 1
    assert a.eval("C_UnitAuras.GetAuraDataByIndex('player', 1, 'HELPFUL').points[1]") == 5
    assert a.eval("C_UnitAuras.GetAuraDataByIndex('player', 2, 'HELPFUL')") is None
    assert a.eval("type(C_UnitAuras)") == "table"
    assert a.eval("Brand.New.Thing") == 7


def test_ns_is_not_a_global(addon):
    a = addon()
    assert a.eval("rawget(_G, 'ns')") is None
    assert a.eval("ns.name") == "FullBuff"


def test_is_forever_flag(addon):
    assert addon().eval("ns.IsForever") is True
    assert addon(mocks={"WOW_PROJECT_ID": 1}).eval("ns.IsForever") is False
