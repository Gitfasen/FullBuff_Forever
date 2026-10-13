local _, ns = ...

-- Round launcher button: badge = number of recommended missing buffs.
ns.UI = ns.UI or {}
ns.UI.OpenDetail = ns.UI.OpenDetail or function() end -- placeholder, Task 14 replaces it

local Launcher = {}
ns.UI.Launcher = Launcher

local SIZE = 36
local ICON = "Interface\Icons\Spell_Holy_WordFortitude"
local DEFAULT_POS = { point = "TOPRIGHT", relPoint = "TOPRIGHT", x = -220, y = -220 }
local button, badgeText, icon

local function db()
  ns.DB = ns.DB or {}
  return ns.DB
end

function Launcher:GetFrame()
  return button
end

function Launcher:ApplyPosition()
  if not button then return end
  local pos = db().launcher or DEFAULT_POS
  button:ClearAllPoints()
  button:SetPoint(pos.point or "CENTER", UIParent, pos.relPoint or pos.point or "CENTER", pos.x or 0, pos.y or 0)
  button:SetScale(db().scale or 1)
end

local function savePosition()
  local point, _, relPoint, x, y = button:GetPoint()
  db().launcher = { point = point, relPoint = relPoint, x = x, y = y }
end

function Launcher:ResetPosition()
  db().launcher = nil
  self:ApplyPosition()
end

local function showTooltip(self)
  local vm = ns.ViewModel:Build()
  local L = ns.L
  GameTooltip:SetOwner(self, "ANCHOR_LEFT")
  GameTooltip:AddLine(L.TITLE)
  GameTooltip:AddDoubleLine(L.TOOLTIP_PROGRESS, string.format("%d%%", vm.tooltip.progress + 0.5), 1, 1, 1, 1, 1, 1)
  if #vm.tooltip.missing > 0 then
    GameTooltip:AddLine(L.TOOLTIP_MISSING .. ":", 1, 0.82, 0)
    for i, name in ipairs(vm.tooltip.missing) do
      if i > 10 then GameTooltip:AddLine("...", 0.7, 0.7, 0.7) break end
      GameTooltip:AddLine(name, 1, 1, 1)
    end
  else
    GameTooltip:AddLine(L.ALL_BUFFED, 0.4, 1, 0.4)
  end
  GameTooltip:AddLine(L.HINT_TOGGLE, 0.7, 0.7, 0.7)
  GameTooltip:AddLine(L.HINT_OPTIONS, 0.7, 0.7, 0.7)
  GameTooltip:AddLine(L.HINT_DRAG, 0.7, 0.7, 0.7)
  GameTooltip:Show()
end

function Launcher:Refresh()
  if not button then return end
  local vm = ns.ViewModel:Build()
  badgeText:SetText(vm.badge > 0 and tostring(vm.badge) or "")
  if GameTooltip:IsShown() and GameTooltip:GetOwner() == button then showTooltip(button) end
end

function Launcher:Create()
  if button then return button end
  button = CreateFrame("Button", "FullBuffLauncher", UIParent)
  button:SetSize(SIZE, SIZE)
  button:SetFrameStrata("MEDIUM")
  button:SetMovable(true)
  button:SetClampedToScreen(true)
  button:RegisterForDrag("LeftButton")
  button:RegisterForClicks("LeftButtonUp", "RightButtonUp")

  icon = button:CreateTexture(nil, "ARTWORK")
  icon:SetPoint("TOPLEFT", 4, -4)
  icon:SetPoint("BOTTOMRIGHT", -4, 4)
  icon:SetTexture(ICON)
  icon:SetMask("Interface\CharacterFrame\TempPortraitAlphaMask")

  local border = button:CreateTexture(nil, "OVERLAY")
  border:SetAllPoints()
  border:SetTexture("Interface\Minimap\MiniMap-TrackingBorder")
  border:SetTexCoord(0, 0.6, 0, 0.6)
  button:SetHighlightTexture("Interface\Minimap\UI-Minimap-ZoomButton-Highlight")

  badgeText = button:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
  badgeText:SetPoint("BOTTOMRIGHT", 2, -2)
  badgeText:SetTextColor(1, 0.3, 0.3)

  button:SetScript("OnDragStart", function(self)
    if InCombatLockdown() then return end -- never move during combat
    self:StartMoving()
    self.fbDragging = true
  end)
  button:SetScript("OnDragStop", function(self)
    if not self.fbDragging then return end
    self.fbDragging = false
    self:StopMovingOrSizing()
    savePosition()
  end)
  button:SetScript("OnClick", function(_, mouse)
    if mouse == "RightButton" then
      if ns.UI.OpenOptions then ns.UI.OpenOptions() end
    else
      ns.UI.Popover:Toggle()
    end
  end)
  button:SetScript("OnEnter", showTooltip)
  button:SetScript("OnLeave", function() GameTooltip:Hide() end)

  self:ApplyPosition()
  self:Refresh()
  return button
end

ns.Events:On("FULLBUFF_LOADED", function() Launcher:Create() end)
ns.Events:On("FULLBUFF_STATE", function() Launcher:Refresh() end)
ns.Events:On("FULLBUFF_LANGUAGE", function() Launcher:Refresh() end)
