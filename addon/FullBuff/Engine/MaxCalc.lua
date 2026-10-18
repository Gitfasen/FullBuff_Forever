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

-- Sums flat effects and multiplies percent effects of a list of entries
-- (useActive: an entry's activeFx, the rank the player has, over its fx).
-- Different percent buffs are assumed to stack multiplicatively
-- (e.g. STAT_PCT 10 and STR_PCT 10 -> x1.21); verify in game.
local function aggregate(entries, useActive)
  local flat, mult = {}, { ARMOR = 1 }
  for _, p in ipairs(PRIMARIES) do mult[p] = 1 end
  for _, e in ipairs(entries) do
    local fx = (useActive and e.activeFx) or e.fx or {}
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

-- Compute(state, catalog) runs Scoring:MarkRecommended(catalog, state) (mutates
-- entry.recommended) and returns { rows = { {stat, current, max, diff} },
--   percentOfMax, stale }
-- With `picks` ({[slot]=buffId|false}) the chosen entries are those whose buff id is
-- picked (ACTIVE or CAN_ADD, not burst), grouped by the entry's current excl (the
-- slot key is ignored, so a rebuild that moved a buff still works). If two picked
-- entries share a group the higher Score wins (tie: lower id). When the pick is not
-- up but another buff of its group is ACTIVE, the slot counts as filled by that buff
-- (max for that slot = current).
function MaxCalc:Compute(state, catalog, picks)
  local reported = state and state.stats or {}
  catalog = catalog or {}
  ns.Scoring:MarkRecommended(catalog, state)
  local pickedId
  if picks then
    pickedId = {}
    for _, id in pairs(picks) do
      if id then pickedId[id] = true end
    end
  end
  local all, chosen, chosenGroup = {}, {}, {}
  local best = {}
  for key, list in pairs(catalog) do
    if key ~= "order" and type(list) == "table" then
      for _, e in ipairs(list) do
        all[#all + 1] = e
        if pickedId then
          if pickedId[e.id] and not e.burst and (e.status == "ACTIVE" or e.status == "CAN_ADD") then
            local g = groupKey(e)
            local cur = best[g]
            if not cur then
              best[g] = { e = e, score = ns.Scoring:Score(e.fx or {}, state) }
            else
              local sc = ns.Scoring:Score(e.fx or {}, state)
              if sc > cur.score or (sc == cur.score and (e.id or 0) < (cur.e.id or 0)) then
                best[g] = { e = e, score = sc }
              end
            end
          end
        elseif e.recommended and not e.burst and e.status ~= "UNAVAILABLE" then
          chosen[#chosen + 1] = e
          chosenGroup[groupKey(e)] = true
        end
      end
    end
  end
  -- A slot whose picked buff is not up while another buff of the slot is: the slot
  -- is filled by that buff as it is (its active rank), so max = current there.
  if pickedId then
    for _, e in ipairs(all) do
      local b = best[groupKey(e)]
      if b and b.e.status ~= "ACTIVE" and e.status == "ACTIVE" and not e.burst and e.excl
        and (not b.kept or (e.id or 0) < (b.kept.id or 0)) then
        b.e, b.kept = { id = e.id, excl = e.excl, fx = e.activeFx or e.fx }, e
      end
    end
  end
  for g, b in pairs(best) do
    chosen[#chosen + 1] = b.e
    chosenGroup[g] = true
  end
  -- An active lower rank (status ACTIVE with upgrade, activeFx set) counts with its
  -- activeFx; the chosen entry's fx is the best rank.
  -- Only active non-burst buffs whose group has a chosen entry are removed from
  -- the baseline. Active burst buffs and active buffs nobody would pick (score 0
  -- for this spec) stay in current AND max, so max is never below current.
  local active, anyActive = {}, {}
  for _, e in ipairs(all) do
    local isActive = e.status == "ACTIVE" or e.activeFx ~= nil
    if isActive then anyActive[#anyActive + 1] = e end
    if isActive and not e.burst and chosenGroup[groupKey(e)] then
      active[#active + 1] = e
    end
  end

  -- Non-primary stats the client does not report (MP5, HP5): current is the sum
  -- of the active known buffs' effects, so the usual subtraction stays consistent.
  local stats = {}
  for k, v in pairs(reported) do stats[k] = v end
  for k, v in pairs((aggregate(anyActive, true))) do
    if stats[k] == nil and not IS_PRIMARY[k] then stats[k] = v end
  end

  local activeFlat, activeMult = aggregate(active, true)
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

  return {
    rows = rows,
    percentOfMax = n > 0 and (sum / n * 100) or 100,
    stale = state and state.stale or false,
  }
end
