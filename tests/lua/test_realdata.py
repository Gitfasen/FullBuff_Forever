"""Maximum over the REAL generated Data/Buffs.lua (final review Critical #1).

Mutually exclusive consumables (flasks, weapon enchants, Well Fed foods, same-stat
elixirs/scrolls) must not stack in the maximum.
"""

MAGE = dict(stats=dict(STR=35, AGI=40, STA=70, INT=100, SPI=120, AP=25, RAP=0, SPELL_DMG=0, HEAL=0,
                       ARMOR=300, HP=1500, MANA=2300, CRIT=5.0, SPELL_CRIT=6.0, HIT=0, SPELL_HIT=0),
            ratios=dict(hpPerSta=10, manaPerInt=15, apPerStr=1, apPerAgi=0, rapPerAgi=0,
                        critPerAgi=0.05, spellCritPerInt=0.0168))
ROGUE = dict(stats=dict(STR=90, AGI=200, STA=120, INT=30, SPI=50, AP=600, RAP=200, SPELL_DMG=0, HEAL=0,
                        ARMOR=1500, HP=2500, MANA=0, CRIT=15.0, SPELL_CRIT=1.0, HIT=3.0, SPELL_HIT=0),
             ratios=dict(hpPerSta=10, manaPerInt=15, apPerStr=1, apPerAgi=1, rapPerAgi=1,
                         critPerAgi=0.0345))


def _tbl(d):
    return "{" + ", ".join("%s=%r" % (k, v) for k, v in d.items()) + "}"


def probe(addon, cls, spec, fixture):
    """Returns (result, rows {stat: (cur, max)}, chosen [(id, cat, excl, name)])."""
    a = addon()
    a.run("ns.DB = ns.DB or {}")
    a.run("__ns.__st = {class=%r, spec=%d, level=60, stale=false, stats=%s, ratios=%s,"
          " active={}, activeAura={}, unknownAuras={}}"
          % (cls, spec, _tbl(fixture["stats"]), _tbl(fixture["ratios"])))
    a.run("__ns.__cat = ns.Catalog:Build(__ns.__st)")
    a.run("__ns.__res = ns.MaxCalc:Compute(__ns.__st, __ns.__cat)")
    res = a.eval("__ns.__res")
    rows = {r["stat"]: (r["current"], r["max"]) for r in res["rows"].values()}
    chosen = a.eval("""(function()
      local out = {}
      for k, list in pairs(__ns.__cat) do
        if k ~= 'order' then
          for _, e in ipairs(list) do
            if e.recommended and not e.burst and e.status ~= 'UNAVAILABLE' then
              out[#out + 1] = {e.id, e.cat, e.excl or '', e.name}
            end
          end
        end
      end
      return out
    end)()""")
    chosen = [tuple(c.values()) for c in chosen.values()]
    return res, rows, chosen


def _assert_one_per_exclusive_family(chosen):
    flasks = [c for c in chosen if c[1] == "FLASK"]
    weapons = [c for c in chosen if c[1] == "WEAPON"]
    well_fed = [c for c in chosen if c[2] == "FOOD:Well Fed"]
    familiars = [c for c in chosen if c[3].endswith(" Familiar")]
    assert len(flasks) <= 1, flasks
    assert len(weapons) <= 1, weapons
    assert len(well_fed) <= 1, well_fed
    assert len(familiars) <= 1, familiars
    excl = [c[2] for c in chosen]
    assert len(excl) == len(set(excl)), "one chosen entry per group"


def test_real_data_mage_maximum_is_sane(addon):
    res, rows, chosen = probe(addon, "MAGE", 3, MAGE)
    _assert_one_per_exclusive_family(chosen)
    # Sanity bound: the largest real spell-damage stack at 60 is Fengus' Ferocity 230
    # (Forever value) + Rallying Cry 80 + Supreme Power 150 + one SPELL_DMG elixir 40
    # + one food 28 + one weapon enchant 45 = 573; anything above 600 means stacking.
    assert rows["SPELL_DMG"][1] <= 600, rows["SPELL_DMG"]
    assert len(chosen) <= 30, len(chosen)


def test_real_data_rogue_maximum_is_sane(addon):
    res, rows, chosen = probe(addon, "ROGUE", 2, ROGUE)
    _assert_one_per_exclusive_family(chosen)
    assert len(chosen) <= 30, len(chosen)
