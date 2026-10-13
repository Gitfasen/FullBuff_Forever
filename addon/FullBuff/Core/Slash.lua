local _, ns = ...

-- /fullbuff [options | lang en|uk | debug | reset]
SLASH_FULLBUFF1 = "/fullbuff"

local function say(text)
  if DEFAULT_CHAT_FRAME then DEFAULT_CHAT_FRAME:AddMessage(text) end
end

local function usage()
  local L = ns.L
  say("FullBuff:")
  for _, k in ipairs({ "SLASH_USAGE_TOGGLE", "SLASH_USAGE_OPTIONS", "SLASH_USAGE_LANG", "SLASH_USAGE_DEBUG", "SLASH_USAGE_RESET" }) do
    say(L[k])
  end
end

local function debug()
  local L = ns.L
  local state = ns.PlayerState:Get()
  say("FullBuff: " .. string.format(L.DEBUG_STALE, state.stale and L.DEBUG_YES or L.DEBUG_NO))
  local ids = {}
  for id in pairs(state.unknownAuras or {}) do ids[#ids + 1] = id end
  table.sort(ids)
  if #ids == 0 then
    say(L.DEBUG_NONE)
    return
  end
  say(string.format(L.DEBUG_UNKNOWN_HEADER, #ids))
  for _, id in ipairs(ids) do
    say(string.format("  %d  %s", id, tostring(state.unknownAuras[id])))
  end
end

local function handler(msg)
  local cmd, rest = (msg or ""):match("^%s*(%S*)%s*(.-)%s*$")
  cmd = (cmd or ""):lower()
  rest = (rest or ""):lower()
  if cmd == "" then
    if ns.UI.Toggle then ns.UI.Toggle() end
  elseif cmd == "options" or cmd == "config" then
    if ns.UI.OpenOptions then ns.UI.OpenOptions() end
  elseif cmd == "lang" then
    if (rest == "en" or rest == "uk") and ns.SetLanguage(rest) then
      for _, l in ipairs(ns.Options.LANGS) do
        if l.code == rest then say("FullBuff: " .. string.format(ns.L.SLASH_LANG_SET, l.label)) end
      end
    else
      say(ns.L.SLASH_USAGE_LANG)
    end
  elseif cmd == "debug" then
    debug()
  elseif cmd == "reset" then
    ns.Options:ResetLayout()
    say("FullBuff: " .. ns.L.SLASH_RESET_DONE)
  else
    usage()
  end
end

SlashCmdList = SlashCmdList or {}
SlashCmdList["FULLBUFF"] = handler
