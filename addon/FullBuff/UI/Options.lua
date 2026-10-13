local _, ns = ...

-- Options: logic (ns.Options setters) plus the Settings canvas panel.
-- Every setter that changes what the engine computes or what the popover shows
-- ends in recompute(): PlayerState:Refresh() fires FULLBUFF_STATE, which the
-- popover and launcher already listen to.
-- Option keys: ns.CharDB.specOverride, ns.DB.weightOverrides[class][spec][stat],
-- ns.DB.hiddenCats[cat], ns.DB.showAllStats, ns.DB.scale, ns.DB.launcher,
-- ns.DB.collapsed, ns.DB.lang.
ns.UI = ns.UI or {}
local Options = {}
ns.Options = Options

local SCALE_MIN, SCALE_MAX = 0.5, 2.0
local CATEGORIES = { "CLASS", "WORLD", "CAMPING", "FLASK", "ELIXIR", "FOOD", "SCROLL", "WEAPON", "QUEST", "TRINKET", "POTION" }
-- Endonyms: shown the same in every UI language.
local LANGS = { { code = "en", label = "English" }, { code = "uk", label = "Українська" } }
Options.CATEGORIES, Options.LANGS = CATEGORIES, LANGS

local function db()
  ns.DB = ns.DB or {}
  return ns.DB
end

local function charDb()
  ns.CharDB = ns.CharDB or {}
  return ns.CharDB
end

local function recompute()
  ns.PlayerState:Refresh()
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

function Options:SetCategoryHidden(cat, hidden)
  local d = db()
  d.hiddenCats = d.hiddenCats or {}
  d.hiddenCats[cat] = hidden and true or nil
  recompute()
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

-- Position and collapsed sections (used by /fullbuff reset).
function Options:ResetLayout()
  self:ResetPosition()
  db().collapsed = {}
  recompute()
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

------------------------------------------------------------------ panel

local panel, category
local texts = {} -- { fs, key }
local specButtons, catChecks, langButtons, weightRows = {}, {}, {}, {}
local allStatsCheck, scaleSlider, scaleLabel, resetButton
local warned = false
local built = false

local function addText(key, template, x, y)
  local fs = panel:CreateFontString(nil, "ARTWORK", template)
  fs:SetPoint("TOPLEFT", panel, "TOPLEFT", x, y)
  fs:SetText(ns.L[key])
  texts[#texts + 1] = { fs = fs, key = key }
  return fs
end

local function newCheck(x, y)
  local cb = CreateFrame("CheckButton", nil, panel, "UICheckButtonTemplate")
  cb:SetPoint("TOPLEFT", panel, "TOPLEFT", x, y)
  cb:SetSize(24, 24)
  local label = panel:CreateFontString(nil, "ARTWORK", "GameFontHighlight")
  label:SetPoint("LEFT", cb, "RIGHT", 4, 0)
  cb.fbLabel = label
  return cb
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

function Options:Refresh()
  if not built then return end
  for _, t in ipairs(texts) do t.fs:SetText(ns.L[t.key]) end
  local cur = charDb().specOverride or 0
  for i = 0, 3 do
    specButtons[i].fbLabel:SetText(specLabel(i))
    specButtons[i]:SetChecked(cur == i)
  end
  local hidden = db().hiddenCats
  for _, c in ipairs(catChecks) do
    c.fbLabel:SetText(ns.L["CATEGORY_" .. c.fbCat])
    c:SetChecked(not (hidden and hidden[c.fbCat]))
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
end

local function buildPanel()
  panel = CreateFrame("Frame", "FullBuffOptionsPanel", UIParent)
  panel.name = "FullBuff"

  local title = panel:CreateFontString(nil, "ARTWORK", "GameFontNormalLarge")
  title:SetPoint("TOPLEFT", 16, -16)
  title:SetText(ns.L.TITLE)

  -- Specialization: Auto / 1 / 2 / 3
  addText("OPT_SPEC", "GameFontNormal", 16, -48)
  for i = 0, 3 do
    local b = newCheck(16 + i * 140, -68)
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
    local b = newCheck(16 + (i - 1) * 140, -124)
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

  -- Categories and all-stats (right column)
  addText("OPT_CATEGORIES", "GameFontNormal", 320, -184)
  for i, cat in ipairs(CATEGORIES) do
    local c = newCheck(320, -204 - (i - 1) * 24)
    c.fbCat = cat
    c:SetScript("OnClick", function(self)
      Options:SetCategoryHidden(self.fbCat, not self:GetChecked())
    end)
    catChecks[i] = c
  end
  allStatsCheck = newCheck(320, -204 - #CATEGORIES * 24 - 8)
  allStatsCheck:SetScript("OnClick", function(self)
    Options:SetShowAllStats(self:GetChecked())
  end)

  resetButton = CreateFrame("Button", nil, panel, "UIPanelButtonTemplate")
  resetButton:SetSize(160, 24)
  resetButton:SetPoint("TOPLEFT", 16, -520)
  resetButton:SetScript("OnClick", function() Options:ResetPosition() end)

  panel:SetScript("OnShow", function() Options:Refresh() end)
  built = true
  Options:Refresh()
end

-- Build() is all-or-nothing: on error the half-built state is dropped and the
-- error is re-raised, so panel is only set once every widget exists.
function Options:Build()
  if built then return panel end
  local ok, err = pcall(buildPanel)
  if not ok then
    panel, built, resetButton, allStatsCheck, scaleSlider, scaleLabel = nil, false, nil, nil, nil, nil
    texts, specButtons, catChecks, langButtons, weightRows = {}, {}, {}, {}, {}
    error(err, 0)
  end
  return panel
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
