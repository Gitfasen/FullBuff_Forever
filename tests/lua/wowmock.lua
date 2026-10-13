-- Minimal WoW API mock. Everything here is a plain global and can be
-- replaced from Python (addon(mocks={...})) or from Lua before use.

-- Lua helpers the game provides
wipe = wipe or function(t) for k in pairs(t) do t[k] = nil end return t end
tinsert = tinsert or table.insert
tremove = tremove or table.remove

-- Frames and events
local frames = {}
-- Permissive frame stub: known methods below are real, every other method is a
-- no-op (Get...Texture/FontString/Region style getters return a stub).
local noop = function() end
local newFrame
local frameMethods = {}
local frameMT = {
  __index = function(t, k)
    local m = frameMethods[k]
    if m then return m end
    if type(k) == "string" and k:match("^%u") then
      if k:match("^Get.*Texture$") or k:match("^Get.*FontString$") or k:match("^Create") then
        return function(self) return newFrame("Texture") end
      end
      return noop
    end
  end,
}
function frameMethods:RegisterEvent(e) self.__events[e] = true end
function frameMethods:UnregisterEvent(e) self.__events[e] = nil end
function frameMethods:UnregisterAllEvents() self.__events = {} end
function frameMethods:IsEventRegistered(e) return self.__events[e] == true end
function frameMethods:SetScript(n, fn) self.__scripts[n] = fn end
function frameMethods:GetScript(n) return self.__scripts[n] end
function frameMethods:HookScript(n, fn) self.__scripts[n] = fn end
function frameMethods:Show()
  local was = self.__shown
  self.__shown = true
  if not was and self.__scripts.OnShow then self.__scripts.OnShow(self) end
end
function frameMethods:Hide()
  local was = self.__shown
  self.__shown = false
  if was and self.__scripts.OnHide then self.__scripts.OnHide(self) end
end
function frameMethods:SetShown(v) if v then self:Show() else self:Hide() end end
function frameMethods:IsShown() return self.__shown end
function frameMethods:IsVisible() return self.__shown end
function frameMethods:SetParent(p) end
function frameMethods:GetName() return self.__name end
function frameMethods:GetObjectType() return self.__type end
function frameMethods:SetPoint(...) self.__point = { ... } end
function frameMethods:GetPoint() local p = self.__point or {} return p[1] or "CENTER", p[2], p[3] or p[1] or "CENTER", p[4] or 0, p[5] or 0 end
function frameMethods:ClearAllPoints() self.__point = nil end
function frameMethods:SetSize(w, h) self.__w, self.__h = w, h end
function frameMethods:SetWidth(w) self.__w = w end
function frameMethods:SetHeight(h) self.__h = h end
function frameMethods:GetWidth() return self.__w or 100 end
function frameMethods:GetHeight() return self.__h or 100 end
function frameMethods:GetCenter() return 500, 400 end
function frameMethods:GetLeft() return 450 end
function frameMethods:GetRight() return 550 end
function frameMethods:GetTop() return 420 end
function frameMethods:GetBottom() return 380 end
function frameMethods:GetEffectiveScale() return 1 end
function frameMethods:GetScale() return 1 end
function frameMethods:SetText(t) self.__text = t end
function frameMethods:SetTexture(t) self.__texture = t end
function frameMethods:GetText() return self.__text end
function frameMethods:SetChecked(v) self.__checked = v and true or false end
function frameMethods:GetChecked() return self.__checked end
function frameMethods:GetStringWidth() return 50 end
function frameMethods:GetVerticalScroll() return 0 end
function frameMethods:GetScrollChild() return self.__child end
function frameMethods:SetScrollChild(c) self.__child = c end

