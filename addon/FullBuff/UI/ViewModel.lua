local _, ns = ...

-- Pure view model: turns engine output into plain tables for the frames.
-- No frame code here, so it is fully testable.
--
-- Build(state?, catalog?) -> {
--   header  = { class, specName, specHint, level, stale, setName,
--               rows = { {stat,label,current,max,diff}... } },
--             (rows: current -> maximum reachable with the ACTIVE SET's picks, MaxCalc:Compute;
--              specName: the talent tree's name, else "Specialization N"; specHint: set
--              while the spec is not detected automatically)
--   sets    = { {id, name, active}... }   in ns.Sets:List() order,
--   list    = SetTracker rows of the active set {slot,slotName,buffId,name,icon,valueText,status,bagCount}
--             (status ACTIVE, MISSING, UNAVAILABLE, already in that order),
--   burst   = SetTracker burst rows {buffId,name,icon,bagCount,unavailable},
--   empty   = true when the active set has neither picks nor burst buffs (or there is no set),
--   badge   = SetTracker missingCount (MISSING rows + tracked burst with no bags),
--   tooltip = { setName, progress = percentOfMax (0..100), missing = { names... } },
-- }
-- tooltip.missing: names of MISSING rows, then of available burst buffs with bagCount 0.
--
-- valueText format (FormatFx): "+25 Agility, +2% Critical strike". Entries follow the
-- canonical stat order, then percent keys; "%" for CRIT/HIT/SPELL_*, and *_PCT keys
-- ("+10% All stats"). At most MAX_FX entries are shown, then an ellipsis.
local VM = {}
ns.ViewModel = VM

local MAX_FX = 4
local QUESTION = "Interface\\Icons\\INV_Misc_QuestionMark"
local PERCENT_STAT = { CRIT = true, SPELL_CRIT = true, HIT = true, SPELL_HIT = true }
local PCT_ORDER = { "STAT_PCT", "STR_PCT", "AGI_PCT", "STA_PCT", "INT_PCT", "SPI_PCT", "ARMOR_PCT" }

local function label(key)
  return ns.L["STAT_" .. key]
end

local function num(v)
  v = math.floor(v * 10 + 0.5) / 10
  if v == math.floor(v) then return string.format("%d", v) end
  return string.format("%.1f", v)
end

-- FxEntries(fx) -> every effect as a list of strings ("+25 Agility"), same order and
-- wording as FormatFx but without the MAX_FX cut-off.
function VM.FxEntries(fx)
  local parts = {}
  local order = ns.Scoring and ns.Scoring.CANONICAL or {}
  for _, k in ipairs(order) do
    local v = fx and fx[k]
    if v and v ~= 0 then
      if PERCENT_STAT[k] then
        parts[#parts + 1] = string.format("+%s%% %s", num(v), label(k))
      else
        parts[#parts + 1] = string.format("+%s %s", num(v), label(k))
      end
    end
  end
  for _, k in ipairs(PCT_ORDER) do
    local v = fx and fx[k]
    if v and v ~= 0 then
      local text = label(k):gsub("%s*%%$", "")
      parts[#parts + 1] = string.format("+%s%% %s", num(v), text)
    end
  end
  return parts
end

function VM.FormatFx(fx)
  local all = VM.FxEntries(fx)
  local parts = {}
  for i = 1, math.min(#all, MAX_FX) do parts[i] = all[i] end
  local s = table.concat(parts, ", ")
  if #all > MAX_FX then s = s .. ", \226\128\166" end -- UTF-8 ellipsis
  return s
end

local function iconFor(spellId)
  local tex
  if C_Spell and C_Spell.GetSpellTexture then
    tex = C_Spell.GetSpellTexture(spellId)
  end
  if not tex and GetSpellTexture then
    tex = GetSpellTexture(spellId)
  end
  return tex or QUESTION
end
VM.IconFor = iconFor

local function className(class)
  if UnitClass then
    local name, token = UnitClass("player")
    if token == class and name then return name end
  end
  return class
end

function VM:Build(state, catalog)
  local L = ns.L
  state = state or ns.PlayerState:Get()
  catalog = catalog or ns.Catalog:Build(state)
  local activeId, set = ns.Sets:Active()
  local calc = ns.MaxCalc:Compute(state, catalog, ns.Sets:Resolve(set)) -- also marks entry.recommended
  local tracked = ns.SetTracker:Evaluate(state, catalog, set or { picks = {}, burst = {} })

  local header = {
    class = className(state.class),
    specName = state.specName or string.format(L.SPEC_FMT, state.spec or 1),
    specHint = (state.specAuto == false) and L.SPEC_HINT or nil,
    level = state.level,
    stale = state.stale and true or false,
    setName = set and set.name or "",
    rows = {},
  }
  for i, r in ipairs(calc.rows) do
    header.rows[i] = { stat = r.stat, label = label(r.stat), current = r.current, max = r.max, diff = r.diff }
  end

  local sets = {}
  for _, id in ipairs(ns.Sets:List()) do
    local s = ns.Sets:Get(id)
    sets[#sets + 1] = { id = id, name = s and s.name or tostring(id), active = (id == activeId) }
  end

  local names = {}
  for _, r in ipairs(tracked.rows) do
    if r.status == "MISSING" then names[#names + 1] = r.name end
  end
  for _, b in ipairs(tracked.burst) do
    if b.bagCount == 0 and not b.unavailable then names[#names + 1] = b.name end
  end

  return {
    header = header,
    sets = sets,
    list = tracked.rows,
    burst = tracked.burst,
    empty = (#tracked.rows == 0 and #tracked.burst == 0),
    badge = tracked.missingCount,
    tooltip = { setName = header.setName, progress = calc.percentOfMax, missing = names },
  }
end

-- Get() -> the view model of the current PlayerState snapshot, built once and
-- shared by the launcher, its tooltip, the popover and the detail card (vm.catalog
-- is the catalog it was built from). Rebuilt for a new snapshot (FULLBUFF_STATE),
-- a language change, a set change (FULLBUFF_SET), a bag rescan (FULLBUFF_BAGS), or after
-- Invalidate() (display options).
local cache

function VM:Invalidate()
  cache = nil
end

function VM:Get()
  local state = ns.PlayerState:Get()
  local lang = ns.GetLanguage and ns.GetLanguage()
  if cache and cache.state == state and cache.lang == lang then return cache.vm end
  local catalog = ns.Catalog:Build(state)
  local vm = self:Build(state, catalog)
  vm.catalog = catalog
  cache = { vm = vm, state = state, lang = lang }
  return vm
end

ns.Events:On("FULLBUFF_STATE", function() VM:Invalidate() end)
ns.Events:On("FULLBUFF_LANGUAGE", function() VM:Invalidate() end)
ns.Events:On("FULLBUFF_SET", function() VM:Invalidate() end)
ns.Events:On("FULLBUFF_BAGS", function() VM:Invalidate() end)
