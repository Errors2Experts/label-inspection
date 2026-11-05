"""Parse the date formats that appear on Indian food labels (FSS Labelling & Display Regs 2020, Reg 5(10)).

Pure Python (no Django) so the rules engine can be unit-tested on its own.

Accepted: DD/MM/YY, DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY, "05 MAR 2026", "05-MAR-26",
          MM/YYYY, MM/YY, "MAR 2026", "MAR/26", "MARCH-2026".
A date without a day has *month precision*: as a start date it means the 1st, as an end date (expiry) the last day.
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date

MONTHS = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'sept': 9, 'oct': 10, 'nov': 11, 'dec': 12,
}  # fmt: skip
SEP = r'[\s/\-.,]+'
_MON = r'(?P<mon>[A-Za-z]{3,9})'


@dataclass(frozen=True)
class LabelDate:
    year: int
    month: int
    day: int | None  # None => month precision

    @property
    def start(self) -> date:
        return date(self.year, self.month, self.day or 1)

    @property
    def end(self) -> date:
        return date(self.year, self.month, self.day or calendar.monthrange(self.year, self.month)[1])


def _year(raw: str) -> int:
    value = int(raw)
    return 2000 + value if len(raw) <= 2 else value


def _month_from_name(name: str) -> int | None:
    key = name.lower()
    if key in MONTHS:
        return MONTHS[key]
    for full, number in (('january', 1), ('february', 2), ('march', 3), ('april', 4), ('june', 6), ('july', 7),
                         ('august', 8), ('september', 9), ('october', 10), ('november', 11), ('december', 12)):  # fmt: skip
        if full.startswith(key) and len(key) >= 3:
            return number
    return None


_LABEL_PREFIX = re.compile(
    r'^(?:best\s*before|use\s*(?:by|before)|expiry(?:\s*date)?|exp(?:\s*date)?|mfg(?:\s*date)?|mfd(?:\s*date)?|'
    r'pkd(?:\s*date)?|packed(?:\s*on)?|manufactured(?:\s*on)?|date\s*of\s*(?:manufacture|packing))\s*[:\-]?\s*',
    re.I,
)

_PATTERNS = [
    # 05/03/2026, 05-03-26, 5.3.2026
    ('num_full', re.compile(rf'^(?P<d>\d{{1,2}}){SEP}(?P<m>\d{{1,2}}){SEP}(?P<y>\d{{4}}|\d{{2}})$')),
    # 05 MAR 2026, 05-Mar-26
    ('day_mon', re.compile(rf'^(?P<d>\d{{1,2}}){SEP}{_MON}{SEP}(?P<y>\d{{4}}|\d{{2}})$')),
    # 03/2026, 03-26
    ('num_month', re.compile(rf'^(?P<m>\d{{1,2}}){SEP}(?P<y>\d{{4}}|\d{{2}})$')),
    # MAR 2026, MAR/26
    ('mon_year', re.compile(rf'^{_MON}{SEP}(?P<y>\d{{4}}|\d{{2}})$')),
]


def parse_label_date(text: str | None) -> LabelDate | None:
    """Return a LabelDate, or None when the text is empty or not a recognised label date."""
    value = (text or '').strip()
    # Tolerate a leading label such as "EXP:", "Use by", "Best before", "Mfg date -"
    value = _LABEL_PREFIX.sub('', value).strip()
    if not value:
        return None
    for kind, pattern in _PATTERNS:
        match = pattern.match(value)
        if not match:
            continue
        parts = match.groupdict()
        try:
            year = _year(parts['y'])
            if kind == 'num_full':
                day, month = int(parts['d']), int(parts['m'])
            elif kind == 'day_mon':
                day, month = int(parts['d']), _month_from_name(parts['mon'])
            elif kind == 'num_month':
                day, month = None, int(parts['m'])
            else:
                day, month = None, _month_from_name(parts['mon'])
            if not month or not 1 <= month <= 12 or not 1900 <= year <= 2200:
                return None
            if day is not None:
                date(year, month, day)  # validates day-of-month
            return LabelDate(year, month, day)
        except (ValueError, TypeError):
            return None
    return None
