"""Lua test harness for the FullBuff addon.

Usage in a test:

    def test_x(addon):
        a = addon(mocks={"InCombatLockdown": lambda: True})
        assert a.eval("ns.Compat.CanReadAuras()") is False
        a.load_addon()          # fires ADDON_LOADED "FullBuff"
        a.fire_event("PLAYER_REGEN_ENABLED")
        a.flush_timers()
"""
from pathlib import Path

import pytest

try:
    from lupa.lua51 import LuaRuntime
except ImportError:  # pragma: no cover
    from lupa import LuaRuntime

ROOT = Path(__file__).resolve().parents[2]
ADDON_DIR = ROOT / "addon" / "FullBuff"
TOC = ADDON_DIR / "FullBuff_Forever.toc"
MOCK = Path(__file__).with_name("wowmock.lua")
ADDON_NAME = "FullBuff"


def read_toc_header(toc=TOC):
    header = {}
    for line in toc.read_text(encoding="utf-8").splitlines():
        if line.startswith("##") and ":" in line:
            key, _, val = line[2:].partition(":")
            header[key.strip()] = val.strip()
    return header


def toc_files(toc=TOC):
    """Lua files listed in the TOC, in order, with forward slashes."""
    out = []
    for line in toc.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        path = line.replace("\\", "/")
        if path.lower().endswith(".lua"):
            out.append(path)
    return out


class Addon:
    def __init__(self, files=None, mocks=None):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.g = self.lua.globals()
        self.lua.execute(MOCK.read_text(encoding="utf-8"))
        for name, value in (mocks or {}).items():
            self.mock(name, value)
        self.ns = self.lua.eval("{}")
        self.g.ns = self.ns  # visible to eval()/run() snippets
        loader = self.lua.eval(
            "function(src, name, ns) return assert(loadstring(src, '@' .. name))(%r, ns) end"
            % ADDON_NAME)
        for rel in (files if files is not None else toc_files()):
            src = (ADDON_DIR / rel).read_text(encoding="utf-8")
            loader(src, rel, self.ns)

    def mock(self, name, value):
        """Override a global. str = Lua expression, None = nil, else Python value/callable."""
        if isinstance(value, str):
            value = self.lua.eval(value)
        elif callable(value):  # make it a real Lua function (type() == "function")
            value = self.lua.eval("function(f) return function(...) return f(...) end end")(value)
        self.g[name] = value

    def eval(self, expr):
        return self.lua.eval(expr)

    def run(self, code):
        return self.lua.execute(code)

    def fire_event(self, name, *args):
        self.g["__fire_event"](name, *args)

    def flush_timers(self):
        self.g["__flush_timers"]()

    def load_addon(self, name=ADDON_NAME):
        self.fire_event("ADDON_LOADED", name)


@pytest.fixture
def addon():
    """Factory: addon(files=None, mocks=None) -> Addon (fresh Lua state per call)."""
    return Addon
