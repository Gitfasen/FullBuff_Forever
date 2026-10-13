"""Download and cache DB2 CSV tables from wago.tools."""
import csv
import urllib.request
from pathlib import Path
from typing import Callable

DB2_TABLES = [
    "SpellName", "Spell", "SpellEffect", "SpellMisc", "SpellDuration",
    "SpellLevels", "SpellClassOptions", "SpellCategories", "SkillLineAbility",
    "ItemEffect", "ItemXItemEffect", "Item", "ItemSparse",
    "SpellItemEnchantment", "UiMapAssignment",
]

URL_TEMPLATE = "https://wago.tools/db2/{table}/csv?build={build}"


def default_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "FullBuff-build"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def fetch_tables(
    build: str,
    tables: list[str],
    cache_dir: Path,
    http_get: Callable[[str], bytes] = default_get,
) -> dict[str, Path]:
    """Ensure each table's CSV is cached under cache_dir/<build>/; return paths."""
    out_dir = Path(cache_dir) / build
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for table in tables:
        path = out_dir / f"{table}.csv"
        if not path.exists():
            data = http_get(URL_TEMPLATE.format(table=table, build=build))
            tmp = path.with_suffix(".csv.part")
            tmp.write_bytes(data)
            tmp.replace(path)
        paths[table] = path
    return paths


def read_table(path: Path) -> list[dict[str, str]]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))
