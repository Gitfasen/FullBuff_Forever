local _, ns = ...

-- DetailCard: what a buff gives and every place it comes from. Sources with
-- coordinates can be pinned on the world map and the minimap (ns.Pins).
--
-- ns.Detail:Model(buffId, state?) -> {
--   id, name, fxLines = {"+8 Strength", ...}, durText, minLevel, score,
--   groupMembers = {names of the other buffs that share the stacking group},
--   sources = { {text, loc?, pinnable, index} }  -- one "Source unknown" row when none
-- }
-- Pure data, no frames: the frame code below only renders it.
local Detail = {}
ns.Detail = Detail
ns.UI = ns.UI or {}

local SRC_KEYS = {
  vendor = "SRC_VENDOR", drop = "SRC_DROP", quest = "SRC_QUEST", craft = "SRC_CRAFT",
  npc = "SRC_NPC", object = "SRC_OBJECT", camping = "SRC_CAMPING",
}

local function zoneName(mapID)
  local info = C_Map and C_Map.GetMapInfo and C_Map.GetMapInfo(mapID)
  return info and info.name or ns.L.ZONE_UNKNOWN
end

local function hasCoords(src)
  return type(src.mapID) == "number" and type(src.x) == "number" and type(src.y) == "number"
end
Detail.HasCoords = hasCoords

-- "Zone 45.6, 50.0" or nil
local function locText(src)
  if not hasCoords(src) then return nil end
  return string.format("%s %.1f, %.1f", zoneName(src.mapID), src.x * 100, src.y * 100)
end

-- Text of one source row (also the pin tooltip). Formats:
--   vendor "Vendor: %s (%s %.1f, %.1f)", craft "Crafted: %s %s",
--   camping "Camping: %s (%s)", others "Kind: %s".
-- A vendor without coordinates, and craft/camping without a note, drop the extras.
function Detail:SourceText(src)
  local L = ns.L
  local label = L[SRC_KEYS[src.kind] or "SRC_DROP"]
  local name = tostring(src.name or "?")
  if src.kind == "vendor" and hasCoords(src) then
    return string.format("%s: %s (%s %.1f, %.1f)", label, name, zoneName(src.mapID), src.x * 100, src.y * 100)
  elseif src.kind == "craft" and src.note then
    return string.format("%s: %s %s", label, name, tostring(src.note))
  elseif src.kind == "camping" and src.note then
    return string.format("%s: %s (%s)", label, name, tostring(src.note))
  end
  return string.format("%s: %s", label, name)
end

