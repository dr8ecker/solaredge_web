# Copyright (c) 2026 8ecker.de
"""Strict visible-text quantities. Never turn a parse failure into zero."""

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


class ParseError(ValueError):
    pass


@dataclass(frozen=True)
class Quantity:
    value: Decimal
    unit: str
    resolution: Decimal


class ValueParser:
    PATTERN = re.compile(r"(?<![\w.,])([-+]?\d+(?:[.,\s\u00a0\u202f]\d+)*)\s*(MWh|kWh|Wh|MW|kW|W|%|[°˚º]C|V|Hz)(?![\w/])", re.I)
    UNITS = {"w": ("W", 1), "kw": ("W", 1000), "mw": ("W", 1000000),
             "wh": ("kWh", Decimal("0.001")), "kwh": ("kWh", 1), "mwh": ("kWh", 1000),
             "%": ("%", 1), "°c": ("°C", 1), "˚c": ("°C", 1), "ºc": ("°C", 1),
             "v": ("V", 1), "hz": ("Hz", 1)}

    @staticmethod
    def number(text: str) -> tuple[Decimal, int]:
        text = re.sub(r"\s", "", text)
        if ',' in text and '.' in text:
            # The last separator is decimal, the other must be valid grouping.
            decimal = ',' if text.rfind(',') > text.rfind('.') else '.'
            grouping = '.' if decimal == ',' else ','
            integer, fraction = text.rsplit(decimal, 1)
            if not re.fullmatch(r"[-+]?\d{1,3}(?:" + re.escape(grouping) + r"\d{3})+", integer):
                raise ParseError("Invalid numeric grouping")
            text = integer.replace(grouping, '') + '.' + fraction
        elif text.count('.') > 1 or text.count(',') > 1:
            # Ambiguous single-separator grouping is deliberately rejected.
            raise ParseError("Ambiguous numeric separators")
        else:
            text = text.replace(',', '.')
        try:
            value = Decimal(text)
        except InvalidOperation:
            raise ParseError("Invalid number") from None
        if not value.is_finite():
            raise ParseError("Nonfinite number")
        return value, len(text.split('.')[1]) if '.' in text else 0

    @classmethod
    def quantities(cls, text: str, unit: str | None = None) -> list[Quantity]:
        result = []
        for match in cls.PATTERN.finditer(text):
            value, places = cls.number(match.group(1))
            normalized, multiplier = cls.UNITS[match.group(2).lower()]
            if unit and normalized != unit:
                continue
            multiplier = Decimal(multiplier)
            result.append(Quantity(value * multiplier, normalized, Decimal(10) ** -places * multiplier))
        return result

    @classmethod
    def parse(cls, text: str, unit: str) -> Quantity:
        matches = cls.quantities(text, unit)
        if len(matches) != 1:
            raise ParseError("Expected one unambiguous quantity")
        item = matches[0]
        if unit == '°C':
            if not Decimal(-50) <= item.value <= Decimal(80):
                raise ParseError("Temperature out of range")
        elif item.value < 0:
            raise ParseError("Negative quantity")
        if unit == '%' and item.value > 100:
            raise ParseError("Percentage out of range")
        return item
