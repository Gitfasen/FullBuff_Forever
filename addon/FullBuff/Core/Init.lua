local ADDON, ns = ...
ns.name = ADDON
ns.UI = ns.UI or {}

-- AddonCompartmentFunc named in the TOC.
function FullBuff_OnCompartmentClick(...)
  if ns.UI.Toggle then
    ns.UI.Toggle(...)
  end
end
