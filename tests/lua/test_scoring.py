import pytest

def state(cls="WARRIOR", spec=1, ratios=None, stats=None):
    r = {"hpPerSta": 10, "manaPerInt": 15}
    r.update(ratios or {})
    return {"class": cls, "spec": spec, "stats": stats or {}, "ratios": r}


def test_expand_str_to_ap_for_warrior(addon):
    a = addon()
    a.ns["__st"] = a.to_lua(state(ratios={"apPerStr": 2}))
    out = a.eval("ns.Scoring:Expand({STR=10, STA=2}, __ns.__st)")
    assert out["STR"] == 10 and out["AP"] == 20 and out["HP"] == 20


def test_expand_agi_int_and_nil_ratio(addon):
    a = addon()
    a.ns["__st"] = a.to_lua(state(ratios={"apPerAgi": 1, "rapPerAgi": 2, "critPerAgi": 0.05,
                                           "spellCritPerInt": 0.01}))
    out = a.eval("ns.Scoring:Expand({AGI=10, INT=100}, __ns.__st)")
    assert out["AP"] == 10 and out["RAP"] == 20 and out["ARMOR"] == 20
    assert out["CRIT"] == pytest.approx(0.5) and out["MANA"] == 1500
    assert out["SPELL_CRIT"] == pytest.approx(1.0)
    a.ns["__st"] = a.to_lua(state())
    out = a.eval("ns.Scoring:Expand({AGI=10, STR=5}, __ns.__st)")
    assert out["AP"] is None and out["RAP"] is None and out["ARMOR"] == 20


def test_expand_percent_keys(addon):
    a = addon()
    a.ns["__st"] = a.to_lua(state(ratios={"apPerStr": 2},
                                  stats={"STR": 100, "AGI": 50, "ARMOR": 1000}))
    out = a.eval("ns.Scoring:Expand({STR_PCT=10, ARMOR_PCT=5}, __ns.__st)")
    assert out["STR"] == 10 and out["AP"] == 20 and out["ARMOR"] == 50
    assert out["STR_PCT"] is None
    out = a.eval("ns.Scoring:Expand({STAT_PCT=10}, __ns.__st)")
    assert out["STR"] == 10 and out["AGI"] == 5 and out["INT"] is None
    # armor: flat from AGI (5*2) only, no double counting
    assert out["ARMOR"] == 10


def test_score_uses_override(addon):
    a = addon()
    a.run("ns.Weights = {WARRIOR = {{AP=1}, {AP=1}, {AP=1}}}")
    a.ns["__st"] = a.to_lua(state())
    assert a.eval("ns.Scoring:Score({AP=10}, __ns.__st)") == 10
    a.run("ns.DB = {weightOverrides = {WARRIOR = {[1] = {AP = 3, CRIT = 2}}}}")
    assert a.eval("ns.Scoring:Score({AP=10, CRIT=1}, __ns.__st)") == 32
    w = a.eval("ns.Scoring:Weights(__ns.__st)")
    assert w["AP"] == 3 and w["CRIT"] == 2


ENTRIES = """
local function E(id, excl, fx, status, burst)
  return {id=id, excl=excl, fx=fx, status=status or "CAN_ADD", burst=burst, cat="FOOD"}
end
__cat = {
  FOOD = { E(5, "food", {AP=10}), E(3, "food", {AP=10}), E(4, "food", {AP=2}),
           E(6, "food", {AP=99}, "UNAVAILABLE"), E(7, "flask", {AP=50}, "ACTIVE"),
           E(8, "flask", {AP=500}, "CAN_ADD", true), E(9, "z", {SPI=100}) },
  order = {"FOOD"},
}
"""


def mark(a):
    a.ns["__st"] = a.to_lua(state())
    a.run("ns.Weights = {WARRIOR = {{AP=1}, {AP=1}, {AP=1}}}\n" + ENTRIES.replace("__cat", "__ns.__cat") +
          "\n__ns.__out = ns.Scoring:MarkRecommended(__ns.__cat, __ns.__st)")
    return {e["id"]: e["recommended"] for e in a.eval("__ns.__cat.FOOD").values()}


def test_recommended_one_per_group(addon):
    a = addon()
    r = mark(a)
    assert r[3] is True and r[5] is None and r[4] is None and r[6] is None
    assert r[7] is True
    assert r[9] is None  # zero score: not recommended
    assert a.eval("__ns.__out == __ns.__cat")
    # idempotent
    a.run("ns.Scoring:MarkRecommended(__ns.__cat, __ns.__st)")
    r2 = {e["id"]: e["recommended"] for e in a.eval("__ns.__cat.FOOD").values()}
    assert r2 == r


def test_burst_never_recommended(addon):
    a = addon()
    assert mark(a)[8] is None


def test_relevant_stats_for_rogue(addon):
    a = addon()
    a.run("ns.Weights = {ROGUE = {{AP=1, CRIT=18, HIT=18}, {AP=1}, {AP=1}}}")
    a.ns["__st"] = a.to_lua(state("ROGUE", 1, {"apPerStr": 2, "apPerAgi": 1, "critPerAgi": 0.05}))
    out = list(a.eval("ns.Scoring:RelevantStats(__ns.__st)").values())
    assert out == ["STR", "AGI", "AP", "CRIT", "HIT"]
    assert "INT" not in out and "SPI" not in out
