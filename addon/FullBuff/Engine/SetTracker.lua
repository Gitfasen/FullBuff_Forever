local _, ns = ...

-- Turns a buff set into display rows: active / missing / unavailable buffs with
-- bag counts, plus the tracked burst buffs. Info only.
local SetTracker = {}
ns.SetTracker = SetTracker

local RANK = { ACTIVE = 1, MISSING = 2, UNAVAILABLE = 3 }

local function slotName(slots, slot)
  local n = slots[slot] and slots[slot].name
  if not n then return tostring(slot) end
  local lang = ns.GetLanguage and ns.GetLanguage() or "en"
  return n[lang] or n.en or tostring(slot)
end

-- Evaluate(state, catalog, set) ->
--   { rows = {{slot, slotName, buffId, name, icon, valueText, status, bagCount}},
--     burst = {{buffId, name, icon, bagCount, unavailable}}, missingCount, unavailableCount }
-- slotName: the slot's localized name (the slot key when unknown).
-- A burst buff that is unknown, has no catalog entry or is UNAVAILABLE is marked
-- unavailable and not counted as missing.
-- `state` is unused (kept for API symmetry with MaxCalc:Compute). Picks are read
-- through ns.Sets:Resolve (one row per buff, under its current slot).
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
  for slot, buffId in pairs(ns.Sets:Resolve(set)) do
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
        slot = slot, slotName = slotName(slots, slot), buffId = buffId,
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
    local gone = not buff or not e or e.status == "UNAVAILABLE"
    local n = buff and ns.Bags:CountBuff(buff) or 0
    if n == 0 and not gone then missing = missing + 1 end
    burst[#burst + 1] = {
      buffId = buffId,
      name = buff and buff.name or ("#" .. tostring(buffId)),
      icon = VM.IconFor(e and e.rankSpell),
      bagCount = n,
      unavailable = gone or nil,
    }
  end

  return { rows = rows, burst = burst, missingCount = missing, unavailableCount = unavailable }
end
