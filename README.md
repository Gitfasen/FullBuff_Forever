# FullBuff

FullBuff is a World of Warcraft: Forever addon that shows which consumable, world and class buffs you are missing and how much each is worth for your class and specialization. It compares your current stats with the theoretical maximum if every recommended buff were applied, ranks buffs by stat weight, and tells you where to get each one (vendors, crafting, quests, camps), with map and minimap pins for sources. The buff database is generated from WoW DB2 data by a Python build pipeline in `tools/`. The UI is available in English and Ukrainian.

## Requirements

- Python 3.12
- `pip install -r requirements-dev.txt`

## Build the database

    python tools/build.py --build 1.60.1.70338

This fetches the DB2 tables and site data into `tools/.cache`, regenerates `addon/FullBuff/Data`, and writes `tools/out/build_report.md`. Use `--offline` to build from the caches only, without any network access (the caches must have been filled by an earlier online run):

    python tools/build.py --build 1.60.1.70338 --offline

## Install

Link the addon into your game folder with a junction. The `-ExecutionPolicy Bypass` applies to this one process only and does not change your system settings:

    powershell -ExecutionPolicy Bypass -File tools/install_junction.ps1

## Tests

    python -m pytest

In-game checks that cannot be automated are listed in `docs/manual-test.md`.

## Usage

- `/fullbuff` toggles the popover
- `/fullbuff options` opens the settings panel (right-clicking the launcher icon or the addon compartment entry does the same)
- `/fullbuff lang en|uk` switches the interface language
- `/fullbuff debug` lists unknown auras and the stale state
- `/fullbuff reset` resets the launcher position and collapsed sections

## Buff sets

A set is a named list of buffs for one situation (for example a raid set and a solo set). Each conflict slot (Intellect, Stamina, flask, food and so on) holds at most one pick, and potions and trinkets are tracked by how many you carry. The popover shows only the active set, with buffs you already have first. Open the settings panel, Sets, to create, copy, rename and delete sets, pick one option per slot (the raid star marks the recommended one, the green tick the one already on you) and choose which burst items to track. A set can be bound to a talent specialization, and then it activates automatically when you switch specialization; the set button in the popover header cycles through the sets by hand. The set maximum counts only the picks of the active set.

## How the maximum is counted

The maximum takes the best buff of every stacking group. Consumables follow a vanilla-style model: one flask, one temporary weapon enchant (oils, stones, imbues, including self-only class imbues such as Rockbiter Weapon), one Well Fed food, and one elixir and one scroll per dominant stat (e.g. one Agility elixir, one Spell damage elixir). Explicit groups in `tools/curated.yaml` (`excl_merge`) override this, e.g. the Rumsey Rum drinks (which stack with Well Fed), the scroll familiars and Spirit of Zanza.

## Known limitations

- The stacking model is an approximation: Forever-specific stacking rules that differ from it need a curated `excl_merge` entry.
- Category ordering in the popover is fixed; user-defined ordering is not implemented yet.
- Mana and health regeneration (MP5, HP5) from gear are not reported by the client; only known active buffs count towards the current value.

## Data sources

- wago.tools DB2 tables (spells, items, effects)
- QuestieDB_Forever (vendor, quest and object locations)
- wowclassicforever.info (Forever-specific items and sources)
- `tools/curated.yaml` (hand-maintained overrides, classification and exclusions)

## License

GPL-3.0, see `LICENSE`.
