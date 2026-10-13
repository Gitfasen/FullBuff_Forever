local _, ns = ...

-- Popover: stat table + collapsible buff sections, anchored to the launcher.
ns.UI = ns.UI or {}
local Popover = {}
ns.UI.Popover = Popover
ns.UI.Toggle = function() Popover:Toggle() end

local FRAME_NAME = "FullBuffPopover"
local WIDTH, HEIGHT = 340, 440
local STAT_H, SECTION_H, ITEM_H = 16, 22, 32

local STAR = "|TInterface\\TargetingFrame\\UI-RaidTargetingIcon_1:0|t" -- raid-target star: exists in every client
local CHECK = "|TInterface\\RaidFrame\\ReadyCheck-Ready:0|t" -- ready-check tick: already on the character
local frame, scroll, content, staleText, titleText, headerText, onlyMissing, onlyMissingLabel
local pool, used = {}, 0

local function db()
  ns.DB = ns.DB or {}
  return ns.DB
end

local COLORS = {
  ACTIVE = { 0.25, 1, 0.25 }, -- green: already have it
  CAN_ADD = { 1, 1, 1 },
  UNAVAILABLE = { 0.5, 0.5, 0.5 },
  RECOMMENDED = { 1, 0.82, 0 },
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
    if self.fbKind ~= "item" then return end
    GameTooltip:SetOwner(self, "ANCHOR_RIGHT")
    GameTooltip:AddLine(self.fbName or "")
    if self.fbRecommended then GameTooltip:AddLine(ns.L.RECOMMENDED, 1, 0.82, 0) end
    GameTooltip:Show()
  end)
  b:SetScript("OnLeave", function() GameTooltip:Hide() end)
  b:SetScript("OnClick", function(self)
    if self.fbKind == "section" then
      local d = db()
      d.collapsed = d.collapsed or {}
      d.collapsed[self.fbCat] = (not d.collapsed[self.fbCat]) or nil
      ns.ViewModel:Invalidate()
      Popover:Refresh()
    elseif self.fbKind == "item" then
      ns.UI.OpenDetail(self.fbId)
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
  b.fbKind, b.fbId, b.fbCat, b.fbName, b.fbRecommended = kind, nil, nil, nil, nil
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
  onlyMissingLabel:SetText(L.SHOW_ONLY_MISSING)
  onlyMissing:SetChecked(db().onlyMissing and true or false)
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

  for _, sec in ipairs(vm.sections) do
    b, y = takeLine(y, "section", SECTION_H)
    b.fbCat = sec.cat
    b.bg:SetColorTexture(1, 1, 1, 0.08)
    b.name:SetPoint("LEFT", 6, 0)
    b.name:SetText(string.format("%s %s (%d/%d)", sec.collapsed and "[+]" or "[-]", sec.title, sec.activeCount, sec.total))
    if not sec.collapsed then
      for _, it in ipairs(sec.items) do
        b, y = takeLine(y, "item", ITEM_H)
        b.fbId, b.fbName, b.fbRecommended = it.id, it.name, it.recommended
        b.icon:SetTexture(it.icon)
        b.icon:Show()
        b.name:SetPoint("TOPLEFT", 34, -4)
        b.name:SetPoint("TOPRIGHT", -4, -4)
        b.sub:SetPoint("BOTTOMLEFT", 34, 4)
        b.sub:SetPoint("BOTTOMRIGHT", -4, 4)
        b.name:SetWordWrap(false)
        b.sub:SetWordWrap(false)
        b:SetAlpha(1)
        local mark = ""
        if it.status == "ACTIVE" then
          mark = CHECK .. " "
        elseif it.recommended then
          mark = STAR .. " "
        end
        b.name:SetText(mark .. it.name)
        b.sub:SetText(it.valueText)
        local c = COLORS[it.status] or COLORS.CAN_ADD
        if it.status == "CAN_ADD" and it.recommended then c = COLORS.RECOMMENDED end
        b.name:SetTextColor(c[1], c[2], c[3])
      end
    end
  end
  if #vm.sections == 0 then
    b, y = takeLine(y, "section", SECTION_H)
    b.name:SetPoint("LEFT", 6, 0)
    b.name:SetText(L.NO_BUFFS)
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

  onlyMissing = CreateFrame("CheckButton", nil, frame, "UICheckButtonTemplate")
  onlyMissing:SetPoint("TOPLEFT", 12, -50)
  onlyMissing:SetSize(24, 24)
  onlyMissingLabel = frame:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
  onlyMissingLabel:SetPoint("LEFT", onlyMissing, "RIGHT", 2, 0)
  onlyMissing:SetScript("OnClick", function(self)
    db().onlyMissing = self:GetChecked() and true or false
    ns.ViewModel:Invalidate()
    Popover:Refresh()
    if ns.UI.Launcher then ns.UI.Launcher:Refresh() end
  end)

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

function Popover:Toggle()
  if not frame then create() end
  if frame:IsShown() then frame:Hide() else frame:Show() end
end

ns.Events:On("FULLBUFF_STATE", function()
  if frame and frame:IsShown() then Popover:Refresh() end
end)
ns.Events:On("FULLBUFF_LANGUAGE", function()
  if frame and frame:IsShown() then Popover:Refresh() end
end)
