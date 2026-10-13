"""Lua test harness for the FullBuff addon.

Usage in a test:

    def test_x(addon):
        a = addon(mocks={"InCombatLockdown": lambda: True})
        assert a.eval("ns.Compat.CanReadAuras()") is False
        a.load_addon()          # fires ADDON_LOADED "FullBuff"
        a.fire_event("PLAYER_REGEN_ENABLED")
        a.advance(0.3)          # virtual clock; or a.flush_timers()
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


def _is_lua_object(value):
    return type(value).__module__.startswith("lupa")


class Addon:
    def __init__(self, files=None, mocks=None):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.g = self.lua.globals()
        self.lua.execute(MOCK.read_text(encoding="utf-8"))
        for name, value in (mocks or {}).items():
            self.mock(name, value)
        self.ns = self.lua.eval("{}")
        # Deliberately not a global named `ns`: a file that forgets
        # `local _, ns = ...` must fail in tests.
        self.g["__ns"] = self.ns
        loader = self.lua.eval(
            "function(src, name, ns) return assert(loadstring(src, '@' .. name))(%r, ns) end"
            % ADDON_NAME)
        for rel in (files if files is not None else toc_files()):
            if rel.startswith("Libs/"):
                continue  # third-party libs (LibStub, HereBeDragons) are mocked in wowmock.lua
            src = (ADDON_DIR / rel).read_text(encoding="utf-8")
            loader(src, rel, self.ns)

    def to_lua(self, value):
        """dict -> table, list/tuple -> 1-based array, callable -> Lua function whose
        return values are converted too, None -> nil. Strings stay strings."""
        if isinstance(value, dict):
            t = self.lua.table()
            for k, v in value.items():
                t[self.to_lua(k)] = self.to_lua(v)
            return t
        if isinstance(value, (list, tuple)):
            t = self.lua.table()
            for i, v in enumerate(value, 1):
                t[i] = self.to_lua(v)
            return t
        if callable(value) and not _is_lua_object(value):
            def wrapper(*args):
                r = value(*args)
                if isinstance(r, tuple):
                    return tuple(self.to_lua(x) for x in r)
                return self.to_lua(r)
            wrap = self.lua.eval("function(f) return function(...) return f(...) end end")
            return wrap(wrapper)
        return value

    def mock(self, name, value):
        """Override a global or a dotted field ("C_Timer.After" sets the field on the
        existing table, creating tables as needed). A str value is a Lua expression,
        None is nil, dict/list become Lua tables (recursively), callables Lua functions."""
        if isinstance(value, str):
            value = self.lua.eval(value)
        else:
            value = self.to_lua(value)
        *path, last = name.split(".")
        tbl = self.g
        for part in path:
            nxt = tbl[part]
            if nxt is None:
                nxt = self.lua.table()
                tbl[part] = nxt
            tbl = nxt
        tbl[last] = value

    def eval(self, expr):
        return self.lua.eval("(function() local ns = __ns; return %s end)()" % expr)

    def run(self, code):
        return self.lua.execute("local ns = __ns\n" + code)

    def fire_event(self, name, *args):
        self.g["__fire_event"](name, *args)

    def advance(self, seconds):
        """Advance the virtual clock, running due timers in (due, queue) order."""
        self.g["__advance"](seconds)

    def flush_timers(self):
        """Run every queued timer, advancing the clock as needed."""
        self.g["__flush_timers"]()

    def errors(self):
        """Messages passed to geterrorhandler() so far."""
        return list(self.eval("__errors").values())

    def load_addon(self, name=ADDON_NAME):
        self.fire_event("ADDON_LOADED", name)


@pytest.fixture
def addon():
    """Factory: addon(files=None, mocks=None) -> Addon (fresh Lua state per call)."""
    return Addon
