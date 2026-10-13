local _, ns = ...

ns.Locales = { enUS = {}, ukUA = {} }
local CODES = { en = "enUS", uk = "ukUA" }
local current = "enUS"

-- Missing keys fall back to English, then to the key itself.
ns.L = setmetatable({}, {
  __index = function(_, key)
    local cur = ns.Locales[current]
    local v = cur and cur[key]
    if v == nil then v = ns.Locales.enUS[key] end
    if v == nil then v = key end
    return v
  end,
})

function ns.SetLanguage(code)
  local loc = CODES[code]
  if not loc then return false end
  current = loc
  ns.lang = code
  if ns.DB then ns.DB.lang = code end
  if ns.Events then ns.Events:Fire("FULLBUFF_LANGUAGE", code) end
  return true
end

function ns.GetLanguage()
  return ns.lang or "en"
end
