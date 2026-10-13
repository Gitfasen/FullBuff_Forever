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
- [ ] The raid-star marker texture renders in the options Sets editor (pending user verification)
- [ ] Buffs already on the character show a green tick and green name and are listed first; the popover lists only the active set. The raid star marks the recommended option in the options editor (pending user verification)
- [ ] Ukrainian text renders with no missing glyphs (boxes or question marks) (pending user verification)

## 3. Launcher and popover

- [ ] The launcher icon appears, drags with the left mouse button, and keeps its position after `/reload` (pending user verification)
- [ ] The badge number is the count of recommended missing buffs and updates after buffing (pending user verification)
- [ ] Left click opens and closes the popover, on the side of the launcher with more screen space (pending user verification)
- [ ] Escape closes the popover (pending user verification)
- [ ] Dragging the launcher is refused during combat (pending user verification)
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
- [ ] Changing a pick in the editor updates the popover list and the set maximum (pending user verification)
- [ ] "Show all stats" adds extra stat rows; the icon scale slider resizes the launcher between 0.5 and 2.0; "Reset position" re-anchors it (pending user verification)
- [ ] "Українська" (panel or `/fullbuff lang uk`) turns the whole UI, the card and pin tooltips Ukrainian at once with no overflow; "English" reverts; it survives `/reload` (pending user verification)
- [ ] `/fullbuff` toggles the popover, `/fullbuff options` opens settings, `/fullbuff reset` resets the launcher position, `/fullbuff debug` lists unknown auras and stale state, an unknown subcommand prints usage (pending user verification)
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

## 8. Buff sets

- [ ] In options, Sets: New, Copy, Rename (Enter commits, Escape cancels; the box sits on its own row) and Delete (asks for confirmation) work; New and Copy switch to the new set (pending user verification)
- [ ] Binding a set to a specialization (1/2/3/None) and then changing talents or specialization switches the active set automatically (pending user verification)
- [ ] The popover lists only the buffs of the active set, with buffs already on the character (green tick) first (pending user verification)
- [ ] The set button in the popover header cycles through the sets (pending user verification)
- [ ] In the editor the recommended option shows the raid star and the active one the green tick; picking an option changes the popover and the set maximum (pending user verification)
- [ ] Bag counts of tracked potions and trinkets update after using a potion (pending user verification)
- [ ] An elixir or flask in the bags shows "in bags ×N" in its row (pending user verification)
- [ ] A level-gated pick in a set shows the unavailable marker in the popover and greyed in the editor; a tracked burst item that is no longer obtainable is greyed with the unavailable label (pending user verification)
- [ ] With an empty set the popover button opens the options (pending user verification)
- [ ] With the options open, levelling up or changing buffs refreshes the slot list without reopening (pending user verification)

