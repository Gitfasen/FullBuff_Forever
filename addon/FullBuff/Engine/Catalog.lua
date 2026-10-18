local _, ns = ...

-- Turns ns.Buffs + a PlayerState snapshot into per-category entry lists.
local Catalog = {}
ns.Catalog = Catalog

Catalog.CATEGORIES = { "CLASS", "WORLD", "CAMPING", "FLASK", "ELIXIR", "FOOD", "SCROLL", "WEAPON", "QUEST", "TRINKET", "POTION" }

-- Ranks of another class's buff may come from a higher caster (up to 10 levels
-- above the player). The player's own class buffs and camp buffs (one rank per
-- level band, all under one spell id) use the player's level only.
local RANK_LEVEL_SLACK = 10

local KNOWN = {}
for _, c in ipairs(Catalog.CATEGORIES) do KNOWN[c] = true end

local function rankLvl(r) return r.lvl or 0 end

local function rankSlack(buff, state)
  if buff.cat == "CAMPING" or buff.cls == state.class then return 0 end
  return RANK_LEVEL_SLACK
end

local function sortedRanks(ranks)
  local sorted = {}
  for i = 1, #ranks do sorted[i] = ranks[i] end
  table.sort(sorted, function(a, b) return rankLvl(a) < rankLvl(b) end)
  return sorted
end

-- Returns rank, rankSpell, fx, allowed for a buff at the given level (rank: nil
-- for a buff without ranks).
local function pickRank(id, buff, level, slack)
  local ranks = buff.ranks
  if not ranks or #ranks == 0 then
    return nil, id, buff.fx, (buff.lvl or 0) <= level
  end
  local sorted = sortedRanks(ranks)
  local best
  for i = 1, #sorted do
    if rankLvl(sorted[i]) - slack <= level then best = sorted[i] end
  end
  if best then return best, best.spell or id, best.fx or buff.fx, true end
  local lowest = sorted[1]
  return lowest, lowest.spell or id, lowest.fx or buff.fx, false
end

-- The rank the player actually has (state.activeAura names its spell). Several
-- ranks may share one spell (camp bands): the highest one the player's level allows,
-- else the lowest. Returns fx, rank (rank nil when no rank matches).
local function activeRank(buff, auraSpell, level)
  local match, lowest
  for _, r in ipairs(sortedRanks(buff.ranks or {})) do
    if r.spell == auraSpell then
      lowest = lowest or r
      if rankLvl(r) <= level then match = r end
    end
  end
  match = match or lowest
  if match then return match.fx or buff.fx, match end
  return buff.fx, nil
end

local function byNameThenId(a, b)
  if a.name ~= b.name then return a.name < b.name end
  return a.id < b.id
end

function Catalog:Build(state)
  local out = { order = {} }
  local level = state.level or 0
  for id, buff in pairs(ns.Buffs or {}) do
    local cat = buff.cat
    if cat and KNOWN[cat] and not (cat == "CLASS" and buff.selfOnly and buff.cls ~= state.class) then
      local best, rankSpell, fx, allowed = pickRank(id, buff, level, rankSlack(buff, state))
      local status, activeFx, upgrade
      if state.active and state.active[id] then
        -- any rank up counts as active; a higher allowed rank is an upgrade
        status = "ACTIVE"
        local auraSpell = state.activeAura and state.activeAura[id]
        local rank
        activeFx, rank = activeRank(buff, auraSpell, level)
        if rank and best and allowed and rankLvl(best) > rankLvl(rank) then upgrade = true end
      elseif allowed then
        status = "CAN_ADD"
      else
        status = "UNAVAILABLE"
      end
      local list = out[cat]
      if not list then
        list = {}
        out[cat] = list
      end
      list[#list + 1] = {
        id = id, name = buff.name or tostring(id), cat = cat, fx = fx,
        lvl = buff.lvl, excl = buff.excl, burst = buff.burst,
        status = status, rankSpell = rankSpell, activeFx = activeFx, upgrade = upgrade,
      }
    end
  end
  for _, cat in ipairs(Catalog.CATEGORIES) do
    if out[cat] then
      table.sort(out[cat], byNameThenId)
      out.order[#out.order + 1] = cat
    end
  end
  return out
end
