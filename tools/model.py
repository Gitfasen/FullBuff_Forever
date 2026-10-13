"""Data records shared by the FullBuff build pipeline."""
from dataclasses import dataclass, field


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
