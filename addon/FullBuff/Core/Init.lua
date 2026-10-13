local ADDON, ns = ...
ns.name = ADDON
ns.UI = ns.UI or {}
ns.IsForever = (WOW_PROJECT_ID == (WOW_PROJECT_CAMELOT or 18))

-- AddonCompartmentFunc named in the TOC.
function FullBuff_OnCompartmentClick(...)
  if ns.UI.Toggle then
    ns.UI.Toggle(...)
  end
end
