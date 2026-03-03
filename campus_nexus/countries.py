from __future__ import annotations

from pathlib import Path


ISO3166_TAB_PATH = Path("/usr/share/zoneinfo/iso3166.tab")

FALLBACK_COUNTRY_NAMES = [
    "Uganda",
    "Kenya",
    "Tanzania",
    "Rwanda",
    "Burundi",
    "South Sudan",
    "Democratic Republic of the Congo",
    "Nigeria",
    "Ghana",
    "South Africa",
    "Egypt",
    "Sudan",
    "Ethiopia",
    "United States",
    "United Kingdom",
    "Canada",
    "India",
    "Pakistan",
    "Bangladesh",
    "China",
    "Japan",
    "Germany",
    "France",
    "Italy",
    "Spain",
    "Saudi Arabia",
    "United Arab Emirates",
    "Qatar",
    "Australia",
    "New Zealand",
]


def _load_country_names() -> list[str]:
    if ISO3166_TAB_PATH.exists():
        country_names: list[str] = []
        with ISO3166_TAB_PATH.open(encoding="utf-8") as source:
            for line in source:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t", 1)
                if len(parts) != 2:
                    continue
                country_names.append(parts[1].strip())
        if country_names:
            return sorted(dict.fromkeys(country_names))
    return sorted(FALLBACK_COUNTRY_NAMES)


COUNTRY_CHOICES = [("", "Select country")] + [(name, name) for name in _load_country_names()]

# Case-insensitive lookup to normalize imported CSV values.
COUNTRY_LOOKUP = {name.lower(): name for _, name in COUNTRY_CHOICES if name}

