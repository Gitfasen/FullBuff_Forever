local _, ns = ...

-- Options: logic (ns.Options setters) plus the Settings canvas panel.
-- Every setter that changes what the engine computes or what the popover shows
-- ends in recompute(): PlayerState:Refresh() fires FULLBUFF_STATE, which the
-- popover and launcher already listen to.
-- Option keys: ns.CharDB.specOverride, ns.DB.weightOverrides[class][spec][stat],
-- ns.DB.showAllStats, ns.DB.scale, ns.DB.launcher, ns.DB.lang.
-- The Sets editor edits the ACTIVE set (ns.Sets:Active()); every edit goes through
-- ns.Sets, whose FULLBUFF_SET event refreshes this panel, the popover and the view model.
ns.UI = ns.UI or {}
local Options = {}
ns.Options = Options

local SCALE_MIN, SCALE_MAX = 0.5, 2.0
-- Endonyms: shown the same in every UI language.
local LANGS = { { code = "en", label = "English" }, { code = "uk", label = "Українська" } }
Options.LANGS = LANGS

local function db()
  ns.DB = ns.DB or {}
  return ns.DB
end

local function charDb()
  ns.CharDB = ns.CharDB or {}
  return ns.CharDB
end

local function recompute()
  ns.PlayerState:Refresh(true)
end

function Options:SetSpecOverride(spec)
  if spec ~= nil then
    spec = tonumber(spec)
    if spec ~= 1 and spec ~= 2 and spec ~= 3 then spec = nil end
  end
  charDb().specOverride = spec
  recompute()
end

-- SetWeight(stat, value): nil or a non-number clears the override for the
-- current class and spec.
function Options:SetWeight(stat, value)
  local state = ns.PlayerState:Get()
  local class, spec = state.class, state.spec or 1
  local d = db()
  value = tonumber(value)
  if value and (value ~= value or value == math.huge or value == -math.huge) then
    Options:Refresh() -- reject non-finite input, show the stored value again
    return
  end
  if value == nil then
    local t = d.weightOverrides and d.weightOverrides[class]
    t = t and t[spec]
    if t then t[stat] = nil end
  else
    d.weightOverrides = d.weightOverrides or {}
    d.weightOverrides[class] = d.weightOverrides[class] or {}
    d.weightOverrides[class][spec] = d.weightOverrides[class][spec] or {}
    d.weightOverrides[class][spec][stat] = value
  end
  recompute()
  Options:Refresh()
end

function Options:SetShowAllStats(on)
  db().showAllStats = on and true or false
  recompute()
end

function Options:SetScale(scale)
  scale = tonumber(scale) or 1
  scale = math.max(SCALE_MIN, math.min(SCALE_MAX, scale))
  db().scale = scale
  if ns.UI.Launcher then ns.UI.Launcher:ApplyPosition() end
end

function Options:ResetPosition()
  if ns.UI.Launcher then ns.UI.Launcher:ResetPosition() else db().launcher = nil end
end

-- /fullbuff reset: the launcher position only.
function Options:ResetLayout()
  self:ResetPosition()
end

