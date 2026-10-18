# FullBuff — Buff Sets Design Spec

Date: 2026-10-13
Status: Draft for review
Builds on: `docs/superpowers/specs/2026-10-13-fullbuff-design.md` (FullBuff v1, merged to `main`)

## 1. Purpose

Let the player build **their own working buff set** — one choice per group of interchangeable buffs — and then simply see **what from that set is missing**. The database and recommendations help choose; the set is what gets tracked.

Example: for Intellect the player picks either Scroll of Intellect, or Arcane Intellect from a mage, or the camp's Boosted Intellect — only one of them works at a time. For food, one food buff. Potions and trinkets are tracked separately by how many are in the bags.

### Success criteria

- A character can have several named sets; one is active; a set can be bound to a spec and switches automatically.
- A new set starts filled with the recommendations (best buff per slot for the spec) and is then edited.
- The editor lists **slots** (conflict groups across categories); each slot offers its interchangeable buffs and "not used"; only one can be picked.
- The popover shows only the stat header (current → maximum **with this set**) and a flat list of the set's buffs: active ✅ first, then missing ❌, then unavailable ⚠️; burst items in a separate block with bag counts.
- A missing buff that is in the bags shows "in bags ×N".

### Decisions

| Topic | Decision |
|---|---|
| Number of sets | Several named sets per character, one active |
| New set | Filled from recommendations, then edited; a set can also be copied |
| Switching | Manual (set dropdown in the popover) plus optional binding of a set to a spec (1–3) that activates it on talent change |
| Editor location | Settings panel (not the popover) |
| Popover | Stats header + flat list of the set (no categories); ✅ first |
| Grouping in editor | By conflict (**slot**), not by category |
| Burst (potions, trinkets) | Separate block; tracked only by count in bags; never in the maximum |
| Bag counts | Shown as ×N; 0 in red |
| Set buff in bags but not active | Row shows "in bags ×N" |
| Buffs from other players | Tracked like any other buff |
| Durations | Not shown |
| Buff in set becomes unavailable | Stays in the set, marked "unavailable — pick a replacement in settings" |
| Reminders | None beyond badge and list |
| Import/export of sets | Out of scope |

## 2. Data: slots

**One concept.** The stacking group (`excl`) used by MaxCalc **is** the slot. Max calculation and the editor share one rule.

### Pipeline changes (`tools/`)

- New `slots:` section in `tools/curated.yaml`; each entry merges existing groups across categories and names the slot:
  ```yaml
  slots:
    - id: INT
      name: {en: Intellect, uk: Інтелект}
      groups: ["CLASS:Arcane Intellect", "SCROLL:INT", "CAMPING:Boosted Intellect"]
  ```
  Group keys refer to the `excl` values produced by the existing pipeline. The build sets `excl = <slot id>` on every buff of those groups. A listed group that matches no buff is a build warning.
- Applied after camping and curated merges (pipeline order: extract → curated → camping → **slots** → questie sources → craft sources → acquisition levels → emit).
- New generated file `addon/FullBuff/Data/Slots.lua`:
  ```lua
  ns.Slots = { [slotId] = { name = { en = "...", uk = "..." }, order = N }, ... }
  ```
  Slots without a curated name get an automatic one from a fixed dictionary (en + uk) built from the category and the dominant stat, e.g. "Elixir — Agility" / "Еліксир — Спритність", "Food" / "Їжа", "Flask" / "Фласка", "Weapon" / "Зброя"; class-family slots use the class buff name. `order` follows the category order then name.
- Every non-burst buff has a slot (its `excl`). Burst buffs are not in slots.
- `build_report.md` gains a "Slots" section: slot id, name, number of options.

### Initial cross-category merges (vanilla Classic rules; to be confirmed in game)

