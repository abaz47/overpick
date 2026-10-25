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
    # Belgium
    {
        "api_id": 144,
        "name": "Jupiler Pro League",
        "country": "Belgium",
        "code": "BJL",
    },
    {
        "api_id": 145,
        "name": "Challenger Pro League",
        "country": "Belgium",
        "code": "BCH",
    },
    # Scotland
    {
        "api_id": 179,
        "name": "Premiership",
        "country": "Scotland",
        "code": "SPL",
    },
    {
        "api_id": 180,
        "name": "Championship",
        "country": "Scotland",
        "code": "SCH",
    },
    # Poland
    {
        "api_id": 106,
        "name": "Ekstraklasa",
        "country": "Poland",
        "code": "PEK",
    },
    {
        "api_id": 107,
        "name": "I Liga",
        "country": "Poland",
        "code": "P1L",
    },
    # Czech Republic
    {
        "api_id": 345,
        "name": "Czech Liga",
        "country": "Czech-Republic",
        "code": "CZL",
    },
    {
        "api_id": 346,
        "name": "FNL",
        "country": "Czech-Republic",
        "code": "FNL",
    },
    # Finland
    {
        "api_id": 244,
        "name": "Veikkausliiga",
        "country": "Finland",
        "code": "VEI",
    },
    {
        "api_id": 1087,
        "name": "Ykkösliiga",
        "country": "Finland",
        "code": "YKK",
    },
    # Romania
    {
        "api_id": 283,
        "name": "Liga I",
        "country": "Romania",
        "code": "ROI",
    },
    {
        "api_id": 284,
        "name": "Liga II",
        "country": "Romania",
        "code": "RO2",
    },
    # Greece
    {
        "api_id": 197,
        "name": "Super League 1",
        "country": "Greece",
        "code": "GSL",
    },
    {
        "api_id": 494,
        "name": "Super League 2",
        "country": "Greece",
        "code": "GSL2",
    },
    # Mexico
    {
        "api_id": 262,
        "name": "Liga MX",
        "country": "Mexico",
        "code": "LMX",
    },
    {
        "api_id": 263,
        "name": "Liga de Expansión MX",
        "country": "Mexico",
        "code": "LEX",
    },
    # Japan
    {
        "api_id": 98,
        "name": "J1 League",
        "country": "Japan",
        "code": "J1",
    },
    {
        "api_id": 99,
        "name": "J2 League",
        "country": "Japan",
        "code": "J2",
    },
    # UEFA club competitions (form: all matches; μ: cup)
    {
        "api_id": 2,
        "name": "UEFA Champions League",
        "country": "World",
        "code": "UCL",
    },
    {
        "api_id": 3,
        "name": "UEFA Europa League",
        "country": "World",
        "code": "UEL",
    },
    {
        "api_id": 848,
        "name": "UEFA Europa Conference League",
        "country": "World",
        "code": "UECL",
    },
]
