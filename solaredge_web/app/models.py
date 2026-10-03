# Copyright (c) 2026 8ecker.de
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class DayEnergy:
    day: date
    values: dict[str, Decimal]
    resolutions: dict[str, Decimal]


@dataclass
class ScrapeResult:
    values: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
