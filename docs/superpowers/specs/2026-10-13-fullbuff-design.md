# FullBuff — Design Spec

Date: 2026-10-13
Status: Draft for review
Target: World of Warcraft: Forever (beta build 1.60.1.70338, `## Interface: 16001`, `WOW_PROJECT_ID == 18` / `WOW_PROJECT_CAMELOT`)

## 1. Purpose

FullBuff is a personal utility addon. It shows the **maximum stats** the current character could reach at its current level if it collected **every obtainable buff** in the game, compares that with what is active right now, and tells the player **what is missing and where to get it**.

Primary goal: surface buffs the player may have missed.

### Success criteria

- For the current class, spec and level, the popover lists every relevant obtainable buff by category, marked active / can add / unavailable by level.
- The header shows, per relevant stat, `current → maximum (+difference)`.
- Each missing buff has a detail card with its effect and its sources; any source with coordinates can be pinned on the map (one, several, or all).
- The buff database is regenerated from all sources with one command.

### Decisions taken during brainstorming

| Topic | Decision |
|---|---|
| Meaning of "maximum" | Current stats + all obtainable buffs, computed numerically (percent buffs and stacking included). |
| Context of maximum | Theoretical ceiling: all classes' cast buffs and all world/NPC buffs. **Excluded:** passive group auras (paladin auras, Trueshot Aura, Leader of the Pack, Moonkin Aura) and shaman totems. |
| Burst buffs | Short buffs (potions, on-use trinkets, ~15–30 s) are listed in their categories but **not** counted in the maximum. |
| Recommendations | Per-spec stat weights (built-in presets, user-overridable). |
| Inventory | Not used. No bag scanning, no "use" buttons. Info only. |
| Map marks | Own pins on world map and minimap (HereBeDragons-Pins); multiple at once; choose from a list when a buff has several locations. |
| UI languages | English (default) and Ukrainian. No Russian. |
| Data | Generated once by a single command from all available sources, plus a hand-curated overrides file. |

## 2. Platform facts and constraints

- Content is vanilla-era (level cap 60) running on a modern (12.x-family) API: `C_UnitAuras`, specializations (talent trees), gamepad, `issecretvalue`.
- In combat and in instances some values (auras, GUIDs) can be **secret**. FullBuff reads auras only when values are readable; every value is checked with `issecretvalue` before use.
- No realm names on Forever.
- `C_Map.SetUserWaypoint` is unreliable on Forever (per ForeverDungeonJournal `Systems/MapMarkers.lua`), so FullBuff draws its own pins.
- Spec on Forever is the talent tree with the most points spent (`GetSpecializationInfo(i)` returns points spent per tree, as used by DBM).
- WoW has no Ukrainian client locale; language is chosen in FullBuff options.

### Blizzard UI Add-On Development Policy compliance

Free of charge; code visible and not obfuscated; no advertising; no in-game donation requests; no harm to realm performance or other players; no objectionable content; complies with ToS/EULA. FullBuff additionally: makes no network requests, sends no addon messages, automates no actions, uses no protected functions or secure buttons.

## 3. Repository layout

Repository: `C:\dev\FullBuff`. The addon folder is linked into the game with a directory junction:
`Interface\AddOns\FullBuff` → `C:\dev\FullBuff\addon\FullBuff`.

```
FullBuff/
  tools/                         # Python 3.12, never shipped
    build.py                     # single entry point
    sources/db2.py               # download + cache DB2 CSVs, extract buffs
    sources/questie.py           # NPC/vendor/quest/coordinates from QuestieDB_Forever
    sources/forever_info.py      # Forever-specific buffs (camping etc.) from wowclassicforever.info
    curated.yaml                 # manual additions, fixes, exclusions, stacking groups, weights
    emit_lua.py                  # writes addon/FullBuff/Data/*.lua
    tests/                       # pytest, small CSV fixtures
  addon/FullBuff/
    FullBuff_Forever.toc
    Core/        Init.lua, Events.lua, SavedVars.lua, Compat.lua, Locale.lua
    Locales/     enUS.lua, ukUA.lua
    Data/        Buffs.lua, Sources.lua, Weights.lua   # generated, never edited by hand
    Engine/      PlayerState.lua, Catalog.lua, Scoring.lua, MaxCalc.lua
    UI/          Launcher.lua, Popover.lua, DetailCard.lua, Options.lua
    Systems/     MapPins.lua
    Libs/        HereBeDragons-2.0, HereBeDragons-Pins-2.0
  tests/lua/     # addon Lua tests (pytest + lupa, WoW API mocks)
  docs/
    superpowers/specs/
    manual-test.md
```