-- Stats to offer weight boxes for: base weights of the current class/spec plus
-- any existing override.
function Options:RelevantStats()
  local state = ns.PlayerState:Get()
  local class, spec = state.class, state.spec or 1
  local seen, out = {}, {}
  local base = ns.Weights and ns.Weights[class]
  base = base and base[spec]
  local ov = db().weightOverrides
  ov = ov and ov[class]
  ov = ov and ov[spec]
  for _, src in ipairs({ base or {}, ov or {} }) do
    for k in pairs(src) do
      if not seen[k] then seen[k] = true; out[#out + 1] = k end
    end
  end
  local rank = {}
  for i, k in ipairs(ns.Scoring and ns.Scoring.CANONICAL or {}) do rank[k] = i end
  table.sort(out, function(a, b)
    local ra, rb = rank[a] or 99, rank[b] or 99
    if ra ~= rb then return ra < rb end
    return a < b
  end)
  return out
end

------------------------------------------------------------------ models

local function slotName(slot)
  local s = ns.Slots and ns.Slots[slot]
  local n = s and s.name
  if n then
    local lang = ns.GetLanguage and ns.GetLanguage() or "en"
    return n[lang] or n.en or tostring(slot)
  end
  return tostring(slot)
end

local function slotOrder(slot)
  local s = ns.Slots and ns.Slots[slot]
  return s and s.order or math.huge
end

local function isAvailable(e)
  return e.status == "ACTIVE" or e.status == "CAN_ADD"
end

-- Every catalog entry (all categories), recommendations marked.
local function entries()
  local state = ns.PlayerState:Get()
  local catalog = ns.Catalog:Build(state)
  ns.Scoring:MarkRecommended(catalog, state)
  local list = {}
  for key, l in pairs(catalog) do
    if key ~= "order" and type(l) == "table" then
      for _, e in ipairs(l) do list[#list + 1] = e end
    end
  end
  return list
end

local function buffName(id)
  local buff = ns.Buffs and ns.Buffs[id]
  return buff and buff.name or ("#" .. tostring(id))
end

-- SlotModel(setId) -> { {slot, name, picked, options = {{buffId, name, valueText,
-- recommended, active, unavailable}}} }. Slots follow their `order`; slots with no
-- obtainable option are hidden unless the set picks a buff there (that pick stays,
-- marked unavailable). Options: recommended first, then by name. Picks are read
-- through ns.Sets:Resolve (filed under their buff's current slot).
function Options:SlotModel(setId)
  local set = ns.Sets:Get(setId)
  local picks = ns.Sets:Resolve(set)
  local bySlot = {}
  for _, e in ipairs(entries()) do
    if e.excl and not e.burst and isAvailable(e) then
      local g = bySlot[e.excl]
      if not g then g = {}; bySlot[e.excl] = g end
      g[#g + 1] = {
        buffId = e.id, name = e.name or buffName(e.id), valueText = ns.ViewModel.FormatFx(e.fx),
        recommended = e.recommended == true, active = e.status == "ACTIVE", unavailable = false,
      }
    end
  end
  for slot, buffId in pairs(picks) do
    if buffId then
      local g = bySlot[slot]
      if not g then g = {}; bySlot[slot] = g end
      local found = false
      for _, o in ipairs(g) do
        if o.buffId == buffId then found = true end
      end
      if not found then
        g[#g + 1] = {
          buffId = buffId, name = buffName(buffId), valueText = "",
          recommended = false, active = false, unavailable = true,
        }
      end
    end
  end
  local out = {}
  for slot, options in pairs(bySlot) do
    table.sort(options, function(a, b)
      if a.recommended ~= b.recommended then return a.recommended end
      if a.name ~= b.name then return a.name < b.name end
      return a.buffId < b.buffId
    end)
    out[#out + 1] = { slot = slot, name = slotName(slot), options = options, picked = picks[slot] }
  end
  table.sort(out, function(a, b)
    local oa, ob = slotOrder(a.slot), slotOrder(b.slot)
    if oa ~= ob then return oa < ob end
    if a.name ~= b.name then return a.name < b.name end
    return tostring(a.slot) < tostring(b.slot)
  end)
  return out
end

-- BurstModel(setId) -> { {buffId, name, tracked, bagCount, unavailable} }: tracked buffs first in
-- the set's order (also ones that are no longer obtainable, so they can be removed),
-- then every other obtainable burst buff by name.
function Options:BurstModel(setId)
  local set = ns.Sets:Get(setId)
  local available = {}
  for _, e in ipairs(entries()) do
    if e.burst and isAvailable(e) then available[e.id] = e end
  end
  local function count(id)
    local buff = ns.Buffs and ns.Buffs[id]
    return buff and ns.Bags:CountBuff(buff) or 0
  end
  local out, tracked = {}, {}
  for _, id in ipairs(set and set.burst or {}) do
    tracked[id] = true
    local e = available[id]
    out[#out + 1] = {
      buffId = id, name = e and e.name or buffName(id), tracked = true, bagCount = count(id),
      unavailable = e == nil,
    }
  end
  local rest = {}
  for id, e in pairs(available) do
    if not tracked[id] then
      rest[#rest + 1] = { buffId = id, name = e.name or buffName(id), tracked = false, bagCount = count(id) }
    end
  end
  table.sort(rest, function(a, b)
    if a.name ~= b.name then return a.name < b.name end
    return a.buffId < b.buffId
  end)
  for _, r in ipairs(rest) do out[#out + 1] = r end
  return out
end

-- The tree name of specialization i (specialization / talent tree name), else "Specialization tree i".
function Options:SpecLabel(i)
  local name
  if GetSpecializationInfo then
    local ok, _, n = pcall(GetSpecializationInfo, i)
    if ok and type(n) == "string" and n ~= "" then name = n end
  end
  if not name and GetTalentTabInfo then
    local ok, n = pcall(GetTalentTabInfo, i)
    if ok and type(n) == "string" and n ~= "" then name = n end
  end
  return name or string.format(ns.L.OPT_SPEC_FMT, i)
end

------------------------------------------------------------------ set actions
-- All edits go through ns.Sets (FULLBUFF_SET), on the ACTIVE set: the set shown in
-- the editor is always the active one. New and Copy switch to the new set.

local function uniqueName(base)
  local taken = {}
  for _, id in ipairs(ns.Sets:List()) do taken[ns.Sets:Get(id).name] = true end
  if not taken[base] then return base end
  for n = 2, 999 do
    local candidate = base .. " " .. n
    if not taken[candidate] then return candidate end
  end
  return base
end

function Options:NewSet()
  local id = ns.Sets:Create(uniqueName(ns.L.SET_DEFAULT_NAME))
  if id then ns.Sets:SetActive(id) end
  return id
end

function Options:CopySet()
  local activeId = ns.Sets:Active()
  local id = activeId and ns.Sets:Copy(activeId)
  if id then ns.Sets:SetActive(id) end
  return id
end

function Options:PickOption(slot, buffId)
  local activeId = ns.Sets:Active()
  if activeId then ns.Sets:Pick(activeId, slot, buffId) end
end

if StaticPopupDialogs then
  StaticPopupDialogs["FULLBUFF_DELETE_SET"] = {
    text = "%s",
    button1 = ACCEPT,
    button2 = CANCEL,
    OnAccept = function(_, data)
      if data then ns.Sets:Delete(data) end
    end,
    timeout = 0,
    whileDead = true,
    hideOnEscape = true,
    preferredIndex = 3,
  }
end

function Options:ConfirmDelete()
  local activeId, set = ns.Sets:Active()
  if not (activeId and StaticPopup_Show and StaticPopupDialogs and StaticPopupDialogs["FULLBUFF_DELETE_SET"]) then return end
  StaticPopupDialogs["FULLBUFF_DELETE_SET"].text = ns.L.SET_DELETE_CONFIRM
  StaticPopup_Show("FULLBUFF_DELETE_SET", set.name, nil, activeId)
end

------------------------------------------------------------------ panel
-- Layout: the whole panel content lives in one scroll frame (UIPanelScrollFrameTemplate);
-- `root` is the canvas registered with Settings, `panel` the scroll child. The Sets
-- editor sits in `setsFrame`, anchored below the weight rows, and is re-laid out
-- from the models on every refresh using pooled widgets.

local root, panel, category, setsFrame
local texts = {} -- { fs, key }
local specButtons, langButtons, weightRows = {}, {}, {}
local allStatsCheck, scaleSlider, scaleLabel, resetButton
local setsHeader, setsSpecLabel, burstHeader
local radios, setButtons, burstChecks, burstUp, burstDown, titles = {}, {}, {}, {}, {}, {}
local ui = {}
local warned = false
local built = false
local refreshingSets = false

Options.radios, Options.setButtons, Options.burstChecks = radios, setButtons, burstChecks
Options.burstUp, Options.burstDown, Options.ui = burstUp, burstDown, ui

local function clear(t)
  for k in pairs(t) do t[k] = nil end
end

local function addText(key, template, x, y)
  local fs = panel:CreateFontString(nil, "ARTWORK", template)
  fs:SetPoint("TOPLEFT", panel, "TOPLEFT", x, y)
  fs:SetText(ns.L[key])
  texts[#texts + 1] = { fs = fs, key = key }
  return fs
end

local function newCheck(parent, x, y)
  local cb = CreateFrame("CheckButton", nil, parent, "UICheckButtonTemplate")
  cb:SetPoint("TOPLEFT", parent, "TOPLEFT", x, y)
  cb:SetSize(24, 24)
  local label = parent:CreateFontString(nil, "ARTWORK", "GameFontHighlight")
  label:SetPoint("LEFT", cb, "RIGHT", 4, 0)
  label:SetJustifyH("LEFT")
  cb.fbLabel = label
  return cb
end

local function newButton(parent, width, height)
  local b = CreateFrame("Button", nil, parent, "UIPanelButtonTemplate")
  b:SetSize(width, height or 22)
  return b
end

local function place(widget, x, y)
  widget:ClearAllPoints()
  widget:SetPoint("TOPLEFT", setsFrame, "TOPLEFT", x, y)
end

local function specLabel(i)
  if i == 0 then return ns.L.OPT_SPEC_AUTO end
  return string.format(ns.L.OPT_SPEC_FMT, i)
end

local function refreshWeights()
  local stats = Options:RelevantStats()
  local state = ns.PlayerState:Get()
  local ov = db().weightOverrides
  ov = ov and ov[state.class]
  ov = ov and ov[state.spec or 1]
  for i, stat in ipairs(stats) do
    local row = weightRows[i]
    if not row then
      row = {}
      row.label = panel:CreateFontString(nil, "ARTWORK", "GameFontHighlight")
      row.label:SetPoint("TOPLEFT", panel, "TOPLEFT", 16, -200 - (i - 1) * 24)
      row.box = CreateFrame("EditBox", nil, panel, "InputBoxTemplate")
      row.box:SetSize(60, 20)
      row.box:SetPoint("TOPLEFT", panel, "TOPLEFT", 200, -196 - (i - 1) * 24)
      row.box:SetAutoFocus(false)
      row.box:SetScript("OnEnterPressed", function(self) self:ClearFocus() end)
      row.box:SetScript("OnEditFocusLost", function(self)
        local t = self:GetText()
        Options:SetWeight(self.fbStat, t ~= "" and t or nil)
      end)
      row.box:SetScript("OnEscapePressed", function(self) self:ClearFocus() end)
      weightRows[i] = row
    end
    row.box.fbStat = stat
    row.label:SetText(ns.L["STAT_" .. stat])
    row.label:Show()
    row.box:SetText(ov and ov[stat] ~= nil and tostring(ov[stat]) or "")
    row.box:Show()
  end
  for i = #stats + 1, #weightRows do
    weightRows[i].label:Hide()
    weightRows[i].box:Hide()
  end
end

local function hideFrom(pool, from)
  for i = from, #pool do
    pool[i]:Hide()
    if pool[i].fbLabel then pool[i].fbLabel:Hide() end
  end
end

local function getRadio(i)
  local r = radios[i]
  if not r then
    r = newCheck(setsFrame, 0, 0)
    r.fbLabel:SetWidth(480)
    r:SetScript("OnClick", function(self) Options:PickOption(self.fbSlot, self.fbBuff) end)
    radios[i] = r
  end
  return r
end

local function getTitle(i)
  local t = titles[i]
  if not t then
    t = setsFrame:CreateFontString(nil, "ARTWORK", "GameFontNormal")
    titles[i] = t
  end
  return t
end

local function setRadio(r, slot, buffId, text, checked, grey, x, y)
  r.fbSlot, r.fbBuff = slot, buffId
  place(r, x, y)
  r:Show()
  r:SetChecked(checked)
  r.fbLabel:SetText(text)
  if grey then r.fbLabel:SetTextColor(0.6, 0.6, 0.6) else r.fbLabel:SetTextColor(1, 1, 1) end
  r.fbLabel:Show()
end

local function optionText(o)
  local L = ns.L
  local s = o.name
  if o.valueText ~= "" then s = s .. "  |cffb0b0b0" .. o.valueText .. "|r" end
  if o.active then s = ns.UI.MARK_CHECK .. " " .. s end
  if o.recommended then s = s .. " " .. ns.UI.MARK_STAR end
  if o.unavailable then s = s .. "  (" .. L.STATUS_UNAVAILABLE .. ")" end
  return s
end

local function getBurstRow(i)
  local c = burstChecks[i]
  if c then return c end
  c = newCheck(setsFrame, 0, 0)
  c.fbLabel:SetWidth(380)
  c:SetScript("OnClick", function(self)
    local id = ns.Sets:Active()
    if not id then return end
    if self.fbTracked then ns.Sets:RemoveBurst(id, self.fbBuff) else ns.Sets:AddBurst(id, self.fbBuff) end
  end)
  burstChecks[i] = c
  local up = CreateFrame("Button", nil, setsFrame, "UIPanelScrollUpButtonTemplate")
  up:SetSize(22, 22)
  up:SetScript("OnClick", function(self)
    local id = ns.Sets:Active()
    if id then ns.Sets:MoveBurst(id, self.fbBuff, -1) end
  end)
  burstUp[i] = up
  local down = CreateFrame("Button", nil, setsFrame, "UIPanelScrollDownButtonTemplate")
  down:SetSize(22, 22)
  down:SetScript("OnClick", function(self)
    local id = ns.Sets:Active()
    if id then ns.Sets:MoveBurst(id, self.fbBuff, 1) end
  end)
  burstDown[i] = down
  return c
end

local function layoutSets()
  local L = ns.L
  local activeId, set = ns.Sets:Active()
  local top = 200 + #Options:RelevantStats() * 24 + 24
  setsFrame:ClearAllPoints()
  setsFrame:SetPoint("TOPLEFT", panel, "TOPLEFT", 0, -top)
  setsFrame:SetSize(580, 10)

  setsHeader:SetText(L.OPT_SETS)
  ui.new:SetText(L.SET_NEW)
  ui.copy:SetText(L.SET_COPY)
  ui.rename:SetText(L.SET_RENAME)
  ui.delete:SetText(L.SET_DELETE)
  setsSpecLabel:SetText(L.SET_BIND_SPEC)
  burstHeader:SetText(L.OPT_BURST)

  local y = -24
  -- one button per set; the active (edited) set's button is disabled = selected
  local ids = ns.Sets:List()
  for i, id in ipairs(ids) do
    local b = setButtons[i]
    if not b then
      b = newButton(setsFrame, 120, 22)
      b:SetScript("OnClick", function(self) ns.Sets:SetActive(self.fbSet) end)
      setButtons[i] = b
    end
    b.fbSet = id
    b:SetText(ns.Sets:Get(id).name)
    b:SetEnabled(id ~= activeId)
    place(b, 16 + ((i - 1) % 4) * 126, y - math.floor((i - 1) / 4) * 26)
    b:Show()
  end
  hideFrom(setButtons, #ids + 1)
  y = y - math.max(1, math.ceil(#ids / 4)) * 26 - 4

  -- the default set follows recommendations until a slot is edited
  if set and set.auto then
    ui.autoLabel:SetText(L.SET_AUTO)
    place(ui.autoLabel, 20, y)
    ui.autoLabel:Show()
    y = y - 18
  else
    ui.autoLabel:Hide()
  end

  -- New / Copy / Rename / Delete (+ rename edit box)
  for i, b in ipairs({ ui.new, ui.copy, ui.rename, ui.delete }) do
    place(b, 16 + (i - 1) * 104, y)
    b:SetEnabled(i == 1 or activeId ~= nil)
  end
  y = y - 30
  -- rename edit box: own row, so it stays inside the scroll child
  if ui.renameBox:IsShown() and ui.renameBox.fbSet ~= activeId then ui.renameBox:Hide() end
  if ui.renameBox:IsShown() then
    place(ui.renameBox, 20, y)
    y = y - 26
  end
  y = y - 6

  -- spec binding: None / 1 / 2 / 3
  place(setsSpecLabel, 16, y)
  y = y - 22
  for i = 0, 3 do
    local b = ui.specs[i]
    place(b, 16 + i * 140, y)
    b.fbLabel:SetText(i == 0 and L.SET_BIND_NONE or Options:SpecLabel(i))
    b:SetChecked(set ~= nil and ((i == 0 and not set.spec) or set.spec == i))
  end
  y = y - 32

  -- conflict slots: "one of" radios plus "not used"
  local nRadio, nTitle = 0, 0
  if set then
    for _, slot in ipairs(Options:SlotModel(activeId)) do
      nTitle = nTitle + 1
      local t = getTitle(nTitle)
      t:ClearAllPoints()
      t:SetPoint("TOPLEFT", setsFrame, "TOPLEFT", 16, y)
      t:SetText(slot.name)
      t:Show()
      y = y - 22
      for _, o in ipairs(slot.options) do
        nRadio = nRadio + 1
        setRadio(getRadio(nRadio), slot.slot, o.buffId, optionText(o), slot.picked == o.buffId, o.unavailable, 32, y)
        y = y - 22
      end
      nRadio = nRadio + 1
      setRadio(getRadio(nRadio), slot.slot, false, L.SLOT_NOT_USED, slot.picked == false, true, 32, y)
      y = y - 28
    end
  end
  hideFrom(radios, nRadio + 1)
  for i = nTitle + 1, #titles do titles[i]:Hide() end

  -- burst list: checkbox (tracked) plus up/down for the tracked ones
  place(burstHeader, 16, y)
  y = y - 24
  local nBurst = 0
  if set then
    for _, b in ipairs(Options:BurstModel(activeId)) do
      nBurst = nBurst + 1
      local c = getBurstRow(nBurst)
      c.fbBuff, c.fbTracked = b.buffId, b.tracked
      place(c, 16, y)
      c:Show()
      c:SetChecked(b.tracked)
      local label = b.name .. "  |cffb0b0b0" .. string.format(L.IN_BAGS, b.bagCount) .. "|r"
      if b.unavailable then label = b.name .. "  (" .. L.STATUS_UNAVAILABLE .. ")" end
      c.fbLabel:SetText(label)
      if b.unavailable then c.fbLabel:SetTextColor(0.6, 0.6, 0.6) else c.fbLabel:SetTextColor(1, 1, 1) end
      c.fbLabel:Show()
      local up, down = burstUp[nBurst], burstDown[nBurst]
      up.fbBuff, down.fbBuff = b.buffId, b.buffId
      if b.tracked then
        place(up, 440, y)
        place(down, 466, y)
        up:Show()
        down:Show()
      else
        up:Hide()
        down:Hide()
      end
      y = y - 24
    end
  end
  hideFrom(burstChecks, nBurst + 1)
  hideFrom(burstUp, nBurst + 1)
  hideFrom(burstDown, nBurst + 1)

  local height = -y + 16
  setsFrame:SetHeight(height)
  panel:SetHeight(top + height + 16)
end

-- RefreshSets: re-lays out the Sets editor. Only while the panel is open; guarded
-- against re-entry (the first bag count may fire FULLBUFF_BAGS from inside).
function Options:RefreshSets()
  if not (built and root.fbOpened) or refreshingSets then return end
  refreshingSets = true
  local ok, err = pcall(layoutSets)
  refreshingSets = false
  if not ok then error(err, 0) end
end

function Options:Refresh()
  if not built then return end
  for _, t in ipairs(texts) do t.fs:SetText(ns.L[t.key]) end
  local cur = charDb().specOverride or 0
  for i = 0, 3 do
    specButtons[i].fbLabel:SetText(specLabel(i))
    specButtons[i]:SetChecked(cur == i)
  end
  allStatsCheck.fbLabel:SetText(ns.L.OPT_ALL_STATS)
  allStatsCheck:SetChecked(db().showAllStats and true or false)
  scaleLabel:SetText(string.format("%s: %.1f", ns.L.OPT_SCALE, db().scale or 1))
  scaleSlider.fbSetting = true
  scaleSlider:SetValue(db().scale or 1)
  scaleSlider.fbSetting = false
  local lang = ns.GetLanguage()
  for _, b in ipairs(langButtons) do b:SetChecked(b.fbCode == lang) end
  resetButton:SetText(ns.L.OPT_RESET_POS)
  refreshWeights()
  Options:RefreshSets()
end

local function buildSets()
  setsFrame = CreateFrame("Frame", nil, panel)
  setsFrame:SetPoint("TOPLEFT", panel, "TOPLEFT", 0, -600)
  setsFrame:SetSize(580, 10)
  setsHeader = setsFrame:CreateFontString(nil, "ARTWORK", "GameFontNormalLarge")
  setsHeader:SetPoint("TOPLEFT", setsFrame, "TOPLEFT", 16, 0)
  setsSpecLabel = setsFrame:CreateFontString(nil, "ARTWORK", "GameFontNormal")
  burstHeader = setsFrame:CreateFontString(nil, "ARTWORK", "GameFontNormal")
  ui.autoLabel = setsFrame:CreateFontString(nil, "ARTWORK", "GameFontHighlightSmall")
  ui.autoLabel:Hide()

  ui.new = newButton(setsFrame, 100)
  ui.new:SetScript("OnClick", function() Options:NewSet() end)
  ui.copy = newButton(setsFrame, 100)
  ui.copy:SetScript("OnClick", function() Options:CopySet() end)
  ui.delete = newButton(setsFrame, 100)
  ui.delete:SetScript("OnClick", function() Options:ConfirmDelete() end)

  -- Rename: Enter commits, Escape (or losing focus) cancels without saving.
  ui.renameBox = CreateFrame("EditBox", nil, setsFrame, "InputBoxTemplate")
  ui.renameBox:SetSize(150, 20)
  ui.renameBox:SetAutoFocus(false)
  ui.renameBox:SetMaxLetters(40)
  ui.renameBox:Hide()
  -- The box sits on its own row of the layout, so every show/hide re-lays it out.
  local function closeRename(box)
    box:Hide()
    Options:RefreshSets()
  end
  ui.renameBox:SetScript("OnEnterPressed", function(self)
    local text = (self:GetText() or ""):match("^%s*(.-)%s*$")
    local id = self.fbSet
    closeRename(self)
    if id and text ~= "" then ns.Sets:Rename(id, text) end
  end)
  ui.renameBox:SetScript("OnEscapePressed", closeRename)
  ui.renameBox:SetScript("OnEditFocusLost", closeRename)
  ui.rename = newButton(setsFrame, 100)
  ui.rename:SetScript("OnClick", function()
    local id, set = ns.Sets:Active()
    if not id then return end
    local box = ui.renameBox
    box.fbSet = id
    box:SetText(set.name)
    box:Show()
    Options:RefreshSets()
    box:SetFocus()
    box:HighlightText()
  end)

  ui.specs = {}
  for i = 0, 3 do
    local b = newCheck(setsFrame, 0, 0)
    b.fbIndex = i
    b:SetScript("OnClick", function(self)
      local id = ns.Sets:Active()
      if id then ns.Sets:BindSpec(id, self.fbIndex ~= 0 and self.fbIndex or nil) end
    end)
    ui.specs[i] = b
  end
end

local function buildPanel()
  root = CreateFrame("Frame", "FullBuffOptionsPanel", UIParent)
  root.name = "FullBuff"
  local scroll = CreateFrame("ScrollFrame", "FullBuffOptionsScroll", root, "UIPanelScrollFrameTemplate")
  scroll:SetPoint("TOPLEFT", root, "TOPLEFT", 0, -4)
  scroll:SetPoint("BOTTOMRIGHT", root, "BOTTOMRIGHT", -28, 4)
  panel = CreateFrame("Frame", nil, scroll)
  panel:SetSize(580, 1000)
  scroll:SetScrollChild(panel)

  local title = panel:CreateFontString(nil, "ARTWORK", "GameFontNormalLarge")
  title:SetPoint("TOPLEFT", 16, -16)
  title:SetText(ns.L.TITLE)

  -- Specialization: Auto / 1 / 2 / 3
  addText("OPT_SPEC", "GameFontNormal", 16, -48)
  for i = 0, 3 do
    local b = newCheck(panel, 16 + i * 140, -68)
    b.fbIndex = i
    b:SetScript("OnClick", function(self)
      Options:SetSpecOverride(self.fbIndex ~= 0 and self.fbIndex or nil)
      Options:Refresh()
    end)
    specButtons[i] = b
  end

  -- Language
  addText("OPT_LANGUAGE", "GameFontNormal", 16, -104)
  for i, l in ipairs(LANGS) do
    local b = newCheck(panel, 16 + (i - 1) * 140, -124)
    b.fbCode = l.code
    b.fbLabel:SetText(l.label)
    b:SetScript("OnClick", function(self) ns.SetLanguage(self.fbCode) end)
    langButtons[i] = b
  end

  -- Icon scale
  scaleLabel = panel:CreateFontString(nil, "ARTWORK", "GameFontHighlight")
  scaleLabel:SetPoint("TOPLEFT", 16, -160)
  scaleSlider = CreateFrame("Slider", nil, panel, "OptionsSliderTemplate")
  scaleSlider:SetPoint("TOPLEFT", 200, -160)
  scaleSlider:SetWidth(160)
  scaleSlider:SetMinMaxValues(SCALE_MIN, SCALE_MAX)
  scaleSlider:SetValueStep(0.1)
  scaleSlider:SetScript("OnValueChanged", function(self, value)
    if self.fbSetting then return end
    Options:SetScale(math.floor(value * 10 + 0.5) / 10)
    scaleLabel:SetText(string.format("%s: %.1f", ns.L.OPT_SCALE, db().scale or 1))
  end)

  -- Weights (left column, below)
  addText("OPT_WEIGHTS", "GameFontNormal", 16, -184)
  addText("OPT_WEIGHTS_HINT", "GameFontHighlightSmall", 120, -186)

  -- All-stats and reset (right column)
  allStatsCheck = newCheck(panel, 320, -204)
  allStatsCheck:SetScript("OnClick", function(self)
    Options:SetShowAllStats(self:GetChecked())
  end)

  resetButton = CreateFrame("Button", nil, panel, "UIPanelButtonTemplate")
  resetButton:SetSize(160, 24)
  resetButton:SetPoint("TOPLEFT", 320, -240)
  resetButton:SetScript("OnClick", function() Options:ResetPosition() end)

  buildSets()

  root:SetScript("OnShow", function()
    root.fbOpened = true
    Options:Refresh()
  end)
  root:SetScript("OnHide", function() root.fbOpened = false end)
  built = true
  Options:Refresh()
end

-- Build() is all-or-nothing: on error the half-built state is dropped and the
-- error is re-raised, so root is only set once every widget exists.
function Options:Build()
  if built then return root end
  local ok, err = pcall(buildPanel)
  if not ok then
    root, panel, setsFrame, built = nil, nil, nil, false
    resetButton, allStatsCheck, scaleSlider, scaleLabel = nil, nil, nil, nil
    setsHeader, setsSpecLabel, burstHeader = nil, nil, nil
    texts, specButtons, langButtons, weightRows, titles = {}, {}, {}, {}, {}
    clear(radios); clear(setButtons); clear(burstChecks); clear(burstUp); clear(burstDown); clear(ui)
    error(err, 0)
  end
  return root
end

local function report(err)
  local msg = ns.L.SETTINGS_UNAVAILABLE .. (err and (" (" .. tostring(err) .. ")") or "")
  print("FullBuff: " .. msg)
end

local function register()
  if category then return end
  if not (Settings and Settings.RegisterCanvasLayoutCategory and Settings.RegisterAddOnCategory) then return end
  local ok, res = pcall(function()
    local c = Settings.RegisterCanvasLayoutCategory(Options:Build(), "FullBuff")
    Settings.RegisterAddOnCategory(c)
    return c
  end)
  if ok then
    category = res
  else
    geterrorhandler()("FullBuff options: " .. tostring(res))
    report(res)
  end
end

function ns.UI.OpenOptions()
  if not (Settings and Settings.OpenToCategory) then
    if not warned then
      warned = true
      report()
    end
    return
  end
  register()
  if category then
    Settings.OpenToCategory(category:GetID())
  else
    report()
  end
end

ns.Events:On("FULLBUFF_LOADED", register)
ns.Events:On("FULLBUFF_LANGUAGE", function() Options:Refresh() end)
ns.Events:On("FULLBUFF_SET", function() Options:RefreshSets() end)
ns.Events:On("FULLBUFF_STATE", function() Options:RefreshSets() end)
ns.Events:On("FULLBUFF_BAGS", function() Options:RefreshSets() end)
