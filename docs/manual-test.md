# Manual in-game tests

All items below are **pending user verification**: they need the Forever client, which the build/test environment cannot run. Work through them in order. Record numbers in the worksheet in section 7. If a number is wrong, write a failing pytest case for MaxCalc first, then fix.

## 1. Install and load

Install: `powershell -ExecutionPolicy Bypass -File tools/install_junction.ps1` (plain `-File` is blocked by the machine's execution policy; the bypass is per-process).

- [ ] Addon appears in the AddOns list at character select as "FullBuff" (pending user verification)
- [ ] After login there are no Lua errors (pending user verification)
- [ ] `/reload` produces no Lua errors (pending user verification)

## 2. Forever-specific environment

- [ ] `WOW_PROJECT_CAMELOT` is defined (`/dump WOW_PROJECT_CAMELOT`) and the addon takes the Forever code path (pending user verification)
- [ ] The libraries load without `LibStub`/`HereBeDragonsQuestie` errors, also when Questie is enabled (pending user verification)
- [ ] The Settings panel opens from both the launcher right-click and the addon compartment entry (pending user verification)
- [ ] The raid-star marker texture renders (pending user verification)
- [ ] Buffs already on the character show a green ready-check tick and green name, listed at the top of their category; recommended ones (star) follow, then the rest (pending user verification)
- [ ] Ukrainian text renders with no missing glyphs (boxes or question marks) (pending user verification)

## 3. Launcher and popover

- [ ] The launcher icon appears, drags with the left mouse button, and keeps its position after `/reload` (pending user verification)
- [ ] The badge number is the count of recommended missing buffs and updates after buffing (pending user verification)
- [ ] Left click opens and closes the popover, on the side of the launcher with more screen space (pending user verification)
- [ ] Escape closes the popover (pending user verification)
- [ ] Dragging the launcher is refused during combat (pending user verification)
- [ ] Section headers collapse/expand and the state survives `/reload`; "Show only missing" filters rows (pending user verification)
- [ ] Hovering the launcher shows progress and the missing buffs list (pending user verification)

## 4. Detail card and map pins

- [ ] Clicking a buff row opens the detail card beside the popover with effects, duration, required level, score, stacking group and every source (pending user verification)
- [ ] The pin button on a vendor source puts a red cross on the world map (right spot) and on the minimap (HereBeDragons pins work); the card shows it as pinned (pending user verification)
- [ ] "Pin all" pins every source with coordinates; pins in other zones show on their own maps (pending user verification)
- [ ] Right-clicking a pin removes it; "Clear pins" removes all (pending user verification)
- [ ] Pins survive `/reload` and a relog (pending user verification)
- [ ] Hovering a pin shows buff name, source text and the right-click hint (pending user verification)

## 5. Options, slash commands and language

- [ ] The specialization override changes recommended buffs and the header spec; "Automatic" restores the detected spec (pending user verification)
- [ ] Editing a stat weight (Enter) changes the ranking; clearing the box restores the default (pending user verification)
- [ ] Unchecking a category hides its popover section; the launcher badge is unchanged (pending user verification)
- [ ] "Show all stats" adds extra stat rows; the icon scale slider resizes the launcher between 0.5 and 2.0; "Reset position" re-anchors it (pending user verification)
- [ ] "Українська" (panel or `/fullbuff lang uk`) turns the whole UI, the card and pin tooltips Ukrainian at once with no overflow; "English" reverts; it survives `/reload` (pending user verification)
- [ ] `/fullbuff` toggles the popover, `/fullbuff options` opens settings, `/fullbuff reset` resets position and collapsed sections, `/fullbuff debug` lists unknown auras and stale state, an unknown subcommand prints usage (pending user verification)
- [ ] The settings panel has no overlap or overflow in both languages (pending user verification)

## 6. Combat, instances and stale behaviour

- [ ] Entering combat: no Lua errors, the popover still opens, and the stale note is shown rather than wrong numbers (pending user verification)
- [ ] Inside a dungeon/raid instance: no Lua errors, the stale note appears when data cannot be refreshed, and it clears after leaving combat/instance (pending user verification)
- [ ] Gaining/losing a buff mid-combat updates the list after combat ends (pending user verification)
- [ ] Food tier detection: eating different food is detected via "Well Fed" and the matching tier shows in the current buffs (pending user verification)

## 7. Max-calc correctness (2-3 classes)

Pick 2-3 classes (e.g. a melee, a caster, a hunter). Apply 3-4 known buffs, then compare. Fill the table.

| Class / spec | Buff applied | Character sheet value | FullBuff current | FullBuff max | Match? |
|---|---|---|---|---|---|
| | | | | | |
| | | | | | |
| | | | | | |
| | | | | | |
| | | | | | |
| | | | | | |

- [ ] FullBuff "current" equals the character sheet for every row (pending user verification)
- [ ] FullBuff "max" equals the hand-computed value with all recommended buffs (pending user verification)

Percent-buff order:

- [ ] Kings: the percent multiplier is applied in the same order as the client (base + gear + flat buffs) (pending user verification)
- [ ] Kings + Boosted Stats + Sayge together: the resulting stat equals the character sheet (additive vs multiplicative stacking as the client does it) (pending user verification)

Runtime ratios (verify per class):

- [ ] Attack power per STR and per AGI (pending user verification)
- [ ] Melee crit per AGI (pending user verification)
- [ ] Spell crit per INT (pending user verification)
- [ ] Hunter ranged attack power per AGI = 2 (pending user verification)
