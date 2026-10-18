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
--   { rows = {{slot, slotName, buffId, name, icon, valueText, status, via, upgrade, bagCount}},
--     burst = {{buffId, name, icon, bagCount, unavailable}}, missingCount, unavailableCount }
-- slotName: the slot's localized name (the slot key when unknown).
-- A picked buff that is not up while another buff of its slot (same excl) is ACTIVE
-- gives an ACTIVE row with via = that buff's name (lowest id when several);
-- valueText then shows the active buff's effects. upgrade = true: the picked buff is up
-- at a lower rank than the best allowed one (still ACTIVE, not counted as missing).
-- A burst buff that is unknown, has no catalog entry or is UNAVAILABLE is marked
-- unavailable and not counted as missing.
-- `state` is unused (kept for API symmetry with MaxCalc:Compute). Picks are read
-- through ns.Sets:Resolve (one row per buff, under its current slot).
function SetTracker:Evaluate(state, catalog, set)
  local VM = ns.ViewModel
  local byId, activeIn = {}, {}
  for key, list in pairs(catalog or {}) do
    if key ~= "order" and type(list) == "table" then
      for _, e in ipairs(list) do
        byId[e.id] = e
        -- the lowest-id ACTIVE non-burst entry of each slot
        if e.status == "ACTIVE" and e.excl and not e.burst then
          local cur = activeIn[e.excl]
          if not cur or (e.id or 0) < (cur.id or 0) then activeIn[e.excl] = e end
        end
      end
    end
  end
  local buffs = ns.Buffs or {}
  local slots = ns.Slots or {}

  local rows, missing, unavailable = {}, 0, 0
  for slot, buffId in pairs(ns.Sets:Resolve(set)) do
    if buffId then
      local buff, e = buffs[buffId], byId[buffId]
      local status, via
      local other = activeIn[(e and e.excl) or slot]
      if e and e.status == "ACTIVE" then
        status = "ACTIVE"
      elseif other and other.id ~= buffId then
        -- another member of the slot is up: the slot is filled
        status, via = "ACTIVE", other
      elseif not buff or not e or e.status == "UNAVAILABLE" then
        status = "UNAVAILABLE"
        unavailable = unavailable + 1
      else
        status = "MISSING"
        missing = missing + 1
      end
      local shown = via or e
      rows[#rows + 1] = {
        slot = slot, slotName = slotName(slots, slot), buffId = buffId,
        name = buff and buff.name or ("#" .. tostring(buffId)),
        icon = VM.IconFor(e and e.rankSpell),
        valueText = (shown and status ~= "UNAVAILABLE") and VM.FormatFx(shown.activeFx or shown.fx) or "",
        status = status,
        via = via and (via.name or tostring(via.id)) or nil,
        upgrade = (not via and e and e.upgrade) and true or nil,
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
