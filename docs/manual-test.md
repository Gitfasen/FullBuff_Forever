# Manual in-game tests

All items below are **pending user verification** (they require running the game client).

## 1. Install and load (Task 8)

Install first: `powershell -ExecutionPolicy Bypass -File tools/install_junction.ps1` (plain `-File` is blocked by this machine's execution policy)

- [ ] Addon appears in the AddOns list at character select as "FullBuff" (pending user verification)
- [ ] After login, `/reload` produces no Lua errors (pending user verification)

## 2. Launcher and popover (Task 13)

- [ ] The launcher icon appears and can be dragged with the left mouse button; its position is kept after `/reload` (pending user verification)
- [ ] The badge number shows the count of recommended missing buffs and updates after buffing (pending user verification)
- [ ] Left click opens and closes the popover; it opens on the side of the launcher with more screen space (pending user verification)
- [ ] Escape closes the popover (pending user verification)
- [ ] Dragging the launcher is refused during combat (pending user verification)
- [ ] Section headers collapse and expand and the state survives `/reload`; the "Show only missing" checkbox filters rows (pending user verification)
- [ ] Hovering the launcher shows progress and the missing buffs list (pending user verification)

## 3. Detail card and map pins (Task 14)

- [ ] Clicking a buff row opens the detail card beside the popover; it shows effects, duration, required level, score, stacking group and every source (pending user verification)
- [ ] The pin button on a vendor source puts a red cross on the world map (at the right spot) and on the minimap; the card shows it as pinned (pending user verification)
- [ ] Several pins at once work ("Pin all" pins every source with coordinates; pins in other zones show on their own maps) (pending user verification)
- [ ] Right-clicking a pin on the map or minimap removes it; "Clear pins" removes all of them (pending user verification)
- [ ] Pins survive `/reload` and a relog (pending user verification)
- [ ] Hovering a pin shows the buff name, the source text and the right-click hint (pending user verification)
- [ ] The card and pin tooltips are fully Ukrainian after switching the language, with no layout overflow (pending user verification)
- [ ] The libraries load without Lua errors on Forever (no `LibStub`/`HereBeDragonsQuestie` errors) and the pins still work when Questie is also enabled (pending user verification)

## 4. Options, slash commands and language (Task 15)

- [ ] Right-clicking the launcher and clicking the addon compartment entry both open the FullBuff settings panel (pending user verification)
- [ ] Changing the specialization override changes the recommended buffs and the header spec; "Automatic" restores the detected spec (pending user verification)
- [ ] Editing a stat weight (Enter) changes the ranking; clearing the box restores the default (pending user verification)
- [ ] Unchecking a category hides its section in the popover; the launcher badge is unchanged (pending user verification)
- [ ] "Show all stats" adds the extra stat rows; the icon scale slider resizes the launcher between 0.5 and 2.0; "Reset position" re-anchors it (pending user verification)
- [ ] Choosing "Українська" (panel or `/fullbuff lang uk`) turns the whole UI Ukrainian at once, and "English" turns it back; it survives `/reload` (pending user verification)
- [ ] `/fullbuff` toggles the popover, `/fullbuff reset` resets the position and collapsed sections, `/fullbuff debug` lists unknown auras and the stale state, an unknown subcommand prints usage (pending user verification)
- [ ] The settings panel layout has no overlap or overflow in both languages (pending user verification)
