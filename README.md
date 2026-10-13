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
- `/fullbuff options` opens the settings panel (right-clicking the launcher icon does the same)
- `/fullbuff lang en|uk` switches the interface language
- `/fullbuff debug` lists unknown auras and the stale state
- `/fullbuff reset` resets the launcher position and collapsed sections

## Data sources

- wago.tools DB2 tables (spells, items, effects)
- QuestieDB_Forever (vendor, quest and object locations)
- wowclassicforever.info (Forever-specific items and sources)
- `tools/curated.yaml` (hand-maintained overrides, classification and exclusions)

## License

GPL-3.0, see `LICENSE`.