newFrame = function(frameType, name, parent)
  local f = setmetatable({ __type = frameType, __name = name, __events = {}, __scripts = {}, __shown = true }, frameMT)
  frames[#frames + 1] = f
  return f
end
function CreateFrame(frameType, name, parent, template)
  local f = newFrame(frameType, name, parent)
  if name then _G[name] = f end
  return f
end
UIParent = newFrame("Frame", "UIParent")
UISpecialFrames = {}
GameTooltip = newFrame("GameTooltip", "GameTooltip")
GameTooltip.__shown = false
GameTooltip.__lines = {}
GameTooltip.SetOwner = function(self, owner) self.__owner = owner; self.__lines = {} end
GameTooltip.GetOwner = function(self) return self.__owner end
GameTooltip.AddLine = function(self, t) self.__lines[#self.__lines + 1] = tostring(t) end
GameTooltip.AddDoubleLine = function(self, a, b) self.__lines[#self.__lines + 1] = tostring(a) .. " | " .. tostring(b) end
GetScreenWidth = function() return 1920 end
GetScreenHeight = function() return 1080 end
GetCursorPosition = function() return 0, 0 end

-- Deliver a game event to every frame registered for it.
function __fire_event(event, ...)
  local snapshot = {}
  for i, f in ipairs(frames) do snapshot[i] = f end
  for _, f in ipairs(snapshot) do
    if f.__events[event] and f.__scripts.OnEvent then
      f.__scripts.OnEvent(f, event, ...)
    end
  end
end

-- Timers on a virtual clock. Ordered by (due, seq) so equal delays are FIFO.
-- __advance(sec) runs due timers, including ones queued by callbacks that fall
-- inside the window. A throwing callback does not stop the others: the rest
-- run, then the first error is re-raised.
local now, seq, timers = 0, 0, {}
C_Timer = {
  After = function(seconds, fn)
    seq = seq + 1
    timers[#timers + 1] = { due = now + (seconds or 0), seq = seq, fn = fn }
  end,
}
local function next_timer(limit)
  local best, bi
  for i, t in ipairs(timers) do
    if (limit == nil or t.due <= limit) and
       (not best or t.due < best.due or (t.due == best.due and t.seq < best.seq)) then
      best, bi = t, i
    end
  end
  return best, bi
end
local function run_until(limit, errs)
  local count = 0
  while true do
    local t, i = next_timer(limit)
    if not t then break end
    count = count + 1
    if count > 10000 then error("timers: runaway") end
    table.remove(timers, i)
    if t.due > now then now = t.due end
    local ok, err = pcall(t.fn)
    if not ok then errs[#errs + 1] = err end
  end
end
function __advance(seconds)
  local errs = {}
  local target = now + seconds
  run_until(target, errs)
  if target > now then now = target end
  if #errs > 0 then error(errs[1], 0) end
end
function __flush_timers()
  local errs, guard = {}, 0
  while #timers > 0 do
    guard = guard + 1
    if guard > 1000 then error("__flush_timers: runaway timers") end
    local t = next_timer()
    run_until(t.due, errs)
  end
  if #errs > 0 then error(errs[1], 0) end
end
function __pending_timers() return #timers end
GetTime = function() return now end

-- Error handler capture: geterrorhandler()(msg) records into __errors
__errors = {}
local handler = function(msg) __errors[#__errors + 1] = tostring(msg) end
geterrorhandler = function() return handler end
seterrorhandler = function(fn) handler = fn end

WOW_PROJECT_ID = 18

-- State queries
InCombatLockdown = function() return false end
issecretvalue = function(v) return false end

-- Player
UnitClass = function(unit) return "Warrior", "WARRIOR", 1 end
UnitLevel = function(unit) return 60 end
GetSpecialization = function() return 1 end
GetSpecializationInfo = function(i) return 71, "Arms", "", "", "DAMAGER" end
UnitStat = function(unit, i) return 100, 100, 0, 0 end

-- Auras and weapon enchants
C_UnitAuras = {
  GetAuraDataByIndex = function(unit, index, filter) return nil end,
}
GetWeaponEnchantInfo = function() return false, 0, 0, nil, false, 0, 0, nil end

-- Stat getters
UnitAttackPower = function() return 0, 0, 0 end
UnitRangedAttackPower = function() return 0, 0, 0 end
GetSpellBonusDamage = function(school) return 0 end
GetSpellBonusHealing = function() return 0 end
GetCritChance = function() return 0 end
GetRangedCritChance = function() return 0 end
GetSpellCritChance = function(school) return 0 end
GetCombatRatingBonus = function(rating) return 0 end
GetManaRegen = function() return 0, 0 end
UnitArmor = function(unit) return 0, 0, 0, 0, 0 end
UnitHealthMax = function(unit) return 1000 end
UnitPowerMax = function(unit, power) return 1000 end