Module rule: Engine never touches frames; UI consumes Engine results only. Generated data is kept separate from curated overrides so a rebuild after a patch never loses manual work.

## 4. Data pipeline

### Command

```
python tools/build.py --build 1.60.1.70338
```

### Steps

1. **Fetch** DB2 CSVs for the build from `https://wago.tools/db2/<Table>/csv?build=<build>` into `tools/.cache/<build>/` (skipped if cached). Tables: SpellName, Spell, SpellEffect, SpellMisc, SpellDuration, SpellLevels, SpellClassOptions, SpellCategories, SpellAuraOptions, SkillLineAbility, ItemEffect, ItemXItemEffect, Item, ItemSparse. Classic Era SpellName (build 1.15.9.70003) is fetched to flag buffs new in Forever.
2. **Extract** stat buffs: SpellEffect rows with `Effect` in {6, 35, 65} and a stat aura type, or `Effect` 54 (temporary weapon enchant). Aura types → normalized stats:
   29 → STR/AGI/STA/INT/SPI (MiscValue; -1 = all), 137 → stat %, 99 → AP, 124 → RAP, 166 → AP %, 13 → SPELL_DMG (school mask), 135 → HEAL, 22 → ARMOR/resistances (school mask), 142 → armor %, 34 → HP, 35 → MANA, 85 → MP5, 84 → HP5, 52 → CRIT, 57/71 → SPELL_CRIT, 54 → HIT, 55 → SPELL_HIT.
3. **Link and classify**: item on-use (`ItemEffect.TriggerType == 0`) → category by Item ClassID/SubclassID/InventoryType (flask, elixir, potion, scroll, food/drink, weapon enhancement, quest item, trinket/on-use); class spells via SpellClassOptions + SkillLineAbility with ranks and target-level limits from SpellLevels; remaining long buffs (≥ 10 min, no item/class) → world/NPC candidates.
4. **Filter noise**: drop ammo, keys, pets, and anything in the curated exclusion list.
5. **Join sources**: vendors, drops, quest rewards, NPC and object coordinates from the installed QuestieDB_Forever; camping and other Forever-specific sources from wowclassicforever.info (fetched politely, cached, used only at build time).
6. **Apply `curated.yaml`**: add world/NPC buffs and their sources, correct values, set `excl` stacking groups, mark `burst`, exclusions, and per-spec stat weights.
7. **Emit** `Data/Buffs.lua`, `Data/Sources.lua`, `Data/Weights.lua`, plus `tools/out/build_report.md`: counts per category, new-in-Forever list, buffs without sources, unknown stacking groups.

### Buff record (`Data/Buffs.lua`)

```lua
[17538] = {                    -- spellID of the aura
  name  = "Elixir of the Mongoose",
  cat   = "ELIXIR",
  fx    = { AGI = 25, CRIT = 2 },
  dur   = 3600,                -- seconds
  lvl   = 46,                  -- minimum level (item requirement or rank)
  excl  = "ELIXIR_AGI",        -- stacking group: only one buff per group counts
  items = { 13452 },
  burst = false,
}
-- class buffs carry ranks:
-- ranks = { { spell = 1243, lvl = 1, fx = { STA = 3 } }, ... }
```

### Source record (`Data/Sources.lua`)

```lua
[17538] = {
  { kind = "craft",  name = "Alchemy", note = "275" },
  { kind = "vendor", name = "…", mapID = 1434, x = 0.272, y = 0.770 },
}
-- kind: vendor | drop | quest | craft | npc | object | camping
```

### Categories (popover order, configurable)

Class buffs · World & NPC buffs · Camping · Flasks · Elixirs · Food · Scrolls · Weapon enhancements · Quest items · Trinkets & on-use (burst) · Potions (burst).

## 5. Engine

### PlayerState

- Class, level (`PLAYER_LEVEL_UP`), spec = tree with most points; below 10 points the class preset is used; manual override in options.
- Current stats via `UnitStat`, `UnitAttackPower`, `UnitRangedAttackPower`, `GetSpellBonusDamage`, `GetSpellBonusHealing`, `GetCritChance`, `GetSpellCritChance`, `UnitHealthMax`, `UnitPowerMax`, `UnitArmor`.
- Active buffs via `C_UnitAuras.GetAuraDataByIndex("player", i, "HELPFUL")`, matched to the database by spellID. Skipped while in combat or when any value is secret; the last good snapshot is kept and flagged stale.

