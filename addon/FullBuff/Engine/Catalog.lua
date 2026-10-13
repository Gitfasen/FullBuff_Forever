local _, ns = ...

-- Turns ns.Buffs + a PlayerState snapshot into per-category entry lists.
local Catalog = {}
ns.Catalog = Catalog

Catalog.CATEGORIES = { "CLASS", "WORLD", "CAMPING", "FLASK", "ELIXIR", "FOOD", "SCROLL", "WEAPON", "QUEST", "TRINKET", "POTION" }

local RANK_LEVEL_SLACK = 10

local KNOWN = {}
for _, c in ipairs(Catalog.CATEGORIES) do KNOWN[c] = true end

local function rankLvl(r) return r.lvl or 0 end

-- Returns rankSpell, fx, allowed for a buff at the given level.
local function pickRank(id, buff, level)
  local ranks = buff.ranks
  if not ranks or #ranks == 0 then
    return id, buff.fx, (buff.lvl or 0) <= level
  end
  local sorted = {}
  for i = 1, #ranks do sorted[i] = ranks[i] end
  table.sort(sorted, function(a, b) return rankLvl(a) < rankLvl(b) end)
  local best
  for i = 1, #sorted do
    if rankLvl(sorted[i]) - RANK_LEVEL_SLACK <= level then best = sorted[i] end
  end
  if best then return best.spell or id, best.fx or buff.fx, true end
  local lowest = sorted[1]
  return lowest.spell or id, lowest.fx or buff.fx, false
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
      local rankSpell, fx, allowed = pickRank(id, buff, level)
      local status
      if state.active and state.active[id] then
        status = "ACTIVE"
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
        status = status, rankSpell = rankSpell,
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
