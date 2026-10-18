local _, ns = ...

-- Popover: set button + stats (current -> max with the active set) + the set's buffs
-- + the burst block, anchored to the launcher.
ns.UI = ns.UI or {}
local Popover = {}
ns.UI.Popover = Popover
ns.UI.Toggle = function() Popover:Toggle() end

local FRAME_NAME = "FullBuffPopover"
local WIDTH, HEIGHT = 340, 440
local STAT_H, SECTION_H, ITEM_H = 16, 22, 32
local RED = "|cffff2020"

local CHECK = ns.UI.MARK_CHECK
local frame, scroll, content, staleText, titleText, headerText, setButton
local pool, used = {}, 0

local function db()
  ns.DB = ns.DB or {}
  return ns.DB
end

local COLORS = {
  ACTIVE = { 0.25, 1, 0.25 }, -- green: already have it
  MISSING = { 1, 1, 1 },
  UNAVAILABLE = { 0.5, 0.5, 0.5 },
}

local function newLine()
  local b = CreateFrame("Button", nil, content)
  b:SetHeight(ITEM_H)
  b.bg = b:CreateTexture(nil, "BACKGROUND")
  b.bg:SetAllPoints()
  b.icon = b:CreateTexture(nil, "ARTWORK")
  b.icon:SetSize(24, 24)
  b.icon:SetPoint("LEFT", 4, 0)
  b.name = b:CreateFontString(nil, "OVERLAY", "GameFontHighlight")
  b.name:SetJustifyH("LEFT")
  b.sub = b:CreateFontString(nil, "OVERLAY", "GameFontDisableSmall")
  b.sub:SetJustifyH("LEFT")
  b.c1 = b:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
  b.c2 = b:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
  b.c3 = b:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
  b:SetScript("OnEnter", function(self)
    if self.fbKind ~= "item" and self.fbKind ~= "burst" then return end
    if not self.fbName then return end
    GameTooltip:SetOwner(self, "ANCHOR_RIGHT")
    GameTooltip:AddLine(self.fbName or "")
    GameTooltip:Show()
  end)
  b:SetScript("OnLeave", function() GameTooltip:Hide() end)
  b:SetScript("OnClick", function(self)
    if (self.fbKind == "item" or self.fbKind == "burst") and self.fbId then
      ns.UI.OpenDetail(self.fbId)
    elseif self.fbKind == "options" then
      if ns.UI.OpenOptions then ns.UI.OpenOptions() end
    end
  end)
  return b
end

-- Take a pooled line, reset it and place it at y; returns the line and the next y.
local function takeLine(y, kind, height)
  used = used + 1
  local b = pool[used]
  if not b then
    b = newLine()
    pool[used] = b
  end
  b.fbKind, b.fbId, b.fbStatus, b.fbName = kind, nil, nil, nil
  b:SetAlpha(1)
  b:SetHeight(height)
  b:ClearAllPoints()
  b:SetPoint("TOPLEFT", content, "TOPLEFT", 0, -y)
  b:SetPoint("TOPRIGHT", content, "TOPRIGHT", 0, -y)
  b.bg:SetColorTexture(0, 0, 0, 0)
  b.icon:Hide()
  for _, fs in ipairs({ b.name, b.sub, b.c1, b.c2, b.c3 }) do
    fs:SetText("")
    fs:ClearAllPoints()
    fs:SetTextColor(1, 1, 1)
  end
  b:Show()
  return b, y + height
end

local function sign(n)
  if n > 0 then return "+" .. n end
  return tostring(n)
end

local function statColumns(b)
  b.c1:SetPoint("LEFT", 6, 0)
  b.c1:SetWidth(130)
  b.c1:SetJustifyH("LEFT")
  b.c2:SetPoint("LEFT", 140, 0)
  b.c2:SetWidth(60)
  b.c2:SetJustifyH("RIGHT")
  b.c3:SetPoint("LEFT", 206, 0)
  b.c3:SetWidth(100)
  b.c3:SetJustifyH("LEFT")
end