| Slot | Members |
|---|---|
| Intellect | Arcane Intellect / Arcane Brilliance + Scroll of Intellect + Boosted Intellect (camp) |
| Stamina | Power Word: Fortitude / Prayer of Fortitude + Scroll of Stamina + Boosted Stamina (camp) |
| Spirit | Divine Spirit / Prayer of Spirit + Scroll of Spirit + Boosted Spirit (camp) |
| Strength | Scroll of Strength + Extra Strength (camp) |
| Attack power | Blessing of Might / Greater + Boosted Attack Power (camp) — already merged |
| Mana regeneration | Blessing of Wisdom / Greater + Boosted Mana Regeneration (camp) — already merged |
| All stats % | Blessing of Kings / Greater + Boosted Stats % (camp) — already merged |
| All stats | Mark / Gift of the Wild + Boosted Stats (camp) — already merged |

Elixirs and scrolls of the same stat stay **different** slots (they stack in vanilla).

## 3. Engine

### Storage (`FullBuffCharDB`)

```lua
sets = {
  [setId] = {
    name  = "Raid",
    picks = { [slotId] = buffId | false },  -- false = "not used"; absent = empty
    burst = { buffId, ... },                -- tracked burst buffs, in user order
    spec  = nil | 1 | 2 | 3,                -- binding
  },
},
activeSet = setId,
nextSetId = n,
```

