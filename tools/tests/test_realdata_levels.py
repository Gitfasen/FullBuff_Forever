"""Acquisition levels in the generated addon/FullBuff/Data/Buffs.lua."""
import re
from pathlib import Path

BUFFS = Path(__file__).resolve().parents[2] / "addon" / "FullBuff" / "Data" / "Buffs.lua"


def lvl_by_name():
    out = {}
    for m in re.finditer(r'name="([^"]+)",.*? lvl=(\d+),', BUFFS.read_text(encoding="utf-8")):
        out[m.group(1)] = int(m.group(2))
    return out


def test_juju_levels():
    lv = lvl_by_name()
    for n in ("Juju Power", "Juju Might", "Juju Guile"):
        assert lv[n] >= 55, n


def test_crystal_levels():
    lv = lvl_by_name()
    for n in ("Crystal Force", "Crystal Ward"):
        assert lv[n] >= 47, n


def test_dire_maul_tribute_levels():
    lv = lvl_by_name()
    for n in ("Fengus' Ferocity", "Mol'dar's Moxie", "Slip'kik's Savvy"):
        assert lv[n] == 55, n
