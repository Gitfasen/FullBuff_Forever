-- Minimal WoW API mock. Everything here is a plain global and can be
-- replaced from Python (addon(mocks={...})) or from Lua before use.

-- Lua helpers the game provides
wipe = wipe or function(t) for k in pairs(t) do t[k] = nil end return t end
tinsert = tinsert or table.insert
tremove = tremove or table.remove

-- Frames and events
local frames = {}
function CreateFrame(frameType, name, parent)
  local f = { __type = frameType, __name = name, __events = {}, __scripts = {}, __shown = true }
  function f:RegisterEvent(e) self.__events[e] = true end
  function f:UnregisterEvent(e) self.__events[e] = nil end
  function f:UnregisterAllEvents() self.__events = {} end
  function f:IsEventRegistered(e) return self.__events[e] == true end
  function f:SetScript(n, fn) self.__scripts[n] = fn end
  function f:GetScript(n) return self.__scripts[n] end
  function f:HookScript(n, fn) self.__scripts[n] = fn end
  function f:Show() self.__shown = true end
  function f:Hide() self.__shown = false end
  function f:IsShown() return self.__shown end
  function f:SetParent(p) end
  frames[#frames + 1] = f
  return f
end

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
UnitStat = function(i) return 100, 100, 0, 0 end

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