### Catalog

Filters the database for the current class/spec/level: item buffs by `lvl`; class buffs choose the highest rank castable on a target of the player's level; burst buffs are listed but flagged.

Buff status: **active** · **can add** · **unavailable by level**.

### Scoring

- `score = Σ (stat value × spec weight)` after converting primary stats to derived stats.
- Conversion ratios come from the client at runtime (`GetAttackPowerForStat`, `GetCritChanceFromAgility`, `GetSpellCritChanceFromIntellect`, Stamina → HP, Intellect → mana), so Forever formulas are not hard-coded.
- In every `excl` group the best-scoring buff is marked recommended (★).
- Weights: built-in presets per class × 3 specs (from `curated.yaml`), user overrides saved in SavedVariables.

### MaxCalc

1. Unbuffed baseline = current stats − contribution of active buffs known to the database.
2. Pick the best non-burst buff per `excl` group; sum flat bonuses.
3. Apply percent buffs (Kings, Spirit of Zandalar, Boosted Stats, …) to primary stats; order of application to be verified in game.
4. Recompute derived stats with the runtime ratios.
5. Output per relevant stat: current, maximum, difference; plus the list of missing buffs.

Shown stats: those with a non-zero weight for the spec; option "show all stats".

Unknown active auras are not subtracted; they are logged with `/fullbuff debug`.

### Updates

Event-driven with a short debounce: `UNIT_AURA` (player), `PLAYER_REGEN_ENABLED`, `PLAYER_LEVEL_UP`, talent changes, `PLAYER_EQUIPMENT_CHANGED`. No OnUpdate polling.

## 6. UI

### Launcher

- Single round icon, draggable (not in combat), position saved.
- Badge with the number of buffs that can be added.
- Tooltip: percent of maximum reached, number of missing buffs.
- Left-click toggles the popover, right-click opens options. Also registered in the Addon Compartment.

### Popover

- Opens next to the icon, flipping side to stay on screen; closes on Esc or icon click.
- Header: class, spec, level, stat table `current → max (+diff)`.
- Collapsible category sections with an `active/total` counter; rows show icon, name, value, status, ★ for recommended; missing first, active dimmed at the bottom.
- Toggle "show only missing".

### DetailCard

- Effect values, duration, minimum level, stacking group members, score for the current spec.
- "Where to get": list of sources; each source with coordinates has a 📍 button; "📍 all" when there are several.
- Unknown source shows "source unknown".

### MapPins

- Own pins on world map and minimap via HereBeDragons-Pins; several at once; tooltip = buff + source; right-click removes a pin; "clear all pins" in the card and options; pins persist across sessions.

### Options (`Settings` panel)

Manual spec, weight editing, category visibility and order, show all stats, icon scale, reset icon position, language (English / Українська). Slash command `/fullbuff` (`lang en|uk`, `debug`, `reset`).

### Localization

Own UI strings in `Locales/enUS.lua` and `Locales/ukUA.lua`; English is the fallback. Buff, item, NPC and zone names come from the client/database (English).

## 7. Error handling

- Secret values, combat, instances: no aura reads; stale snapshot with an "updates after combat" note.
- Spec unknown: class preset plus a hint to set the spec manually.
- Missing source data: "source unknown" in the card; listed in `build_report.md`.
- Each event handler is isolated so a failure in one module does not break the others; errors go to the standard error handler, never silenced.

## 8. Testing

- **Build tools (pytest):** stat normalization, noise filtering, stacking groups, curated merge, valid Lua output, using small CSV fixtures.
- **Addon logic (Lua 5.1 via the `lupa` Python package, driven by pytest, with WoW API mocks; no separate Lua toolchain needed):** Catalog level/class/rank filtering, Scoring weights and best pick, MaxCalc subtraction/percent/derived stats, PlayerState behaviour in combat and with secret values.
- **In game (manual, `docs/manual-test.md`):** spec detection, maximum vs actually applied buffs on 2–3 classes, map pins, dragging, language switch. Percent-buff order and runtime ratios must be confirmed in game before the maximum is considered correct.

## 9. Out of scope for v1

Bag scanning and item use buttons; totems and passive group auras; burst buffs in the maximum; group synchronization; game versions other than Forever; translating game data names.