local function durText(sec)
  sec = tonumber(sec) or 0
  if sec <= 0 then return "" end
  local L = ns.L
  local h = math.floor(sec / 3600)
  local m = math.floor((sec % 3600) / 60)
  local s = math.floor(sec % 60)
  local parts = {}
  if h > 0 then parts[#parts + 1] = h .. " " .. L.TIME_H end
  if m > 0 then parts[#parts + 1] = m .. " " .. L.TIME_M end
  if s > 0 then parts[#parts + 1] = s .. " " .. L.TIME_S end
  return table.concat(parts, " ")
end

local function minLevel(buff)
  local lvl = buff.lvl or 0
  if buff.ranks and #buff.ranks > 0 then
    lvl = nil
    for _, r in ipairs(buff.ranks) do
      if r.lvl and (not lvl or r.lvl < lvl) then lvl = r.lvl end
    end
    lvl = lvl or buff.lvl or 0
  end
  return lvl
end

local MAX_MEMBERS = 6

-- "A, B, C, D, E, F, +3 more": at most MAX_MEMBERS names, the rest counted.
function Detail.MembersText(names)
  local shown = {}
  for i = 1, math.min(#names, MAX_MEMBERS) do shown[i] = names[i] end
  local text = table.concat(shown, ", ")
  if #names > MAX_MEMBERS then text = text .. string.format(ns.L.MORE_FMT, #names - MAX_MEMBERS) end
  return text
end

function Detail:Model(buffId, state)
  local L = ns.L
  local buff = (ns.Buffs or {})[buffId] or {}
  local shared = state == nil -- the current snapshot: reuse the view model's catalog
  state = state or ns.PlayerState:Get()

  -- Effects as the player's rank would give them: take them from the catalog entry.
  local fx = buff.fx
  local ok, catalog = pcall(function()
    if shared then return ns.ViewModel:Get().catalog end
    return ns.Catalog:Build(state)
  end)
  if not ok then
    geterrorhandler()(catalog) -- report, then fall back to the buff's base effects
    catalog = nil
  end
  if catalog then
    for _, cat in ipairs(catalog.order or {}) do
      for _, e in ipairs(catalog[cat]) do
        if e.id == buffId then fx = e.fx end
      end
    end
  end

  local members = {}
  if buff.excl then
    local others = {}
    for id, b in pairs(ns.Buffs or {}) do
      if id ~= buffId and b.excl == buff.excl then others[#others + 1] = { id = id, b = b } end
    end
    table.sort(others, function(a, b)
      if (a.b.name or "") ~= (b.b.name or "") then return (a.b.name or "") < (b.b.name or "") end
      return a.id < b.id
    end)
    local count = {}
    for _, o in ipairs(others) do count[o.b.name or ""] = (count[o.b.name or ""] or 0) + 1 end
    for _, o in ipairs(others) do
      local name = tostring(o.b.name or o.id)
      -- same name as another member (e.g. scroll ranks): add the effect to tell them apart
      if count[o.b.name or ""] > 1 or o.b.name == buff.name then
        local fxText = ns.ViewModel.FormatFx(o.b.fx)
        if fxText ~= "" then name = name .. " (" .. fxText .. ")" end
      end
      members[#members + 1] = name
    end
  end

  local sources = {}
  local list = (ns.Sources or {})[buffId]
  if list and #list > 0 then
    for i, src in ipairs(list) do
      sources[#sources + 1] = {
        text = Detail:SourceText(src),
        loc = (src.kind ~= "vendor") and locText(src) or nil, -- vendor text already has it
        pinnable = hasCoords(src), index = i,
      }
    end
  else
    sources[1] = { text = L.SOURCE_UNKNOWN, pinnable = false }
  end

  return {
    id = buffId,
    name = buff.name or tostring(buffId),
    fxLines = ns.ViewModel.FxEntries(fx),
    durText = durText(buff.dur),
    minLevel = minLevel(buff),
    score = ns.Scoring:Score(fx or {}, state),
    groupMembers = members,
    sources = sources,
  }
end

-- ---------------------------------------------------------------------------
-- Frame
-- ---------------------------------------------------------------------------
local FRAME_NAME = "FullBuffDetail"
local WIDTH, HEIGHT = 330, 440
local ROW_H = 32
local PIN_ICON = "Interface\\TargetingFrame\\UI-RaidTargetingIcon_7"

local frame, infoText, scroll, content, titleText, whereText, pinAll, clearPins
local rows = {}
local currentId

local function newRow()
  local r = CreateFrame("Button", nil, content)
  r:SetHeight(ROW_H)
  r.text = r:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
  r.text:SetJustifyH("LEFT")
  r.text:SetPoint("TOPLEFT", 2, -2)
  r.text:SetPoint("BOTTOMRIGHT", -28, 2)
  r.pin = CreateFrame("Button", nil, r)
  r.pin:SetSize(22, 22)
  r.pin:SetPoint("RIGHT", -2, 0)
  r.pin.tex = r.pin:CreateTexture(nil, "ARTWORK")
  r.pin.tex:SetAllPoints()
  r.pin.tex:SetTexture(PIN_ICON)
  r.pin:SetScript("OnClick", function(self)
    local key = currentId .. ":" .. self.fbIndex
    if ns.Pins:Has(key) then ns.Pins:Remove(key) else ns.Pins:Add(currentId, self.fbIndex) end
  end)
  r.pin:SetScript("OnEnter", function(self)
    GameTooltip:SetOwner(self, "ANCHOR_RIGHT")
    GameTooltip:AddLine(ns.L.PIN_TOGGLE_HINT)
    GameTooltip:Show()
  end)
  r.pin:SetScript("OnLeave", function() GameTooltip:Hide() end)
  return r
end

function Detail:Refresh()
  if not frame or not currentId then return end
  local L = ns.L
  local m = Detail:Model(currentId)
  titleText:SetText(m.name)
  local info = {}
  for _, line in ipairs(m.fxLines) do info[#info + 1] = line end
  if m.durText ~= "" then info[#info + 1] = L.DURATION .. ": " .. m.durText end
  if m.minLevel and m.minLevel > 0 then info[#info + 1] = L.MIN_LEVEL .. ": " .. m.minLevel end
  info[#info + 1] = string.format("%s: %.1f", L.SCORE, m.score)
  if #m.groupMembers > 0 then
    info[#info + 1] = L.NOT_STACK_WITH .. ": " .. Detail.MembersText(m.groupMembers)
  else
    info[#info + 1] = L.STACKS_WITH_NONE
  end
  infoText:SetText(table.concat(info, "\n"))
  whereText:SetText(L.WHERE_TO_GET)
  pinAll:SetText(L.PIN_ALL)
  clearPins:SetText(L.CLEAR_PINS)

  local y = 0
  for i, s in ipairs(m.sources) do
    local r = rows[i]
    if not r then
      r = newRow()
      rows[i] = r
    end
    r:ClearAllPoints()
    r:SetPoint("TOPLEFT", content, "TOPLEFT", 0, -y)
    r:SetPoint("TOPRIGHT", content, "TOPRIGHT", 0, -y)
    local text = s.text
    -- rows whose text lacks the coordinates (drop, npc ...) show them after it
    if s.loc then text = text .. " (" .. s.loc .. ")" end
    r.text:SetText(text)
    r.pin.fbIndex = s.index
    if s.pinnable then
      r.pin:Show()
      r.pin:SetAlpha(ns.Pins:Has(currentId .. ":" .. s.index) and 1 or 0.4)
    else
      r.pin:Hide()
    end
    r:Show()
    y = y + ROW_H
  end
  for i = #m.sources + 1, #rows do rows[i]:Hide() end
  content:SetHeight(math.max(y, 1))
end

function Detail:Reposition()
  if not frame then return end
  frame:ClearAllPoints()
  local pop = _G.FullBuffPopover
  if pop and pop:IsShown() then
    local right = pop:GetRight() or 0
    if right + WIDTH + 4 <= GetScreenWidth() then
      frame:SetPoint("TOPLEFT", pop, "TOPRIGHT", 4, 0)
    else
      frame:SetPoint("TOPRIGHT", pop, "TOPLEFT", -4, 0)
    end
  else
    frame:SetPoint("CENTER", UIParent, "CENTER", 0, 0)
  end
end

local function create()
  frame = CreateFrame("Frame", FRAME_NAME, UIParent, "BackdropTemplate")
  frame:SetSize(WIDTH, HEIGHT)
  frame:SetFrameStrata("DIALOG")
  frame:SetClampedToScreen(true)
  frame:SetBackdrop({
    bgFile = "Interface\\DialogFrame\\UI-DialogBox-Background",
    edgeFile = "Interface\\DialogFrame\\UI-DialogBox-Border",
    tile = true, tileSize = 32, edgeSize = 24,
    insets = { left = 6, right = 6, top = 6, bottom = 6 },
  })
  frame:Hide()

  titleText = frame:CreateFontString(nil, "OVERLAY", "GameFontNormalLarge")
  titleText:SetPoint("TOPLEFT", 16, -14)
  titleText:SetPoint("TOPRIGHT", -34, -14)
  titleText:SetJustifyH("LEFT")
  titleText:SetWordWrap(false)

  local close = CreateFrame("Button", nil, frame, "UIPanelCloseButton")
  close:SetPoint("TOPRIGHT", -2, -2)
  close:SetScript("OnClick", function() frame:Hide() end)

  infoText = frame:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
  infoText:SetPoint("TOPLEFT", 16, -38)
  infoText:SetPoint("TOPRIGHT", -16, -38)
  infoText:SetJustifyH("LEFT")
  infoText:SetJustifyV("TOP")
  infoText:SetHeight(120)

  whereText = frame:CreateFontString(nil, "OVERLAY", "GameFontNormal")
  whereText:SetPoint("TOPLEFT", 16, -166)

  scroll = CreateFrame("ScrollFrame", nil, frame, "UIPanelScrollFrameTemplate")
  scroll:SetPoint("TOPLEFT", 14, -186)
  scroll:SetPoint("BOTTOMRIGHT", -30, 46)
  content = CreateFrame("Frame", nil, scroll)
  content:SetSize(WIDTH - 50, 1)
  scroll:SetScrollChild(content)

  pinAll = CreateFrame("Button", nil, frame, "UIPanelButtonTemplate")
  pinAll:SetSize(130, 24)
  pinAll:SetPoint("BOTTOMLEFT", 16, 14)
  pinAll:SetScript("OnClick", function() ns.Pins:AddAll(currentId) end)
  clearPins = CreateFrame("Button", nil, frame, "UIPanelButtonTemplate")
  clearPins:SetSize(130, 24)
  clearPins:SetPoint("BOTTOMRIGHT", -16, 14)
  clearPins:SetScript("OnClick", function() ns.Pins:Clear() end)

  frame:SetScript("OnShow", function() Detail:Reposition(); Detail:Refresh() end)

  local registered = false
  for _, n in ipairs(UISpecialFrames) do
    if n == FRAME_NAME then registered = true end
  end
  if not registered then table.insert(UISpecialFrames, FRAME_NAME) end
end

function Detail:GetFrame() return frame end
function Detail:GetButtons() return { pinAll = pinAll, clear = clearPins } end
function Detail:GetRows() return rows end

function ns.UI.OpenDetail(buffId)
  if not frame then create() end
  currentId = buffId
  if frame:IsShown() then
    Detail:Reposition()
    Detail:Refresh()
  else
    frame:Show() -- OnShow positions and fills it
  end
end

local function refreshIfShown()
  if frame and frame:IsShown() then Detail:Refresh() end
end
ns.Events:On("FULLBUFF_PINS", refreshIfShown)
ns.Events:On("FULLBUFF_STATE", refreshIfShown)
ns.Events:On("FULLBUFF_LANGUAGE", refreshIfShown)
