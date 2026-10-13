local _, ns = ...

-- Pure view model: turns engine output into plain tables for the frames.
-- No frame code here, so it is fully testable.
--
-- Build(state?, catalog?) -> {
--   header  = { class, specName, level, stale, rows = { {stat,label,current,max,diff}... } },
--   sections= { { cat, title, activeCount, total, collapsed,
--                 items = { {id, icon, name, valueText, status, recommended} } } },
--   badge   = number of recommended buffs that can still be added (non-burst),
--   tooltip = { progress = percentOfMax (0..100), missing = { names... } },
-- }
-- Section items are ordered CAN_ADD (recommended first), UNAVAILABLE, ACTIVE.
-- activeCount/total ignore the "only missing" filter; total excludes UNAVAILABLE.
-- Sections of categories with ns.DB.hiddenCats[cat] == true are omitted from `sections`
-- only; MaxCalc, the badge and the tooltip still count them (hiding is display-only).
-- With ns.DB.onlyMissing only CAN_ADD items are listed and empty sections are dropped.
--
-- valueText format (FormatFx): "+25 Agility, +2% Critical strike". Entries follow the
-- canonical stat order, then percent keys; "%" for CRIT/HIT/SPELL_*, and *_PCT keys
-- ("+10% All stats"). At most MAX_FX entries are shown, then an ellipsis.
local VM = {}
ns.ViewModel = VM

local MAX_FX = 4
local QUESTION = "Interface\\Icons\\INV_Misc_QuestionMark"
local STATUS_RANK = { CAN_ADD = 1, UNAVAILABLE = 2, ACTIVE = 3 }
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

local function sortItems(items)
  for i, it in ipairs(items) do it.__i = i end
  table.sort(items, function(a, b)
    local ra, rb = STATUS_RANK[a.status] or 9, STATUS_RANK[b.status] or 9
    if ra ~= rb then return ra < rb end
    if a.recommended ~= b.recommended then return a.recommended end
    return a.__i < b.__i
  end)
  for _, it in ipairs(items) do it.__i = nil end
end

function VM:Build(state, catalog)
  local L = ns.L
  local DB = ns.DB or {}
  state = state or ns.PlayerState:Get()
  catalog = catalog or ns.Catalog:Build(state)
  local calc = ns.MaxCalc:Compute(state, catalog) -- also marks entry.recommended

  local header = {
    class = className(state.class),
    specName = string.format(L.SPEC_FMT, state.spec or 1),
    level = state.level,
    stale = state.stale and true or false,
    rows = {},
  }
  for i, r in ipairs(calc.rows) do
    header.rows[i] = { stat = r.stat, label = label(r.stat), current = r.current, max = r.max, diff = r.diff }
  end

  local sections = {}
  for _, cat in ipairs(catalog.order or {}) do
   if not (DB.hiddenCats and DB.hiddenCats[cat]) then
    local entries = catalog[cat] or {}
    local sec = { cat = cat, title = L["CATEGORY_" .. cat], activeCount = 0, total = 0,
                  collapsed = (DB.collapsed and DB.collapsed[cat]) and true or false, items = {} }
    for _, e in ipairs(entries) do
      if e.status == "ACTIVE" then sec.activeCount = sec.activeCount + 1 end
      if e.status ~= "UNAVAILABLE" then sec.total = sec.total + 1 end
      if not DB.onlyMissing or e.status == "CAN_ADD" then
        sec.items[#sec.items + 1] = {
          id = e.id, icon = iconFor(e.rankSpell or e.id), name = e.name,
          valueText = VM.FormatFx(e.fx), status = e.status, recommended = e.recommended and true or false,
        }
      end
    end
    sortItems(sec.items)
    if #sec.items > 0 then sections[#sections + 1] = sec end
   end
  end

  local names = {}
  for i, e in ipairs(calc.missing) do names[i] = e.name end

  return {
    header = header,
    sections = sections,
    badge = calc.missingCount,
    tooltip = { progress = calc.percentOfMax, missing = names },
  }
end
