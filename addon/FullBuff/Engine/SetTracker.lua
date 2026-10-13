local _, ns = ...

-- Turns a buff set into display rows: active / missing / unavailable buffs with
-- bag counts, plus the tracked burst buffs. Info only.
local SetTracker = {}
ns.SetTracker = SetTracker

local RANK = { ACTIVE = 1, MISSING = 2, UNAVAILABLE = 3 }

-- Evaluate(state, catalog, set) ->
--   { rows = {{slot, buffId, name, icon, valueText, status, bagCount}},
--     burst = {{buffId, name, icon, bagCount}}, missingCount, unavailableCount }
function SetTracker:Evaluate(state, catalog, set)
  local VM = ns.ViewModel
  local byId = {}
  for key, list in pairs(catalog or {}) do
    if key ~= "order" and type(list) == "table" then
      for _, e in ipairs(list) do byId[e.id] = e end
    end
  end
  local buffs = ns.Buffs or {}
  local slots = ns.Slots or {}

  local rows, missing, unavailable = {}, 0, 0
  for slot, buffId in pairs(set and set.picks or {}) do
    if buffId then
      local buff, e = buffs[buffId], byId[buffId]
      local status
      if not buff or not e or e.status == "UNAVAILABLE" then
        status = "UNAVAILABLE"
        unavailable = unavailable + 1
      elseif e.status == "ACTIVE" then
        status = "ACTIVE"
      else
        status = "MISSING"
        missing = missing + 1
      end
      rows[#rows + 1] = {
        slot = slot, buffId = buffId,
        name = buff and buff.name or ("#" .. tostring(buffId)),
        icon = VM.IconFor(e and e.rankSpell),
        valueText = (e and status ~= "UNAVAILABLE") and VM.FormatFx(e.fx) or "",
        status = status,
        bagCount = buff and ns.Bags:CountBuff(buff) or 0,
      }
    end
  end
  table.sort(rows, function(a, b)
    if a.status ~= b.status then return RANK[a.status] < RANK[b.status] end
    local oa = slots[a.slot] and slots[a.slot].order or math.huge
    local ob = slots[b.slot] and slots[b.slot].order or math.huge
    if oa ~= ob then return oa < ob end
    if a.name ~= b.name then return a.name < b.name end
    return tostring(a.slot) < tostring(b.slot)
  end)

  local burst = {}
  for _, buffId in ipairs(set and set.burst or {}) do
    local buff, e = buffs[buffId], byId[buffId]
    local n = buff and ns.Bags:CountBuff(buff) or 0
    if n == 0 then missing = missing + 1 end
    burst[#burst + 1] = {
      buffId = buffId,
      name = buff and buff.name or ("#" .. tostring(buffId)),
      icon = VM.IconFor(e and e.rankSpell),
      bagCount = n,
    }
  end

  return { rows = rows, burst = burst, missingCount = missing, unavailableCount = unavailable }
end
