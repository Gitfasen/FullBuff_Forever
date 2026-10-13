local ADDON, ns = ...

ns.Defaults = {
  DB = {
    lang = "en",
    scale = 1,
    onlyMissing = false,
    allStats = false,
    spec = "auto",
    categories = {},
    weights = {},
  },
  Char = {
    pins = {},
  },
}

local function applyDefaults(dst, src)
  for k, v in pairs(src) do
    if type(v) == "table" then
      if type(dst[k]) ~= "table" then dst[k] = {} end
      applyDefaults(dst[k], v)
    elseif dst[k] == nil then
      dst[k] = v
    end
  end
  return dst
end

ns.Events:On("ADDON_LOADED", function(name)
  if name ~= ADDON then return end
  FullBuffDB = applyDefaults(FullBuffDB or {}, ns.Defaults.DB)
  FullBuffCharDB = applyDefaults(FullBuffCharDB or {}, ns.Defaults.Char)
  ns.DB = FullBuffDB
  ns.CharDB = FullBuffCharDB
  ns.SetLanguage(ns.DB.lang)
  ns.Events:Fire("FULLBUFF_LOADED")
end)
