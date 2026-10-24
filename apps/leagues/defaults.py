"""Default leagues tracked by OverPick."""

from __future__ import annotations

from typing import TypedDict


class LeagueSeed(TypedDict):
    """Seed row for League."""

    api_id: int
    name: str
    country: str
    code: str


# API-Football v3 league ids: 1st + 2nd divisions.
DEFAULT_LEAGUES: list[LeagueSeed] = [
    # England
    {
        "api_id": 39,
        "name": "Premier League",
        "country": "England",
        "code": "PL",
    },
    {
        "api_id": 40,
        "name": "Championship",
        "country": "England",
        "code": "ELC",
    },
    # Germany
    {
        "api_id": 78,
        "name": "Bundesliga",
        "country": "Germany",
        "code": "BL1",
    },
    {
        "api_id": 79,
        "name": "2. Bundesliga",
        "country": "Germany",
        "code": "BL2",
    },
    # France
    {
        "api_id": 61,
        "name": "Ligue 1",
        "country": "France",
        "code": "FL1",
    },
    {
        "api_id": 62,
        "name": "Ligue 2",
        "country": "France",
        "code": "FL2",
    },
    # Italy
    {
        "api_id": 135,
        "name": "Serie A",
        "country": "Italy",
        "code": "SA",
    },
    {
        "api_id": 136,
        "name": "Serie B",
        "country": "Italy",
        "code": "SB",
    },
    # Spain
    {
        "api_id": 140,
        "name": "La Liga",
        "country": "Spain",
        "code": "PD",
    },
    {
        "api_id": 141,
        "name": "Segunda División",
        "country": "Spain",
        "code": "SD",
    },
    # Russia
    {
        "api_id": 235,
        "name": "Premier League",
        "country": "Russia",
        "code": "RFPL",
    },
    {
        "api_id": 236,
        "name": "First League",
        "country": "Russia",
        "code": "RFNL",
    },
    # Netherlands
    {
        "api_id": 88,
        "name": "Eredivisie",
        "country": "Netherlands",
        "code": "DED",
    },
    {
        "api_id": 89,
        "name": "Eerste Divisie",
        "country": "Netherlands",
        "code": "DED2",
    },
    # Austria
    {
        "api_id": 218,
        "name": "Bundesliga",
        "country": "Austria",
        "code": "ABL",
    },
    {
        "api_id": 219,
        "name": "2. Liga",
        "country": "Austria",
        "code": "ABL2",
    },
    # Denmark
    {
        "api_id": 119,
        "name": "Superliga",
        "country": "Denmark",
        "code": "DSL",
    },
    {
        "api_id": 120,
        "name": "1. Division",
        "country": "Denmark",
        "code": "DK2",
    },
    # Argentina
    {
        "api_id": 128,
        "name": "Liga Profesional",
        "country": "Argentina",
        "code": "APL",
    },
    {
        "api_id": 129,
        "name": "Primera Nacional",
        "country": "Argentina",
        "code": "APN",
    },
    # Brazil
    {
        "api_id": 71,
        "name": "Serie A",
        "country": "Brazil",
        "code": "BSA",
    },
    {
        "api_id": 72,
        "name": "Serie B",
        "country": "Brazil",
        "code": "BSB",
    },
    # Kazakhstan
    {
        "api_id": 389,
        "name": "Premier League",
        "country": "Kazakhstan",
        "code": "KPL",
    },
    {
        "api_id": 388,
        "name": "1. Division",
        "country": "Kazakhstan",
        "code": "K1D",
    },
    # Norway
    {
        "api_id": 103,
        "name": "Eliteserien",
        "country": "Norway",
        "code": "NEL",
    },
    {
        "api_id": 104,
        "name": "1. Division",
        "country": "Norway",
        "code": "NOB",
    },
    # Portugal
    {
        "api_id": 94,
        "name": "Primeira Liga",
        "country": "Portugal",
        "code": "PPL",
    },
    {
        "api_id": 95,
        "name": "Segunda Liga",
        "country": "Portugal",
        "code": "PPL2",
    },
    # USA
    {
        "api_id": 253,
        "name": "Major League Soccer",
        "country": "USA",
        "code": "MLS",
    },
    {
        "api_id": 255,
        "name": "USL Championship",
        "country": "USA",
        "code": "USLC",
    },
    # Serbia
    {
        "api_id": 286,
        "name": "Super Liga",
        "country": "Serbia",
        "code": "SSL",
    },
    {
        "api_id": 287,
        "name": "Prva Liga",
        "country": "Serbia",
        "code": "SPL",
    },
    # Turkey
    {
        "api_id": 203,
        "name": "Süper Lig",
        "country": "Turkey",
        "code": "TSL",
    },
    {
        "api_id": 204,
        "name": "1. Lig",
        "country": "Turkey",
        "code": "T1L",
    },
    # Switzerland
    {
        "api_id": 207,
        "name": "Super League",
        "country": "Switzerland",
        "code": "CHSL",
    },
    {
        "api_id": 208,
        "name": "Challenge League",
        "country": "Switzerland",
        "code": "SCL",
    },
    # Sweden
    {
        "api_id": 113,
        "name": "Allsvenskan",
        "country": "Sweden",
        "code": "SAL",
    },
    {
        "api_id": 114,
        "name": "Superettan",
        "country": "Sweden",
        "code": "SSU",
    },
    # Croatia
    {
        "api_id": 210,
        "name": "HNL",
        "country": "Croatia",
        "code": "HNL",
    },
    {
        "api_id": 211,
        "name": "First NL",
        "country": "Croatia",
        "code": "HNL2",
    },
]
