local _, ns = ...

-- Map pins for buff sources (world map + minimap) through HereBeDragons-Pins.
-- Persisted in ns.CharDB.pins as ["<buffId>:<sourceIndex>"] = true; the source
-- index is the position in ns.Sources[buffId]. Only the key is stored: position
-- and text are read from ns.Sources on every restore, so a source that no longer
-- exists or lost its coordinates is dropped silently.
-- Right-click on a pin removes it. No C_Map user waypoints (unreliable on Forever).
--
-- Pin icon: the red cross raid marker "Interface\\TargetingFrame\\UI-RaidTargetingIcon_7"
-- (a single-file texture present in every client, same family as the popover star).
local Pins = {}
ns.Pins = Pins

local ICON = "Interface\\TargetingFrame\\UI-RaidTargetingIcon_7"
local SIZE_WORLD, SIZE_MINI = 16, 12
local LIB_NAMES = { "HereBeDragons-Pins-2.0" }

local drawn = {}      -- key -> { world = frame, minimap = frame }
local pool = { world = {}, minimap = {} }

local function lib()
  if not LibStub then return nil end
  for _, name in ipairs(LIB_NAMES) do
    local l = LibStub(name, true)
    if l then return l end
  end
end

local function makeKey(buffId, index) return buffId .. ":" .. index end

local function parseKey(key)
  local b, i = tostring(key):match("^(%d+):(%d+)$")
  if b then return tonumber(b), tonumber(i) end
end

local function sourceFor(buffId, index)
  local list = ns.Sources and ns.Sources[buffId]
  local src = list and list[index]
  if src and ns.Detail.HasCoords(src) then return src end
end

local function store()
  if not ns.CharDB then return nil end
  ns.CharDB.pins = ns.CharDB.pins or {}
  return ns.CharDB.pins
end

local function newIcon(kind)
  local f = CreateFrame("Frame", nil, UIParent)
  local size = kind == "world" and SIZE_WORLD or SIZE_MINI
  f:SetSize(size, size)
  f:EnableMouse(true)
  f.tex = f:CreateTexture(nil, "OVERLAY")
  f.tex:SetAllPoints()
  f.tex:SetTexture(ICON)
  f:SetScript("OnEnter", function(self)
    local buffId, index = parseKey(self.fbKey)
    local src = buffId and sourceFor(buffId, index)
    local buff = buffId and ns.Buffs and ns.Buffs[buffId]
    GameTooltip:SetOwner(self, "ANCHOR_RIGHT")
    GameTooltip:AddLine(buff and buff.name or tostring(buffId))
    if src then GameTooltip:AddLine(ns.Detail:SourceText(src)) end
    GameTooltip:AddLine(ns.L.PIN_REMOVE_HINT)
    GameTooltip:Show()
  end)
  f:SetScript("OnLeave", function() GameTooltip:Hide() end)
  f:SetScript("OnMouseUp", function(self, button)
    if button == "RightButton" then Pins:Remove(self.fbKey) end
  end)
  return f
end

local function takeIcon(kind, key)
  local f = table.remove(pool[kind])
  if not f then f = newIcon(kind) end
  f.fbKey = key
  return f
end

local function undraw(key)
  local d = drawn[key]
  if not d then return end
  local l = lib()
  for kind, f in pairs(d) do
    if l then
      if kind == "world" then l:RemoveWorldMapIcon(Pins, f) else l:RemoveMinimapIcon(Pins, f) end
    end
    f:Hide()
    f.fbKey = nil
    pool[kind][#pool[kind] + 1] = f
  end
  drawn[key] = nil
end

local function draw(key, src)
  undraw(key)
  local l = lib()
  if not l then return end
  local d = { world = takeIcon("world", key), minimap = takeIcon("minimap", key) }
  drawn[key] = d
  local flag = _G.HBD_PINS_WORLDMAP_SHOW_CONTINENT or 2
  l:AddWorldMapIconMap(Pins, d.world, src.mapID, src.x, src.y, flag)
  l:AddMinimapIconMap(Pins, d.minimap, src.mapID, src.x, src.y, true, true)
end

local function changed()
  if ns.Events then ns.Events:Fire("FULLBUFF_PINS") end
end

-- Pin one source. Returns false when the source does not exist or has no coordinates.
function Pins:Add(buffId, index)
  local src = sourceFor(buffId, index)
  local db = store()
  if not src or not db then return false end
  local key = makeKey(buffId, index)
  db[key] = true
  draw(key, src)
  changed()
  return true
end

-- Pin every source with coordinates; returns how many were pinned.
function Pins:AddAll(buffId)
  local list = ns.Sources and ns.Sources[buffId]
  local n = 0
  local db = store()
  if not list or not db then return 0 end
  for i = 1, #list do
    local src = sourceFor(buffId, i)
    if src then
      local key = makeKey(buffId, i)
      db[key] = true
      draw(key, src)
      n = n + 1
    end
  end
  if n > 0 then changed() end
  return n
end

function Pins:Remove(key)
  local db = store()
  undraw(key)
  if db then db[key] = nil end
  changed()
end

function Pins:Clear()
  local db = store()
  local keys = {}
  for key in pairs(drawn) do keys[#keys + 1] = key end
  for _, key in ipairs(keys) do undraw(key) end
  if db then wipe(db) end
  changed()
end

function Pins:Has(key)
  local db = store()
  return db ~= nil and db[key] ~= nil
end

-- Sorted list of the saved pins that still resolve to a source:
-- { {key, buffId, index, mapID, x, y, text, buffName} }
function Pins:List()
  local out = {}
  local db = store()
  if not db then return out end
  for key in pairs(db) do
    local buffId, index = parseKey(key)
    local src = buffId and sourceFor(buffId, index)
    if src then
      local buff = ns.Buffs and ns.Buffs[buffId]
      out[#out + 1] = {
        key = key, buffId = buffId, index = index, mapID = src.mapID, x = src.x, y = src.y,
        text = ns.Detail:SourceText(src), buffName = buff and buff.name or tostring(buffId),
      }
    end
  end
  table.sort(out, function(a, b)
    if a.buffId ~= b.buffId then return a.buffId < b.buffId end
    return a.index < b.index
  end)
  return out
end

-- The drawn icon frame of a pin ("world" or "minimap"); nil when not drawn.
function Pins:GetIcon(key, kind)
  return drawn[key] and drawn[key][kind]
end

-- Redraw every saved pin (after login / loading screens); drops stale entries.
function Pins:Restore()
  local db = store()
  if not db then return end
  local keys = {}
  for key in pairs(drawn) do keys[#keys + 1] = key end
  for _, key in ipairs(keys) do undraw(key) end
  local stale = {}
  for key in pairs(db) do
    local buffId, index = parseKey(key)
    local src = buffId and sourceFor(buffId, index)
    if src then draw(key, src) else stale[#stale + 1] = key end
  end
  for _, key in ipairs(stale) do db[key] = nil end
end

ns.Events:On("FULLBUFF_LOADED", function() Pins:Restore() end)
ns.Events:On("PLAYER_ENTERING_WORLD", function() Pins:Restore() end)
