local _, ns = ...

-- Counts items in the player's bags (info only). Cached; rescanned (debounced)
-- on PLAYER_ENTERING_WORLD and BAG_UPDATE_DELAYED, then fires FULLBUFF_BAGS.
local Bags = {}
ns.Bags = Bags

local counts = nil

function Bags:Rescan()
  local c = {}
  local api = C_Container
  if api and api.GetContainerNumSlots and api.GetContainerItemInfo then
    for bag = 0, 4 do
      local slots = api.GetContainerNumSlots(bag) or 0
      for slot = 1, slots do
        local info = api.GetContainerItemInfo(bag, slot)
        if info and info.itemID then
          c[info.itemID] = (c[info.itemID] or 0) + (info.stackCount or 1)
        end
      end
    end
  end
  counts = c
  ns.Events:Fire("FULLBUFF_BAGS")
end

function Bags:Count(itemId)
  if not counts then self:Rescan() end
  return counts[itemId] or 0
end

function Bags:CountBuff(buff)
  local n = 0
  for _, id in ipairs(buff and buff.items or {}) do n = n + self:Count(id) end
  return n
end

local function schedule()
  ns.Events:Debounce("bags", 0.2, function() Bags:Rescan() end)
end

ns.Events:On("PLAYER_ENTERING_WORLD", schedule)
ns.Events:On("BAG_UPDATE_DELAYED", schedule)
