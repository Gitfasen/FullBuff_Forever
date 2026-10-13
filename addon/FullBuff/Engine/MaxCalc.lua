local _, ns = ...

-- Maximum stats: current stats with the recommended (best non-burst) buff of
-- every stacking group applied, and the contribution of every ACTIVE known buff
-- removed first so nothing is counted twice. Unknown auras are not subtracted.
local MaxCalc = {}
ns.MaxCalc = MaxCalc

local PRIMARIES = ns.Scoring.PRIMARIES
local PRIMARY_PCT = { STR = "STR_PCT", AGI = "AGI_PCT", STA = "STA_PCT", INT = "INT_PCT", SPI = "SPI_PCT" }
local PCT_KEY = { STAT_PCT = true, ARMOR_PCT = true }
for _, k in pairs(PRIMARY_PCT) do PCT_KEY[k] = true end
local IS_PRIMARY = {}
for _, p in ipairs(PRIMARIES) do IS_PRIMARY[p] = true end

-- Order used when every stat is shown.
local CANONICAL = ns.Scoring.CANONICAL
local ONE_DECIMAL = { CRIT = true, HIT = true, SPELL_CRIT = true, SPELL_HIT = true }

local function round(v, stat)
  if ONE_DECIMAL[stat] then return math.floor(v * 10 + 0.5) / 10 end
  return math.floor(v + 0.5)
end

-- Sums flat effects and multiplies percent effects of a list of entries.
-- Different percent buffs are assumed to stack multiplicatively
-- (e.g. STAT_PCT 10 and STR_PCT 10 -> x1.21); verify in game.
local function aggregate(entries)
  local flat, mult = {}, { ARMOR = 1 }
  for _, p in ipairs(PRIMARIES) do mult[p] = 1 end
  for _, e in ipairs(entries) do
    local fx = e.fx or {}
    for k, v in pairs(fx) do
      if not PCT_KEY[k] then flat[k] = (flat[k] or 0) + v end
    end
    for _, p in ipairs(PRIMARIES) do
      mult[p] = mult[p] * (1 + (fx.STAT_PCT or 0) / 100) * (1 + (fx[PRIMARY_PCT[p]] or 0) / 100)
    end
    mult.ARMOR = mult.ARMOR * (1 + (fx.ARMOR_PCT or 0) / 100)
  end
  return flat, mult
end

local function groupKey(e) return e.excl or ("#" .. tostring(e.id)) end

-- Guards against a non-positive multiplier (e.g. a -100% effect) in divisions.
local function safeDiv(v, m)
  if m > 0 then return v / m end
  return v
end

local function categoryIndex()
  local idx = {}
  local cats = ns.Catalog and ns.Catalog.CATEGORIES or {}
  for i, c in ipairs(cats) do idx[c] = i end
  return idx
end

-- Compute(state, catalog) runs Scoring:MarkRecommended(catalog, state) (mutates
-- entry.recommended) and returns { rows = { {stat, current, max, diff} },
--   missing = Entry[], missingCount, percentOfMax, stale }
function MaxCalc:Compute(state, catalog)
  local stats = state and state.stats or {}
  catalog = catalog or {}
  ns.Scoring:MarkRecommended(catalog, state)
  local all, chosen, chosenGroup = {}, {}, {}
  for key, list in pairs(catalog) do
    if key ~= "order" and type(list) == "table" then
      for _, e in ipairs(list) do
        all[#all + 1] = e
        if e.recommended and not e.burst and e.status ~= "UNAVAILABLE" then
          chosen[#chosen + 1] = e
          chosenGroup[groupKey(e)] = true
        end
      end
    end
  end
  -- Only ACTIVE non-burst buffs whose group has a chosen entry are removed from
  -- the baseline. Active burst buffs and active buffs nobody would pick (score 0
  -- for this spec) stay in current AND max, so max is never below current.
  local active = {}
  for _, e in ipairs(all) do
    if e.status == "ACTIVE" and not e.burst and chosenGroup[groupKey(e)] then
      active[#active + 1] = e
    end
  end

  local activeFlat, activeMult = aggregate(active)
  local maxFlat, maxMult = aggregate(chosen)

  local maxv = {}
  local deltaFx = {}
  for _, p in ipairs(PRIMARIES) do
    local cur = stats[p] or 0
    local base = safeDiv(cur, activeMult[p]) - (activeFlat[p] or 0)
    maxv[p] = (base + (maxFlat[p] or 0)) * maxMult[p]
    local d = maxv[p] - cur
    if d ~= 0 then deltaFx[p] = d end
  end

  -- Derived stats from the primary deltas only (flat primaries, no percent keys).
  local derived = {}
  if next(deltaFx) then
    for k, v in pairs(ns.Scoring:Expand(deltaFx, state)) do
      if not IS_PRIMARY[k] then derived[k] = v end
    end
  end

  local keys = {}
  for _, t in ipairs({ stats, activeFlat, maxFlat, derived }) do
    for k in pairs(t) do
      if not IS_PRIMARY[k] then keys[k] = true end
    end
  end
  for k in pairs(keys) do
    if k == "ARMOR" then
      local armorBase = safeDiv(stats.ARMOR or 0, activeMult.ARMOR) - (activeFlat.ARMOR or 0)
      maxv.ARMOR = (armorBase + (maxFlat.ARMOR or 0) + (derived.ARMOR or 0)) * maxMult.ARMOR
    else
      maxv[k] = (stats[k] or 0) - (activeFlat[k] or 0) + (maxFlat[k] or 0) + (derived[k] or 0)
    end
  end

  local list
  local db = ns.DB
  if db and db.showAllStats then
    list = {}
    for _, k in ipairs(CANONICAL) do
      if stats[k] ~= nil or (maxv[k] or 0) ~= 0 then list[#list + 1] = k end
    end
  else
    list = ns.Scoring:RelevantStats(state)
  end

  local rows, sum, n = {}, 0, 0
  for _, k in ipairs(list) do
    local cur, mx = stats[k] or 0, maxv[k] or 0
    if mx > 0 then
      sum = sum + math.min(cur / mx, 1)
      n = n + 1
    end
    local rc, rm = round(cur, k), round(mx, k)
    rows[#rows + 1] = { stat = k, current = rc, max = rm, diff = round(rm - rc, k) }
  end

  local missing = {}
  for _, e in ipairs(chosen) do
    if e.status == "CAN_ADD" then missing[#missing + 1] = e end
  end
  local cidx = categoryIndex()
  table.sort(missing, function(a, b)
    local ca, cb = cidx[a.cat] or 999, cidx[b.cat] or 999
    if ca ~= cb then return ca < cb end
    local na, nb = a.name or "", b.name or ""
    if na ~= nb then return na < nb end
    return (a.id or 0) < (b.id or 0)
  end)

  return {
    rows = rows,
    missing = missing,
    missingCount = #missing,
    percentOfMax = n > 0 and (sum / n * 100) or 100,
    stale = state and state.stale or false,
  }
end