- **First load** with no sets: create "Main" ("Основний" when the language is uk) from recommendations and make it active.
- **Recommendations for a new set:** for every slot, the entry `Scoring:MarkRecommended` marks (score > 0, non-burst, available at the player's level); slots with no recommendation stay empty; burst list starts empty.
- **Copy** duplicates picks, burst list and name + " (2)"; binding is not copied.
- **Spec binding:** when PlayerState reports a spec change, the first set bound to the new spec becomes active; otherwise the active set stays. At most one set per spec — binding a set to a spec clears that binding from other sets.
- Deleting the active set activates another; deleting the last set recreates "Main" from recommendations.

### `Engine/Bags.lua`

- `ns.Bags:Count(itemId) -> number` over bags 0–4 via `C_Container.GetContainerNumSlots` / `C_Container.GetContainerItemInfo` (fields `itemID`, `stackCount`).
- Cache rebuilt on `BAG_UPDATE_DELAYED` and `PLAYER_ENTERING_WORLD`, debounced; fires `FULLBUFF_BAGS`. Readable in combat. Missing API → counts 0 and one debug note.
- `ns.Bags:CountBuff(buff) -> number` = sum over `buff.items`.

### `Engine/Sets.lua`

CRUD and active-set logic above: `List()`, `Get(id)`, `Active()`, `SetActive(id)`, `Create(name) -> id` (from recommendations), `Copy(id) -> id`, `Rename(id, name)`, `Delete(id)`, `Pick(id, slotId, buffId|false|nil)`, `AddBurst(id, buffId)`, `RemoveBurst(id, buffId)`, `MoveBurst(id, buffId, delta)`, `BindSpec(id, spec|nil)`. Every change fires `FULLBUFF_SET`.

### `Engine/SetTracker.lua`

`ns.SetTracker:Evaluate(state, catalog, set) -> { rows, burst, missingCount, unavailableCount }`

- `rows` — one per picked slot (`picks[slot]` is a buffId):
  `{ slot, buffId, name, icon, valueText, status = "ACTIVE"|"MISSING"|"UNAVAILABLE", bagCount }`.
  - ACTIVE: the buff (any rank / its `aura`) is on the player — reuses Catalog status ACTIVE.
  - MISSING: obtainable (Catalog CAN_ADD) and not active; also the "upgrade available" case.
  - UNAVAILABLE: not in `ns.Buffs`, not in the Catalog (wrong class for a self-only buff) or Catalog UNAVAILABLE (level).
  - Order: ACTIVE, MISSING, UNAVAILABLE; within each, slot `order`.
- `burst` — one per tracked burst buff: `{ buffId, name, icon, bagCount }`, in user order.
- `missingCount` = MISSING rows + burst entries with `bagCount == 0`. UNAVAILABLE rows are not counted.

### MaxCalc with a set

`ns.MaxCalc:Compute(state, catalog, picks)` — when `picks` is given, the chosen entry of each slot is the picked buff if its status is ACTIVE or CAN_ADD (never UNAVAILABLE, never burst), instead of the recommendation. A slot set to `false` ("not used") or empty has no chosen entry; an active buff in such a slot is not subtracted (existing rule: subtract only in groups with a chosen entry). Without `picks` behaviour is unchanged (used for recommendations).

## 4. UI

### Popover (replaces the category view)

- **Header:** set dropdown (switch active set), class/spec/level, stale note, stat table `current → max (+diff)` computed with the active set.
- **List:** flat, no categories; rows from `SetTracker` rows:
  - ✅ ACTIVE — ready-check tick, green name.
  - ❌ MISSING — name in normal colour, value text; "in bags ×N" when `bagCount > 0`; click opens the existing DetailCard (sources, pins).
  - ⚠️ UNAVAILABLE — grey, "unavailable — pick a replacement in settings".
- **Burst block** (title "Potions & trinkets"): icon, name, `×N`; `×0` in red.
- Empty set → one line "Set is empty — configure it in settings" with a button opening the options.
- "Show only missing" checkbox removed (the list is already the set); `ns.DB.onlyMissing` and `ns.DB.hiddenCats` become unused and are removed from defaults and options.

### Launcher

Badge = `missingCount`; tooltip: set name, percent of max, missing names (burst at 0 included).

### Options — "Sets" section

- **Set bar:** dropdown of sets, buttons New, Copy, Rename, Delete, "Bind to spec" (None / tree 1 / 2 / 3 with tree names).
- **Slots list:** scrollable; each slot is a header (slot name) with radio options:
  - each available buff of the slot (Catalog CAN_ADD or ACTIVE for this character): icon, name, value text, raid-star when it is the recommendation, "active" tick when it is on the player;
  - "Not used";
  - a picked buff that is now unavailable stays listed and selected, greyed, marked "unavailable".
  Buffs not available at the player's level are not offered.
- **Burst list:** all burst buffs available to the character with a checkbox each (tracked / not), plus bag count; tracked ones can be reordered (up/down).
- Existing options stay (spec override, weights, show all stats, scale, reset, language). Category visibility is removed.

### Strings

All new strings in `Locales/enUS.lua` and `Locales/ukUA.lua` (real Ukrainian, key parity and Cyrillic tests). Slot names come from `ns.Slots[id].name[lang]`.

## 5. Error handling

- Saved picks referencing unknown buff or slot ids (after a data rebuild) are kept and shown as UNAVAILABLE; never deleted automatically.
- Bag API missing or failing → counts 0, one debug line via `/fullbuff debug`.
- Combat / secret values: unchanged rules; the list keeps the last snapshot marked stale. Bag counts update in combat.
- All handlers isolated through the existing event system.

## 6. Testing

- **Pipeline (pytest):** slot merges set the same `excl` across categories; unknown group → warning; auto names en/uk; `Slots.lua` emitted and loadable; real-data test: Arcane Intellect, Scroll of Intellect and Boosted Intellect share one slot; elixir and scroll of Agility are different slots.
- **Addon (pytest + lupa):** Sets CRUD, first-load "Main" from recommendations, copy, delete-last recreates, spec binding switch and uniqueness; Bags counting from mocked `C_Container`; SetTracker statuses/order/bag counts/missingCount; MaxCalc with picks (picked beats recommendation, "not used" leaves active buff, unavailable pick ignored); popover rows and burst block; options slot radio and burst checkboxes drive `Sets`; locale parity.
- **In game (manual, added to `docs/manual-test.md`):** create/switch sets, spec binding on talent change, bag counts update after using a potion, "in bags ×N" for an elixir, unavailable marker after a level-gated pick.

## 7. Out of scope

Import/export of sets; reminders/alerts; duration display; account-wide sets; per-hand weapon slots; auto-use of items.
