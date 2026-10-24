"""Map API-Football status short codes to Fixture.Status."""

from apps.matches.models import Fixture

# In-play codes collapsed to LIVE for our model.
_LIVE_CODES = frozenset(
    {
        "1H",
        "2H",
        "ET",
        "BT",
        "P",
        "LIVE",
        "INT",
        "SUSP",
    },
)

_DIRECT = {
    "NS": Fixture.Status.NS,
    "TBD": Fixture.Status.TBD,
    "HT": Fixture.Status.HT,
    "FT": Fixture.Status.FT,
    "AET": Fixture.Status.AET,
    "PEN": Fixture.Status.PEN,
    "PST": Fixture.Status.PST,
    "CANC": Fixture.Status.CANC,
    "ABD": Fixture.Status.ABD,
    "AWD": Fixture.Status.AWD,
    "WO": Fixture.Status.WO,
}


def map_status(short: str | None) -> str:
    """Return Fixture.Status value for an API short code."""
    if not short:
        return Fixture.Status.OTHER
    code = short.upper().strip()
    if code in _DIRECT:
        return _DIRECT[code]
    if code in _LIVE_CODES:
        return Fixture.Status.LIVE
    return Fixture.Status.OTHER
