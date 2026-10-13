local _, ns = ...

-- Game events arrive through one hidden frame; internal events are named
-- FULLBUFF_* and are never registered with the client.
local Events = { handlers = {}, pending = {} }
ns.Events = Events

local frame = CreateFrame("Frame")
frame:Hide()
Events.frame = frame

function Events:Fire(event, ...)
  local list = self.handlers[event]
  if not list then return end
  -- Each handler is isolated: an error is reported and the next one still runs.
  for i = 1, #list do
    local ok, err = pcall(list[i], ...)
    if not ok then
      geterrorhandler()(err)
    end
  end
end

function Events:On(event, fn)
  local list = self.handlers[event]
  if not list then
    list = {}
    self.handlers[event] = list
    if not event:find("^FULLBUFF_") then
      frame:RegisterEvent(event)
    end
  end
  list[#list + 1] = fn
end

frame:SetScript("OnEvent", function(_, event, ...)
  Events:Fire(event, ...)
end)

-- Coalesce repeated calls with the same key; the last fn wins.
function Events:Debounce(key, seconds, fn)
  local had = self.pending[key] ~= nil
  self.pending[key] = fn
  if had then return end
  C_Timer.After(seconds, function()
    local f = self.pending[key]
    self.pending[key] = nil
    if f then f() end
  end)
end
