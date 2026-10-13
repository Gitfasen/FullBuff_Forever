"""Data records and vocabularies shared by the FullBuff build pipeline."""
from dataclasses import dataclass, field

# The one definition of the stat keys, categories and the burst threshold.
STAT_KEYS = ("STR", "AGI", "STA", "INT", "SPI", "AP", "RAP", "SPELL_DMG", "HEAL", "ARMOR", "HP",
             "MANA", "MP5", "HP5", "CRIT", "SPELL_CRIT", "HIT", "SPELL_HIT", "STAT_PCT", "ARMOR_PCT",
             "STR_PCT", "AGI_PCT", "STA_PCT", "INT_PCT", "SPI_PCT")
CATEGORIES = ("CLASS", "WORLD", "CAMPING", "FLASK", "ELIXIR", "FOOD", "SCROLL", "WEAPON", "QUEST",
              "TRINKET", "POTION")
BURST_MAX = 600  # seconds; burst = 0 < dur < BURST_MAX


@dataclass
class Rank:
    spell: int
    lvl: int
    fx: dict[str, float]


@dataclass
class Source:
    kind: str
    name: str
    mapID: int | None = None
    x: float | None = None
    y: float | None = None
    note: str | None = None


@dataclass
class Buff:
    id: int
    name: str
    cat: str | None
    fx: dict[str, float]
    dur: int
    lvl: int
    excl: str
    items: list[int]
    burst: bool
    new: bool
    cls: str | None = None
    ranks: list[Rank] | None = None
    enchant: int | None = None
    sources: list[Source] = field(default_factory=list)