function Popover:Refresh()
  if not frame then return end
  local vm = ns.ViewModel:Get()
  local L = ns.L
  titleText:SetText(L.TITLE)
  setButton:SetText(string.format("%s: %s", L.SET_LABEL, vm.header.setName or ""))
  -- one line under the title: the stale warning wins over the spec hint
  if vm.header.stale then
    staleText:SetText(L.STALE_AFTER_COMBAT)
    staleText:SetTextColor(1, 0.6, 0.2)
  else
    staleText:SetText(vm.header.specHint or "")
    staleText:SetTextColor(0.7, 0.7, 0.7)
  end
  headerText:SetText(string.format("%s - %s - %d", vm.header.class or "", vm.header.specName or "", vm.header.level or 0))

  used = 0
  local y = 0
  local b
  b, y = takeLine(y, "stat", STAT_H)
  statColumns(b)
  b.c1:SetText(L.COL_STAT)
  b.c2:SetText(L.COL_NOW)
  b.c3:SetText("  " .. L.COL_MAX)
  for _, r in ipairs(vm.header.rows) do
    b, y = takeLine(y, "stat", STAT_H)
    statColumns(b)
    b.c1:SetText(r.label)
    b.c2:SetText(tostring(r.current))
    if r.diff ~= 0 then
      b.c3:SetText("  |cff66ff66" .. tostring(r.max) .. " (" .. sign(r.diff) .. ")|r")
    else
      b.c3:SetText("  " .. tostring(r.max))
    end
  end
  y = y + 8

  if vm.empty then
    b, y = takeLine(y, "empty", SECTION_H)
    b.name:SetPoint("LEFT", 6, 0)
    b.name:SetText(L.SET_EMPTY)
    b, y = takeLine(y, "options", SECTION_H)
    b.bg:SetColorTexture(1, 1, 1, 0.08)
    b.name:SetPoint("LEFT", 6, 0)
    b.name:SetText(L.SET_OPEN_SETTINGS)
  end

  -- rows sharing a name (e.g. two "Well Fed") get their slot name in the sub-line
  local nameCount = {}
  for _, it in ipairs(vm.list) do nameCount[it.name] = (nameCount[it.name] or 0) + 1 end
  for _, it in ipairs(vm.list) do
    b, y = takeLine(y, "item", ITEM_H)
    b.fbStatus = it.status
    if it.status ~= "UNAVAILABLE" then b.fbId = it.buffId end
    b.fbName = it.name
    b.icon:SetTexture(it.icon)
    b.icon:Show()
    b.name:SetPoint("TOPLEFT", 34, -4)
    b.name:SetPoint("TOPRIGHT", -4, -4)
    b.sub:SetPoint("BOTTOMLEFT", 34, 4)
    b.sub:SetPoint("BOTTOMRIGHT", -4, 4)
    b.name:SetWordWrap(false)
    b.sub:SetWordWrap(false)
    local sub = it.valueText or ""
    if it.status == "ACTIVE" then
      b.name:SetText(CHECK .. " " .. it.name)
    else
      b.name:SetText(it.name)
    end
    if it.status == "UNAVAILABLE" then sub = L.SET_UNAVAILABLE end
    local function append(text) sub = (sub ~= "" and (sub .. "  ·  ") or "") .. text end
    if it.upgrade then append(L.RANK_UPGRADE) end
    if nameCount[it.name] > 1 and it.slotName then
      append(it.slotName)
    end
    if it.status == "MISSING" and (it.bagCount or 0) > 0 then
      sub = sub .. "  " .. L.IN_BAGS:format(it.bagCount)
    end
    b.sub:SetText(sub)
    local c = COLORS[it.status] or COLORS.MISSING
    b.name:SetTextColor(c[1], c[2], c[3])
  end

  if #vm.burst > 0 then
    b, y = takeLine(y, "section", SECTION_H)
    b.bg:SetColorTexture(1, 1, 1, 0.08)
    b.name:SetPoint("LEFT", 6, 0)
    b.name:SetText(L.BURST_TITLE)
    for _, it in ipairs(vm.burst) do
      b, y = takeLine(y, "burst", ITEM_H)
      b.fbName = it.name
      b.icon:SetTexture(it.icon)
      b.icon:Show()
      b.name:SetWordWrap(false)
      b.name:SetText(it.name)
      if it.unavailable then
        -- greyed, with the unavailable text; no bag count, no detail card
        b.name:SetPoint("TOPLEFT", 34, -4)
        b.name:SetPoint("TOPRIGHT", -4, -4)
        b.sub:SetPoint("BOTTOMLEFT", 34, 4)
        b.sub:SetPoint("BOTTOMRIGHT", -4, 4)
        b.sub:SetWordWrap(false)
        b.sub:SetText(L.SET_UNAVAILABLE)
        local c = COLORS.UNAVAILABLE
        b.name:SetTextColor(c[1], c[2], c[3])
      else
        b.fbId = it.buffId
        b.name:SetPoint("LEFT", 34, 0)
        b.name:SetPoint("RIGHT", -50, 0)
        b.c2:SetPoint("RIGHT", -6, 0)
        b.c2:SetWidth(44)
        b.c2:SetJustifyH("RIGHT")
        local n = it.bagCount or 0
        if n == 0 then
          b.c2:SetText(RED .. "×0|r")
        else
          b.c2:SetText("×" .. n)
        end
      end
    end
  end
  for i = used + 1, #pool do pool[i]:Hide() end
  content:SetHeight(math.max(y, 1))
