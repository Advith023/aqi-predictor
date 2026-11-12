# AQI Predictor by Advith Ashok (github.com/Advith023/aqi-predictor). Copyright (c) 2026 Advith Ashok. All rights reserved. Not licensed for reuse; see LICENSE.
"""India CPCB National AQI categories."""
from bisect import bisect_left

# Upper bound (inclusive) of each category; anything above 400 is Severe.
_UPPER = [50, 100, 200, 300, 400]
CATEGORIES = ["Good", "Satisfactory", "Moderate", "Poor", "Very Poor", "Severe"]


def aqi_category(aqi: float) -> str:
    """Map an AQI value to its CPCB category.

    Boundaries are inclusive at the top (50 -> Good, 51 -> Satisfactory),
    fractional values are handled (50.4 -> Satisfactory) and values above
    400 are Severe.
    """
    if aqi is None or aqi != aqi or aqi < 0:  # None, NaN, negative
        raise ValueError(f"Invalid AQI value: {aqi!r}")
    return CATEGORIES[bisect_left(_UPPER, aqi)]
