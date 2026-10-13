local ADDON, ns = ...
ns.name = ADDON
ns.UI = ns.UI or {}
-- Inline markers shared by the popover and the options Sets editor.
ns.UI.MARK_STAR = "|TInterface\\TargetingFrame\\UI-RaidTargetingIcon_1:0|t" -- recommended
ns.UI.MARK_CHECK = "|TInterface\\RaidFrame\\ReadyCheck-Ready:0|t" -- already on the character
ns.IsForever = (WOW_PROJECT_ID == (WOW_PROJECT_CAMELOT or 18))

-- AddonCompartmentFunc named in the TOC: right click opens options, else toggle.
function FullBuff_OnCompartmentClick(_, button)
  if button == "RightButton" then
    if ns.UI.OpenOptions then ns.UI.OpenOptions() end
  elseif ns.UI.Toggle then
    ns.UI.Toggle()
  end
end