end

-- Anchor next to the launcher, on the side (and vertical half) with more room.
function Popover:Reposition()
  if not frame then return end
  frame:SetScale(db().scale or 1)
  frame:ClearAllPoints()
  local l = ns.UI.Launcher and ns.UI.Launcher:GetFrame()
  if not l then
    frame:SetPoint("CENTER", UIParent, "CENTER", 0, 0)
    return
  end
  local cx, cy = l:GetCenter()
  local sw, sh = GetScreenWidth(), GetScreenHeight()
  local ls = l:GetEffectiveScale() / UIParent:GetEffectiveScale()
  cx, cy = (cx or sw / 2) * ls, (cy or sh / 2) * ls
  local left = cx > sw / 2 -- more room on the left
  local top = cy > sh / 2  -- more room below
  local vert = top and "TOP" or "BOTTOM"
  local from = vert .. (left and "RIGHT" or "LEFT")
  local to = vert .. (left and "LEFT" or "RIGHT")
  frame:SetPoint(from, l, to, left and -4 or 4, 0)
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
  headerText = frame:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
  headerText:SetPoint("TOPRIGHT", -34, -18)
  staleText = frame:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
  staleText:SetPoint("TOPLEFT", 16, -36)
  staleText:SetTextColor(1, 0.6, 0.2)

  local close = CreateFrame("Button", nil, frame, "UIPanelCloseButton")
  close:SetPoint("TOPRIGHT", -2, -2)
  close:SetScript("OnClick", function() frame:Hide() end)

  -- Set switcher: shows the active set's name; each click activates the next set in
  -- ns.Sets:List() order (wrapping around). A full dropdown menu is not needed.
  setButton = CreateFrame("Button", nil, frame, "UIPanelButtonTemplate")
  setButton:SetSize(200, 22)
  setButton:SetPoint("TOPLEFT", 16, -52)
  setButton:SetScript("OnClick", function() Popover:CycleSet() end)

  scroll = CreateFrame("ScrollFrame", nil, frame, "UIPanelScrollFrameTemplate")
  scroll:SetPoint("TOPLEFT", 14, -78)
  scroll:SetPoint("BOTTOMRIGHT", -30, 14)
  content = CreateFrame("Frame", nil, scroll)
  content:SetSize(WIDTH - 50, 1)
  scroll:SetScrollChild(content)

  frame:SetScript("OnShow", function()
    Popover:Reposition()
    Popover:Refresh()
  end)

  -- Escape closes it
  local registered = false
  for _, n in ipairs(UISpecialFrames) do
    if n == FRAME_NAME then registered = true end
  end
  if not registered then table.insert(UISpecialFrames, FRAME_NAME) end
end

function Popover:GetLines() return pool, used end
function Popover:GetSetButton() return setButton end

-- Activate the set after the current one in the view model's `sets` order.
function Popover:CycleSet()
  local sets = ns.ViewModel:Get().sets
  for i, s in ipairs(sets) do
    if s.active then
      local nxt = sets[i % #sets + 1]
      if nxt and not nxt.active then ns.Sets:SetActive(nxt.id) end
      return
    end
  end
end

function Popover:Toggle()
  if not frame then create() end
  if frame:IsShown() then frame:Hide() else frame:Show() end
end

ns.Events:On("FULLBUFF_STATE", function()
  if frame and frame:IsShown() then Popover:Refresh() end
end)
ns.Events:On("FULLBUFF_SET", function()
  if frame and frame:IsShown() then Popover:Refresh() end
end)
ns.Events:On("FULLBUFF_BAGS", function()
  if frame and frame:IsShown() then Popover:Refresh() end
end)
ns.Events:On("FULLBUFF_LANGUAGE", function()
  if frame and frame:IsShown() then Popover:Refresh() end
end)
