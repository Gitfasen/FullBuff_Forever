local _, ns = ...

-- Set selector: a modern dropdown (DropdownButton + WowStyle1DropdownTemplate) listing
-- ns.Sets:List(); picking an entry activates that set. Create() returns nil when the
-- template or SetupMenu is unavailable, so callers keep their cycling-button fallback.
ns.UI = ns.UI or {}
local SetDropdown = {}
ns.UI.SetDropdown = SetDropdown

local function setName(id)
  local s = ns.Sets:Get(id)
  return s and s.name or tostring(id)
end

local function generate(_, root)
  for _, id in ipairs(ns.Sets:List()) do
    root:CreateRadio(setName(id),
      function(sid) return sid == (ns.Sets:Active()) end,
      function(sid) ns.Sets:SetActive(sid) end,
      id)
  end
end

function SetDropdown.Create(parent, width)
  local ok, dd = pcall(CreateFrame, "DropdownButton", nil, parent, "WowStyle1DropdownTemplate")
  if not ok or not dd then return nil end
  if type(dd.SetupMenu) ~= "function" then return nil end
  if width and dd.SetWidth then dd:SetWidth(width) end
  if not pcall(dd.SetupMenu, dd, generate) then return nil end
  return dd
end

-- Re-run the menu generator so the shown text follows the active set / language.
function SetDropdown.Refresh(dd)
  if dd and dd.GenerateMenu then pcall(dd.GenerateMenu, dd) end
end
