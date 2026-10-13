local _, ns = ...

-- Snapshot of the player: class, level, spec, current stats and active buffs.
-- Consumed by Catalog, Scoring and MaxCalc.
local PlayerState = {}
ns.PlayerState = PlayerState

local HP_PER_STA, MANA_PER_INT = 10, 15
local MIN_SPEC_POINTS = 10

local state = nil
local auraLookup, enchantLookup = nil, nil

local function isSecret(v)
  return ns.Compat.IsSecret(v)
end

-- Lazy auraSpellId -> { buffId, ... } and enchantId -> { buffId, ... }.
local function buildLookups()
  auraLookup, enchantLookup = {}, {}
  local function add(map, key, id)
    if not key then return end
    local list = map[key]
    if not list then
      list = {}
      map[key] = list
    end
    for i = 1, #list do
      if list[i] == id then return end
    end
    list[#list + 1] = id
  end
  for id, buff in pairs(ns.Buffs or {}) do
    add(auraLookup, buff.aura or id, id)
    if buff.ranks then
      for _, rank in ipairs(buff.ranks) do add(auraLookup, rank.spell, id) end
    end
    add(enchantLookup, buff.enchant, id)
  end
end

local function hasFxValue(buff, value)
  for _, v in pairs(buff.fx or {}) do
    if v == value then return true end
  end
  return false
end

local function firstNonZero(points)
  if type(points) ~= "table" then return nil end
  for i = 1, #points do
    local p = points[i]
    if type(p) == "number" and p ~= 0 then return p end
  end
  return nil
end

-- Several buffs (food tiers) may share one aura: pick by the aura's value,
-- falling back to the highest tier the player's level allows.
local function pickBuff(candidates, auraData, level)
  if #candidates == 1 then return candidates[1] end
  local best, bestLvl
  local value = firstNonZero(auraData.points)
  if value then
    for _, id in ipairs(candidates) do
      local buff = ns.Buffs[id]
      local lvl = buff.lvl or 0
      if hasFxValue(buff, value) and (not best or lvl > bestLvl) then best, bestLvl = id, lvl end
    end
    if best then return best end
  end
  for _, id in ipairs(candidates) do
    local lvl = ns.Buffs[id].lvl or 0
    if lvl <= level and (not best or lvl > bestLvl) then best, bestLvl = id, lvl end
  end
  if best then return best end
  -- every tier is above the player's level: take the lowest
  for _, id in ipairs(candidates) do
    local lvl = ns.Buffs[id].lvl or 0
    if not best or lvl < bestLvl then best, bestLvl = id, lvl end
  end
  return best
end

local function readSpec()
  local override = ns.CharDB and ns.CharDB.specOverride
  local bestTree, bestPoints, total = 1, -1, 0
  if type(GetSpecializationInfo) == "function" then
    for i = 1, 3 do
      local points = select(7, GetSpecializationInfo(i))
      if type(points) == "number" then
        total = total + points
        if points > bestPoints then bestTree, bestPoints = i, points end
      end
    end
  end
  if override then return override, true end
  if total < MIN_SPEC_POINTS then return 1, false end
  return bestTree, true
end

local function call(name, ...)
  local fn = _G[name]
  if type(fn) ~= "function" then return nil end
  return fn(...)
end

-- Returns a stats table, or nil when a value is secret.
local function readStats()
  local stats, secret = {}, false
  local function put(key, v)
    if v == nil then return end
    if isSecret(v) then secret = true return end
    stats[key] = v
  end
  local function power(name, key)
    if type(_G[name]) ~= "function" then return end
    local base, pos, neg = _G[name]("player")
    if isSecret(base) or isSecret(pos) or isSecret(neg) then secret = true
    elseif base then stats[key] = base + (pos or 0) + (neg or 0) end
  end
  local function maxOver(name, key)
    local fn = _G[name]
    if type(fn) ~= "function" then return end
    local best
    for school = 2, 7 do
      local v = fn(school)
      if isSecret(v) then secret = true return end
      if type(v) == "number" and (not best or v > best) then best = v end
    end
    put(key, best)
  end

  local keys = { "STR", "AGI", "STA", "INT", "SPI" }
  if type(UnitStat) == "function" then
    for i = 1, 5 do put(keys[i], (select(2, UnitStat("player", i)))) end
  end
  power("UnitAttackPower", "AP")
  power("UnitRangedAttackPower", "RAP")
  maxOver("GetSpellBonusDamage", "SPELL_DMG")
  put("HEAL", call("GetSpellBonusHealing"))
  put("ARMOR", (select(2, call("UnitArmor", "player"))))
  put("HP", call("UnitHealthMax", "player"))
  put("MANA", call("UnitPowerMax", "player", 0))
  put("CRIT", call("GetCritChance"))
  maxOver("GetSpellCritChance", "SPELL_CRIT")
  put("HIT", call("GetHitModifier"))
  put("SPELL_HIT", call("GetSpellHitModifier"))
  if secret then return nil end
  return stats
end

local RAP_PER_AGI = { HUNTER = 2, WARRIOR = 1, ROGUE = 1 }

-- Returns a ratios table, or nil when a value is secret.
local function readRatios(stats, class)
  local r = { hpPerSta = HP_PER_STA, manaPerInt = MANA_PER_INT, rapPerAgi = RAP_PER_AGI[class] or 0 }
  if type(GetAttackPowerForStat) == "function" then
    r.apPerStr = GetAttackPowerForStat(1, 1)
    r.apPerAgi = GetAttackPowerForStat(2, 1)
    if isSecret(r.apPerStr) or isSecret(r.apPerAgi) then return nil end
  end
  if type(GetCritChanceFromAgility) == "function" and stats.AGI and stats.AGI > 0 then
    local v = GetCritChanceFromAgility("player")
    if isSecret(v) then return nil end
    if v then r.critPerAgi = v / stats.AGI end
  end
  if type(GetSpellCritChanceFromIntellect) == "function" and stats.INT and stats.INT > 0 then
    local v = GetSpellCritChanceFromIntellect("player")
    if isSecret(v) then return nil end
    if v then r.spellCritPerInt = v / stats.INT end
  end
  return r
end

-- Returns active, activeAura, unknown, or nil when a value is secret.
local function readAuras(level)
  if not auraLookup then buildLookups() end
  local active, activeAura, unknown = {}, {}, {}
  local getter = C_UnitAuras and C_UnitAuras.GetAuraDataByIndex
  if getter then
    local i = 1
    while true do
      local aura = getter("player", i, "HELPFUL")
      if not aura then break end
      local spellId, name = aura.spellId, aura.name
      if isSecret(spellId) or isSecret(name) then return nil end
      if type(aura.points) == "table" then
        for k = 1, #aura.points do
          if isSecret(aura.points[k]) then return nil end
        end
      end
      local candidates = auraLookup[spellId]
      if candidates then
        local id = pickBuff(candidates, aura, level)
        if id then
          active[id] = true
          activeAura[id] = spellId
        end
      elseif spellId then
        unknown[spellId] = name
      end
      i = i + 1
    end
  end
  if type(GetWeaponEnchantInfo) == "function" then
    local r = { GetWeaponEnchantInfo() }
    for _, idx in ipairs({ 4, 8 }) do
      local enchantId = r[idx]
      if isSecret(enchantId) then return nil end
      for _, id in ipairs(enchantLookup[enchantId] or {}) do active[id] = true end
    end
  end
  return active, activeAura, unknown
end

function PlayerState:Refresh()
  local prev = state
  local s = {
    class = select(2, UnitClass("player")) or "WARRIOR",
    level = UnitLevel("player") or 1,
    stats = prev and prev.stats or {},
    active = prev and prev.active or {},
    activeAura = prev and prev.activeAura or {},
    unknownAuras = prev and prev.unknownAuras or {},
    ratios = prev and prev.ratios or { hpPerSta = HP_PER_STA, manaPerInt = MANA_PER_INT },
    stale = true,
  }
  s.spec, s.specAuto = readSpec()

  if ns.Compat.CanReadAuras() then
    local stats = readStats()
    local active, activeAura, unknown = readAuras(s.level)
    local ratios = stats and readRatios(stats, s.class)
    if stats and active and ratios then
      s.stats, s.active, s.activeAura, s.unknownAuras = stats, active, activeAura, unknown
      s.ratios = ratios
      s.stale = false
    end
  end

  state = s
  ns.Events:Fire("FULLBUFF_STATE")
  return s
end

function PlayerState:Get()
  return state or self:Refresh()
end

local function request()
  ns.Events:Debounce("state", 0.3, function() PlayerState:Refresh() end)
end

ns.Events:On("PLAYER_ENTERING_WORLD", request)
ns.Events:On("UNIT_AURA", function(unit) if unit == "player" then request() end end)
ns.Events:On("PLAYER_REGEN_ENABLED", request)
ns.Events:On("PLAYER_LEVEL_UP", request)
ns.Events:On("CHARACTER_POINTS_CHANGED", request)
ns.Events:On("PLAYER_EQUIPMENT_CHANGED", request)
