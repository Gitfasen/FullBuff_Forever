local _, ns = ...

-- Per-character buff sets in ns.CharDB (FullBuffCharDB):
--   sets[id] = { name, picks = {[slotId] = buffId | false}, burst = {buffId,...}, spec = nil|1|2|3 }
--   activeSet, nextSetId.   picks: false = "not used", absent = empty.
-- Every mutation fires FULLBUFF_SET. Picks naming unknown buffs/slots are never pruned.
local Sets = {}
ns.Sets = Sets

local lastSpec

local function db()
  local c = ns.CharDB
  if not c then return nil end
  c.sets = c.sets or {}
  c.nextSetId = c.nextSetId or 1
  return c
end

local function changed()
  ns.Events:Fire("FULLBUFF_SET")
end

local function lowestId()
  local ids = Sets:List()
  return ids[1]
end

function Sets:List()
  local c = db()
  local ids = {}
  if c then
    for id in pairs(c.sets) do ids[#ids + 1] = id end
    table.sort(ids)
  end
  return ids
end

function Sets:Get(id)
  local c = db()
  return c and id and c.sets[id] or nil
end

function Sets:Active()
  local c = db()
  if not c then return nil end
  local set = c.sets[c.activeSet]
  if not set then return nil end
  return c.activeSet, set
end

function Sets:SetActive(id)
  local c = db()
  if not c or not c.sets[id] then return end
  c.activeSet = id
  changed()
end

local function recommendedPicks()
  local picks = {}
  local ok, state = pcall(function() return ns.PlayerState:Get() end)
  if not ok or not state then return picks end
  local catalog = ns.Catalog:Build(state)
  ns.Scoring:MarkRecommended(catalog, state)
  for _, cat in ipairs(catalog.order or {}) do
    for _, e in ipairs(catalog[cat] or {}) do
      if e.recommended == true and not e.burst and e.excl then
        picks[e.excl] = e.id
      end
    end
  end
  return picks
end

function Sets:Create(name)
  local c = db()
  if not c then return nil end
  local id = c.nextSetId
  c.nextSetId = id + 1
  c.sets[id] = {
    name = name or ns.L.SET_DEFAULT_NAME,
    picks = recommendedPicks(),
    burst = {},
  }
  if not c.sets[c.activeSet] then c.activeSet = id end
  changed()
  return id
end

function Sets:Copy(id)
  local c = db()
  local src = c and c.sets[id]
  if not src then return nil end
  local new = c.nextSetId
  c.nextSetId = new + 1
  local picks, burst = {}, {}
  for k, v in pairs(src.picks) do picks[k] = v end
  for i, v in ipairs(src.burst) do burst[i] = v end
  c.sets[new] = { name = src.name .. ns.L.SET_COPY_SUFFIX, picks = picks, burst = burst }
  changed()
  return new
end

function Sets:Rename(id, name)
  local set = self:Get(id)
  if not set or type(name) ~= "string" or name == "" then return end
  set.name = name
  changed()
end

function Sets:EnsureDefault()
  local c = db()
  if not c then return end
  if next(c.sets) == nil then
    self:Create(ns.L.SET_DEFAULT_NAME)
  elseif not c.sets[c.activeSet] then
    c.activeSet = lowestId()
    changed()
  end
end

function Sets:Delete(id)
  local c = db()
  if not c or not c.sets[id] then return end
  c.sets[id] = nil
  if c.activeSet == id or not c.sets[c.activeSet] then
    c.activeSet = lowestId()
  end
  if not c.activeSet then
    self:EnsureDefault()  -- recreates "Main" and fires
    return
  end
  changed()
end

-- buffId: a buff id, false ("not used") or nil (empty).
function Sets:Pick(id, slotId, buffId)
  local set = self:Get(id)
  if not set then return end
  set.picks[slotId] = buffId
  changed()
end

local function indexOf(list, v)
  for i, x in ipairs(list) do
    if x == v then return i end
  end
end

function Sets:AddBurst(id, buffId)
  local set = self:Get(id)
  if not set or indexOf(set.burst, buffId) then return end
  set.burst[#set.burst + 1] = buffId
  changed()
end

function Sets:RemoveBurst(id, buffId)
  local set = self:Get(id)
  local i = set and indexOf(set.burst, buffId)
  if not i then return end
  table.remove(set.burst, i)
  changed()
end

function Sets:MoveBurst(id, buffId, delta)
  local set = self:Get(id)
  local i = set and indexOf(set.burst, buffId)
  if not i then return end
  local j = math.max(1, math.min(#set.burst, i + (delta or 0)))
  if j == i then return end
  table.remove(set.burst, i)
  table.insert(set.burst, j, buffId)
  changed()
end

-- A spec belongs to at most one set: binding clears it from every other set.
function Sets:BindSpec(id, spec)
  local c = db()
  local set = c and c.sets[id]
  if not set then return end
  if spec then
    for oid, other in pairs(c.sets) do
      if oid ~= id and other.spec == spec then other.spec = nil end
    end
  end
  set.spec = spec
  changed()
end

ns.Events:On("FULLBUFF_LOADED", function() Sets:EnsureDefault() end)

ns.Events:On("FULLBUFF_STATE", function()
  local state = ns.PlayerState:Get()
  local spec = state and state.spec
  if not spec or spec == lastSpec then return end
  lastSpec = spec
  local c = db()
  if not c then return end
  for id, set in pairs(c.sets) do
    if set.spec == spec then
      if c.activeSet ~= id then Sets:SetActive(id) end
      return
    end
  end
end)
