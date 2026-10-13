local ADDON, ns = ...
ns.name = ADDON
ns.UI = ns.UI or {}
ns.IsForever = (WOW_PROJECT_ID == (WOW_PROJECT_CAMELOT or 18))

-- AddonCompartmentFunc named in the TOC: right click opens options, else toggle.
function FullBuff_OnCompartmentClick(_, button)
  if button == "RightButton" then
    if ns.UI.OpenOptions then ns.UI.OpenOptions() end
  elseif ns.UI.Toggle then
    ns.UI.Toggle()
  end
end
