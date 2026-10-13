local _, ns = ...

-- Counts items in the player's bags (info only). Cached; rescanned (debounced)
-- on PLAYER_ENTERING_WORLD and BAG_UPDATE_DELAYED, then fires FULLBUFF_BAGS when
-- the counts changed. The lazy first scan inside Count never fires.
-- Bags.noContainerApi: set when C_Container is missing (shown by /fullbuff debug).
local Bags = {}
ns.Bags = Bags

local counts = nil

local function same(a, b)
  if not a then return false end
  for k, v in pairs(a) do
    if b[k] ~= v then return false end
  end
  for k in pairs(b) do
    if a[k] == nil then return false end
  end
  return true
end

-- Rescan(silent): silent never fires FULLBUFF_BAGS.
function Bags:Rescan(silent)
  local c = {}
  local api = C_Container
  self.noContainerApi = not (api and api.GetContainerNumSlots and api.GetContainerItemInfo) or nil
  if not self.noContainerApi then
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
  local changed = not same(counts, c)
  counts = c
  if changed and not silent then ns.Events:Fire("FULLBUFF_BAGS") end
end

function Bags:Count(itemId)
  if not counts then self:Rescan(true) end
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
