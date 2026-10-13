local _, ns = ...

local Compat = {}
ns.Compat = Compat

-- issecretvalue does not exist on every client.
function Compat.IsSecret(v)
  if type(issecretvalue) == "function" then
    return issecretvalue(v) and true or false
  end
  return false
end

function Compat.CanReadAuras()
  return not InCombatLockdown()
end
