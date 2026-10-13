# Manual in-game tests

All items below are **pending user verification** (they require running the game client).

## 1. Install and load (Task 8)

Install first: `powershell -ExecutionPolicy Bypass -File tools/install_junction.ps1` (plain `-File` is blocked by this machine's execution policy)

- [ ] Addon appears in the AddOns list at character select as "FullBuff" (pending user verification)
- [ ] After login, `/reload` produces no Lua errors (pending user verification)
