local _, ns = ...

-- Per-character buff sets in ns.CharDB (FullBuffCharDB):
--   sets[id] = { name, picks = {[slotId] = buffId | false}, burst = {buffId,...}, spec = nil|1|2|3,
--                auto = true|nil }
--   activeSet, nextSetId.   picks: false = "not used", absent = empty.
-- auto: only the default set made by EnsureDefault; while set, its picks follow the
-- current recommendations (recomputed on FULLBUFF_STATE). Any Pick clears it.
-- Every mutation fires FULLBUFF_SET. Picks naming unknown buffs/slots are never pruned.
-- Picks are saved under a slot key, but a data rebuild may move a buff to another
-- slot: readers use Sets:Resolve(set), which files every pick under its buff's slot.
local Sets = {}
ns.Sets = Sets

local lastSpec
-- Spec binding and auto picks wait for PLAYER_ENTERING_WORLD: before it the talent
-- snapshot may be incomplete (spec 1 by default).
local worldReady = false

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

-- Default picks (Create, auto sets): per slot with a recommendation, the best-scoring
-- available (ACTIVE/CAN_ADD, non-burst) CLASS buff scoring > 0 when there is one
-- (buffs from players come first; ties: lower id), else the recommended entry.
local function recommendedPicks()
  local picks = {}
  local ok, state = pcall(function() return ns.PlayerState:Get() end)
  if not ok or not state then return picks end
  local catalog = ns.Catalog:Build(state)
  ns.Scoring:MarkRecommended(catalog, state)
  local classBest = {}
  for _, cat in ipairs(catalog.order or {}) do
    for _, e in ipairs(catalog[cat] or {}) do
      if e.recommended == true and not e.burst and e.excl then
        picks[e.excl] = e.id
      end
      if cat == "CLASS" and e.excl and not e.burst and (e.status == "ACTIVE" or e.status == "CAN_ADD") then
        local sc = ns.Scoring:Score(e.fx or {}, state)
        local b = classBest[e.excl]
        if sc > 0 and (not b or sc > b.score or (sc == b.score and e.id < b.id)) then
          classBest[e.excl] = { id = e.id, score = sc }
        end
      end
    end
  end
  for slot in pairs(picks) do
    if classBest[slot] then picks[slot] = classBest[slot].id end
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
    local id = self:Create(ns.L.SET_DEFAULT_NAME)
    if id then c.sets[id].auto = true end
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

-- The slot a saved pick belongs to: its buff's current slot, else the saved key.
local function slotOf(key, buffId)
  local buff = buffId and ns.Buffs and ns.Buffs[buffId]
  return buff and buff.excl or key
end

local function keyLess(a, b) return tostring(a) < tostring(b) end

-- Resolve(set) -> { [slotKey] = buffId | false }: every pick under its buff's current
-- slot (unknown buffs keep their saved key; false stays under its key). A buff id
-- picked under several keys, or two picks landing in one slot: the first by saved-key
-- order wins.
function Sets:Resolve(set)
  local out, seen = {}, {}
  local picks = set and set.picks
  if not picks then return out end
  local keys = {}
  for k in pairs(picks) do keys[#keys + 1] = k end
  table.sort(keys, keyLess)
  for _, k in ipairs(keys) do
    local v = picks[k]
    if v == false then
      if out[k] == nil then out[k] = false end
    elseif v ~= nil and not seen[v] then
      seen[v] = true
      local slot = slotOf(k, v)
      if out[slot] == nil then out[slot] = v end
    end
  end
  return out
end

-- buffId: a buff id, false ("not used") or nil (empty). Other keys whose pick
-- resolves to the same slot are removed first; the set stops following recommendations.
function Sets:Pick(id, slotId, buffId)
  local set = self:Get(id)
  if not set then return end
  for k, v in pairs(set.picks) do
    if k ~= slotId and slotOf(k, v) == slotId then set.picks[k] = nil end
  end
  set.picks[slotId] = buffId
  set.auto = nil
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

local function samePicks(a, b)
  for k, v in pairs(a) do
    if b[k] ~= v then return false end
  end
  for k in pairs(b) do
    if a[k] == nil then return false end
  end
  return true
end

-- Recompute the picks of every auto set from the current recommendations.
function Sets:RefreshAuto()
  local c = db()
  if not c then return end
  local picks
  for _, set in pairs(c.sets) do
    if set.auto then
      picks = picks or recommendedPicks()
      if not samePicks(set.picks, picks) then
        local copy = {}
        for k, v in pairs(picks) do copy[k] = v end
        set.picks = copy
        changed()
      end
    end
  end
end

-- Spec binding (switch to the set bound to the current spec) + auto picks.
local function sync()
  if not worldReady then return end
  local c = db()
  if not c then return end
  local state = ns.PlayerState:Get()
  local spec = state and state.spec
  if spec and spec ~= lastSpec then
    lastSpec = spec
    for id, set in pairs(c.sets) do
      if set.spec == spec then
        if c.activeSet ~= id then Sets:SetActive(id) end
        break
      end
    end
  end
  Sets:RefreshAuto()
end

-- After PLAYER_ENTERING_WORLD run one catch-up even if no new FULLBUFF_STATE fires
-- (the snapshot may not change after the world loads). Usually redundant: PlayerState
-- also refreshes on PEW and its FULLBUFF_STATE runs sync first; a second sync is a
-- no-op then (lastSpec already seen, RefreshAuto fires only on changed picks).
ns.Events:On("PLAYER_ENTERING_WORLD", function()
  worldReady = true
  ns.Events:Debounce("setsWorld", 0.5, sync)
end)

ns.Events:On("FULLBUFF_STATE", sync)
