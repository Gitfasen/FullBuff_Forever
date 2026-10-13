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
