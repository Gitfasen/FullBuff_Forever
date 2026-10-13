local _, ns = ...

-- Stat weighting: expands buff effects into leaf stats, scores them, and
-- marks the best buff per stacking group.
local Scoring = {}
ns.Scoring = Scoring

local PRIMARIES = { "STR", "AGI", "STA", "INT", "SPI" }
local PCT_KEYS = {
  STR_PCT = "STR", AGI_PCT = "AGI", STA_PCT = "STA", INT_PCT = "INT", SPI_PCT = "SPI",
}
-- Canonical order for RelevantStats.
local CANONICAL = {
  "STR", "AGI", "STA", "INT", "SPI", "AP", "RAP", "SPELL_DMG", "HEAL", "ARMOR", "HP",
  "MANA", "MP5", "HP5", "CRIT", "SPELL_CRIT", "HIT", "SPELL_HIT",
}
Scoring.PRIMARIES = PRIMARIES
Scoring.CANONICAL = CANONICAL
local IS_PRIMARY = {}
for _, k in ipairs(PRIMARIES) do IS_PRIMARY[k] = true end

-- primary -> list of { derivedStat, ratioKey | fixedMultiplier }
local DERIVE = {
  STR = { { "AP", "apPerStr" } },
  AGI = { { "AP", "apPerAgi" }, { "RAP", "rapPerAgi" }, { "CRIT", "critPerAgi" }, { "ARMOR", 2 } },
  INT = { { "MANA", "manaPerInt" }, { "SPELL_CRIT", "spellCritPerInt" } },
  STA = { { "HP", "hpPerSta" } },
}

local function ratioFor(spec, ratios)
  if type(spec) == "number" then return spec end
  return ratios and ratios[spec]
end

local function add(t, k, v) t[k] = (t[k] or 0) + v end

-- Expand(fx, state): returns a new table of flat stats. Percent keys
-- (STAT_PCT, X_PCT, ARMOR_PCT) are converted to flat amounts from state.stats
-- and are NOT kept in the output (counted exactly once, as flat amounts).
-- Derived stats are added on top of the original flat stats.
function Scoring:Expand(fx, state)
  local stats = state and state.stats or {}
  local ratios = state and state.ratios or {}
  local out = {}
  for k, v in pairs(fx or {}) do
    if k == "STAT_PCT" then
      for _, p in ipairs(PRIMARIES) do
        local flat = (stats[p] or 0) * v / 100
        if flat ~= 0 then add(out, p, flat) end
      end
    elseif PCT_KEYS[k] then
      local p = PCT_KEYS[k]
      local flat = (stats[p] or 0) * v / 100
      if flat ~= 0 then add(out, p, flat) end
    elseif k == "ARMOR_PCT" then
      local flat = (stats.ARMOR or 0) * v / 100
      if flat ~= 0 then add(out, "ARMOR", flat) end
    else
      add(out, k, v)
    end
  end
  for _, p in ipairs(PRIMARIES) do
    local amt = out[p]
    local rules = DERIVE[p]
    if amt and rules then
      for _, rule in ipairs(rules) do
        local r = ratioFor(rule[2], ratios)
        if r then add(out, rule[1], amt * r) end
      end
    end
  end
  return out
end

-- Weights(state): base spec weights overlaid with user overrides (new table).
function Scoring:Weights(state)
  local w = {}
  local class, spec = state and state.class, (state and state.spec) or 1
  local base = ns.Weights and ns.Weights[class]
  base = base and base[spec]
  if base then for k, v in pairs(base) do w[k] = v end end
  local ov = ns.DB and ns.DB.weightOverrides
  ov = ov and ov[class]
  ov = ov and ov[spec]
  if ov then for k, v in pairs(ov) do w[k] = v end end
  return w
end

local function scoreWith(fx, state, w)
  local total = 0
  for k, v in pairs(Scoring:Expand(fx, state)) do
    local wt = w[k]
    if wt then total = total + v * wt end
  end
  return total
end

function Scoring:Score(fx, state)
  return scoreWith(fx, state, self:Weights(state))
end

-- MarkRecommended: mutates entries (entry.recommended = true on the best
-- non-burst ACTIVE/CAN_ADD entry per excl group, score must be > 0; ties go to
-- the lower id). Entries without excl are each their own group. Returns catalog.
function Scoring:MarkRecommended(catalog, state)
  local w = self:Weights(state)
  local best = {}
  local list = {}
  for key, entries in pairs(catalog) do
    if key ~= "order" and type(entries) == "table" then
      for _, e in ipairs(entries) do
        e.recommended = nil
        list[#list + 1] = e
      end
    end
  end
  for _, e in ipairs(list) do
    if not e.burst and (e.status == "ACTIVE" or e.status == "CAN_ADD") then
      local s = scoreWith(e.fx, state, w)
      if s > 0 then
        local g = e.excl or ("#" .. tostring(e.id))
        local b = best[g]
        if not b or s > b.score or (s == b.score and e.id < b.entry.id) then
          best[g] = { entry = e, score = s }
        end
      end
    end
  end
  for _, b in pairs(best) do b.entry.recommended = true end
  return catalog
end

-- RelevantStats: ordered leaf stats with weight > 0, plus primaries that
-- directly carry weight or feed a weighted stat through a non-nil ratio.
function Scoring:RelevantStats(state)
  local w = self:Weights(state)
  local ratios = state and state.ratios or {}
  local want = {}
  for _, k in ipairs(CANONICAL) do
    if (w[k] or 0) > 0 then want[k] = true end
  end
  for p, rules in pairs(DERIVE) do
    for _, rule in ipairs(rules) do
      local r = ratioFor(rule[2], ratios)
      if r and r > 0 and (w[rule[1]] or 0) > 0 then want[p] = true end
    end
  end
  local out = {}
  for _, k in ipairs(CANONICAL) do
    if want[k] then out[#out + 1] = k end
  end
  return out
end
