"""
Swiss Ephemeris Python API Server
Copyright (C) 2025 Triple Moon Goddess Astrology
Contact: Lisa@triplemoongoddess.com

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program. If not, see <https://www.gnu.org/licenses/>.

This software uses Swiss Ephemeris, Copyright (C) 1997-2021 Astrodienst AG.
Swiss Ephemeris is licensed under AGPL-3.0.
Website: https://www.astro.com/swisseph/
"""

from fastapi import FastAPI, HTTPException, Security, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, field_validator, ValidationError
import swisseph as swe
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Optional, List, Dict
from timezonefinder import TimezoneFinder
import pytz
import os
import logging
import hashlib
import hmac

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(title="Swiss Ephemeris API", version="1.0.0")

# API Key Security (transitional)
#
# Callers authenticate to this service with a Google-signed OIDC identity token
# (audience = this service's URL) that Cloud Run's IAM front door verifies before
# a request reaches this process. The static X-API-Key below is the legacy
# second check kept only until `allUsers` is removed from the service's invoker
# policy; it is then deleted along with the SWISS_EPH_API_KEY secret.
#
# There is deliberately NO default value: a deployment without API_KEY must fail
# at startup rather than silently accept a well-known placeholder key.
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise RuntimeError("API_KEY environment variable is not set — refusing to start with no credential.")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(api_key: str = Security(api_key_header)):
    """Verify the API key from request header (constant-time compare)."""
    if api_key is None:
        logger.warning("API key missing")
        raise HTTPException(status_code=403, detail="API key is missing")

    if not hmac.compare_digest(api_key.encode("utf-8"), API_KEY.encode("utf-8")):
        logger.warning("Invalid API key attempt")
        raise HTTPException(status_code=403, detail="Invalid API key")

    return api_key

# CORS Configuration
# Google Apps Script makes server-to-server requests and may not send Origin headers
# Allow all origins but enforce API key authentication for security
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # API key authentication provides security
    allow_credentials=False,  # Not needed for API key auth
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Key"],
)

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to all responses"""
    response = await call_next(request)

    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    return response

# Set ephemeris path
import os

# Set the ephemeris path to our data directory
# Swiss Ephemeris uses the SE_EPHE_PATH environment variable
EPHE_PATH = '/app/ephe'
if os.path.exists(EPHE_PATH):
    os.environ['SE_EPHE_PATH'] = EPHE_PATH
    swe.set_ephe_path(EPHE_PATH)
    print(f"Ephemeris path set to: {EPHE_PATH}")
else:
    # Fallback to pyswisseph package data
    package_path = os.path.join(os.path.dirname(swe.__file__), 'data')
    if os.path.exists(package_path):
        os.environ['SE_EPHE_PATH'] = package_path
        swe.set_ephe_path(package_path)
        print(f"Ephemeris path set to: {package_path}")
    else:
        print("Warning: No ephemeris path found, using swisseph defaults")

# Constants
SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
]

PLANETS = {
    "sun": swe.SUN,
    "moon": swe.MOON,
    "mercury": swe.MERCURY,
    "venus": swe.VENUS,
    "mars": swe.MARS,
    "jupiter": swe.JUPITER,
    "saturn": swe.SATURN,
    "uranus": swe.URANUS,
    "neptune": swe.NEPTUNE,
    "pluto": swe.PLUTO,
    "true_node": swe.TRUE_NODE,
    "chiron": 15,  # SE_CHIRON
    "ceres": 17,   # SE_CERES
    "pallas": 18,  # SE_PALLAS
    "juno": 19,    # SE_JUNO
    "vesta": 20,   # SE_VESTA
    "lilith": swe.OSCU_APOG  # Black Moon Lilith (True/Osculating)
}

HOUSE_SYSTEMS = {
    "placidus": b"P",
    "whole_sign": b"W",
    "koch": b"K",
    "equal": b"E",
    "campanus": b"C"
}

# Request models with validation
class ChartRequest(BaseModel):
    year: int
    month: int
    day: int
    hour: int
    min: int
    lat: float
    lon: float
    house_type: Optional[str] = "placidus"

    @field_validator('year')
    @classmethod
    def validate_year(cls, v):
        if v < 1800 or v > 2200:
            raise ValueError('Year must be between 1800 and 2200')
        return v

    @field_validator('month')
    @classmethod
    def validate_month(cls, v):
        if v < 1 or v > 12:
            raise ValueError('Month must be between 1 and 12')
        return v

    @field_validator('day')
    @classmethod
    def validate_day(cls, v):
        if v < 1 or v > 31:
            raise ValueError('Day must be between 1 and 31')
        return v

    @field_validator('hour')
    @classmethod
    def validate_hour(cls, v):
        if v < 0 or v > 23:
            raise ValueError('Hour must be between 0 and 23')
        return v

    @field_validator('min')
    @classmethod
    def validate_min(cls, v):
        if v < 0 or v > 59:
            raise ValueError('Minute must be between 0 and 59')
        return v

    @field_validator('lat')
    @classmethod
    def validate_lat(cls, v):
        if v < -90 or v > 90:
            raise ValueError('Latitude must be between -90 and 90')
        return v

    @field_validator('lon')
    @classmethod
    def validate_lon(cls, v):
        if v < -180 or v > 180:
            raise ValueError('Longitude must be between -180 and 180')
        return v

    @field_validator('house_type')
    @classmethod
    def validate_house_type(cls, v):
        valid_types = ['placidus', 'whole_sign', 'koch', 'equal', 'campanus']
        if v not in valid_types:
            raise ValueError(f'House type must be one of: {", ".join(valid_types)}')
        return v

# Helper functions

# Stationary thresholds in degrees/day - planets moving slower than this are considered stationary
# Values based on typical apparent motion at station points
STATIONARY_THRESHOLDS = {
    "sun": 0.0,       # Sun never stations
    "moon": 0.0,      # Moon never stations
    "mercury": 0.08,  # ~0.08°/day or less at station
    "venus": 0.06,    # ~0.06°/day or less at station
    "mars": 0.03,     # ~0.03°/day or less at station
    "jupiter": 0.015, # ~0.015°/day or less at station
    "saturn": 0.008,  # ~0.008°/day or less at station
    "uranus": 0.004,  # ~0.004°/day or less at station
    "neptune": 0.002, # ~0.002°/day or less at station
    "pluto": 0.002,   # ~0.002°/day or less at station
    "chiron": 0.01,   # Estimated
    "north_node": 0.0,  # Nodes don't station the same way
    "south_node": 0.0,
}

def is_stationary(planet_name: str, speed: float) -> bool:
    """
    Determine if a planet is stationary based on its speed.
    A planet is stationary when its apparent motion is near zero,
    typically just before or after turning retrograde/direct.
    """
    threshold = STATIONARY_THRESHOLDS.get(planet_name.lower(), 0.02)
    if threshold == 0.0:
        return False  # Sun, Moon, and nodes don't station
    return abs(speed) < threshold

def lon_to_sign_degree(lon: float):
    """Convert longitude to sign and degree"""
    lon = lon % 360.0
    sign_index = int(lon // 30.0)
    degree = lon - (sign_index * 30.0)
    return {
        "sign": SIGNS[sign_index],
        "degree": degree,
        "full_degree": lon
    }

def calculate_julian_day(year: int, month: int, day: int, hour: int, minute: int, lat: float = None, lon: float = None):
    """Calculate Julian Day - converts local time to UTC if lat/lon provided"""
    if lat is not None and lon is not None:
        # Find timezone and convert local time to UTC
        tf = TimezoneFinder()
        tz_name = tf.timezone_at(lat=lat, lng=lon)

        if tz_name:
            try:
                local_tz = pytz.timezone(tz_name)
                local_dt = local_tz.localize(datetime(year, month, day, hour, minute))
                utc_dt = local_dt.astimezone(pytz.utc)

                decimal_hour = utc_dt.hour + utc_dt.minute / 60.0 + utc_dt.second / 3600.0
                return swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, decimal_hour, swe.GREG_CAL)
            except Exception as e:
                print(f"Timezone conversion failed: {e}, using local time as-is")

    # Fallback: treat as UTC or no timezone info
    decimal_hour = hour + minute / 60.0
    return swe.julday(year, month, day, decimal_hour, swe.GREG_CAL)

def calculate_houses_for_jd(jd: float, lat: float, lon: float, house_system: str = "placidus"):
    """Calculate houses for a given Julian Day and location"""
    house_sys = HOUSE_SYSTEMS.get(house_system, b"P")
    cusps, ascmc = swe.houses(jd, lat, lon, house_sys)

    houses_data = {}

    # Add ascendant and midheaven
    asc_data = lon_to_sign_degree(ascmc[0])
    mc_data = lon_to_sign_degree(ascmc[1])

    houses_data["ascendant"] = {
        "longitude": round(ascmc[0], 6),
        "sign": asc_data["sign"],
        "degree": round(asc_data["degree"], 4)
    }

    houses_data["midheaven"] = {
        "longitude": round(ascmc[1], 6),
        "sign": mc_data["sign"],
        "degree": round(mc_data["degree"], 4)
    }

    # Add all 12 houses
    for i in range(12):
        house_lon = cusps[i]
        house_data = lon_to_sign_degree(house_lon)
        houses_data[f"house{i+1}"] = {
            "longitude": round(house_lon, 6),
            "sign": house_data["sign"],
            "degree": round(house_data["degree"], 4)
        }

    return houses_data, cusps

def get_planet_house(planet_lon: float, house_cusps) -> int:
    """Determine which house a planet is in based on its longitude and house cusps"""
    planet_lon = planet_lon % 360.0

    for i in range(12):
        cusp_start = house_cusps[i] % 360.0
        cusp_end = house_cusps[(i + 1) % 12] % 360.0

        # Handle wrap-around at 0/360 degrees
        if cusp_start < cusp_end:
            if cusp_start <= planet_lon < cusp_end:
                return i + 1
        else:  # Wraps around 0 degrees
            if planet_lon >= cusp_start or planet_lon < cusp_end:
                return i + 1

    return 1  # Default to house 1 if not found

def get_whole_sign_house(planet_lon: float, ascendant_lon: float) -> int:
    """Determine which whole sign house a planet is in"""
    # Get the signs (0-11) for planet and ascendant
    planet_sign = int((planet_lon % 360.0) // 30)
    asc_sign = int((ascendant_lon % 360.0) // 30)

    # Calculate house number (1-12)
    # In whole sign: if ASC is in Aries (0), then Aries=1st house, Taurus=2nd, etc.
    house_num = ((planet_sign - asc_sign) % 12) + 1

    return house_num

# API Endpoints
@app.get("/")
def root():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "Swiss Ephemeris API",
        "version": "1.0.0",
        "endpoints": {
            "planets": "/api/planets",
            "houses": "/api/houses",
            "chart": "/api/chart"
        }
    }

@app.post("/api/planets")
def get_planets(request: ChartRequest, api_key: str = Security(verify_api_key)):
    """Get planetary positions"""
    # Never log the request: its date, time and place are a person's birth data.
    logger.info("Planets calculation requested")
    try:
        # Calculate Julian Day (with timezone conversion based on location)
        jd = calculate_julian_day(request.year, request.month, request.day,
                                 request.hour, request.min, request.lat, request.lon)

        result = {}

        # Calculate each planet
        for name, planet_id in PLANETS.items():
            try:
                # All bodies use Swiss Ephemeris with .se1 files
                xx, ret = swe.calc_ut(jd, planet_id, swe.FLG_SWIEPH | swe.FLG_SPEED)

                longitude = xx[0]
                speed = xx[3]
                sign_data = lon_to_sign_degree(longitude)

                result[name] = {
                    "longitude": longitude,
                    "full_degree": sign_data["full_degree"],
                    "normDegree": sign_data["full_degree"],
                    "sign": sign_data["sign"],
                    "degree": sign_data["degree"],
                    "speed": speed,
                    "isRetro": "true" if speed < 0 else "false",
                    "isStationary": "true" if is_stationary(name, speed) else "false"
                }
            except Exception as e:
                import traceback
                print(f"ERROR calculating {name} (id={planet_id}): {e}")
                print(f"Full traceback: {traceback.format_exc()}")
                # Also check if files exist
                import os
                print(f"Ephemeris path set to: {swe.get_library_path()}")
                if name in ["chiron", "ceres", "pallas", "juno", "vesta"]:
                    ast_dir = "ast0" if name != "chiron" else "ast2"
                    file_path = f"/app/ephe/{ast_dir}/se{planet_id:05d}.se1"
                    print(f"  Looking for: {file_path}, exists={os.path.exists(file_path)}")
                continue

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating planets: {str(e)}")

@app.post("/api/houses")
def get_houses(request: ChartRequest, api_key: str = Security(verify_api_key)):
    """Get house cusps"""
    logger.info("Houses calculation requested")  # no birth data in logs
    try:
        # Calculate Julian Day (with timezone conversion based on location)
        jd = calculate_julian_day(request.year, request.month, request.day,
                                 request.hour, request.min, request.lat, request.lon)

        # Calculate houses (now returns cusps too)
        houses_data, cusps = calculate_houses_for_jd(jd, request.lat, request.lon, request.house_type)

        # Return in the original format
        result = {}

        # Add ascendant and midheaven
        result["ascendant"] = {
            "longitude": houses_data["ascendant"]["longitude"],
            "full_degree": houses_data["ascendant"]["longitude"],
            **houses_data["ascendant"]
        }

        result["midheaven"] = {
            "longitude": houses_data["midheaven"]["longitude"],
            "full_degree": houses_data["midheaven"]["longitude"],
            **houses_data["midheaven"]
        }

        # Add all 12 houses
        for i in range(12):
            house_key = f"house{i+1}"
            result[house_key] = {
                "longitude": houses_data[house_key]["longitude"],
                "full_degree": houses_data[house_key]["longitude"],
                **houses_data[house_key]
            }

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating houses: {str(e)}")

@app.post("/api/chart")
def get_chart(request: ChartRequest, api_key: str = Security(verify_api_key)):
    """Get complete chart data (planets + houses)"""
    logger.info("Complete chart requested")  # no birth data in logs
    try:
        # Calculate Julian Day
        jd = calculate_julian_day(request.year, request.month, request.day,
                                 request.hour, request.min, request.lat, request.lon)

        # Get planets
        planets = {}
        for name, planet_id in PLANETS.items():
            try:
                xx, ret = swe.calc_ut(jd, planet_id, swe.FLG_SWIEPH | swe.FLG_SPEED)
                longitude = xx[0]
                speed = xx[3]
                sign_data = lon_to_sign_degree(longitude)

                planets[name] = {
                    "longitude": longitude,
                    "full_degree": sign_data["full_degree"],
                    "normDegree": sign_data["full_degree"],
                    "sign": sign_data["sign"],
                    "degree": sign_data["degree"],
                    "speed": speed,
                    "isRetro": "true" if speed < 0 else "false",
                    "isStationary": "true" if is_stationary(name, speed) else "false"
                }
            except:
                continue

        # Get houses
        houses_data, cusps = calculate_houses_for_jd(jd, request.lat, request.lon, request.house_type)

        houses = {}
        houses["ascendant"] = {
            "longitude": houses_data["ascendant"]["longitude"],
            "full_degree": houses_data["ascendant"]["longitude"],
            **houses_data["ascendant"]
        }
        houses["midheaven"] = {
            "longitude": houses_data["midheaven"]["longitude"],
            "full_degree": houses_data["midheaven"]["longitude"],
            **houses_data["midheaven"]
        }
        for i in range(12):
            house_key = f"house{i+1}"
            houses[house_key] = {
                "longitude": houses_data[house_key]["longitude"],
                "full_degree": houses_data[house_key]["longitude"],
                **houses_data[house_key]
            }

        return {
            "planets": planets,
            "houses": houses
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating chart: {str(e)}")

# Transit Request Model with validation
class TransitRequest(BaseModel):
    natal_positions: Dict[str, float]  # e.g., {"Sun": 26.57, "Moon": 109.35, ...}
    start_date: str  # ISO format: "2025-12-17"
    end_date: str    # ISO format: "2026-12-17"
    lat: float
    lon: float
    # Birth data for natal houses
    birth_year: int
    birth_month: int
    birth_day: int
    birth_hour: int
    birth_min: int
    house_type: Optional[str] = "placidus"
    transiting_planets: Optional[List[str]] = ["jupiter", "saturn", "uranus", "neptune", "pluto"]
    aspects: Optional[Dict[str, Dict]] = {
        "Conjunction": {"angle": 0, "orb": 1.0},
        "Square": {"angle": 90, "orb": 1.0},
        "Opposition": {"angle": 180, "orb": 1.0},
        "Quincunx": {"angle": 150, "orb": 1.0}
    }
    step_days: Optional[int] = 7

    @field_validator('natal_positions')
    @classmethod
    def validate_natal_positions(cls, v):
        if not v or len(v) == 0:
            raise ValueError('Natal positions cannot be empty')
        for planet, lon in v.items():
            if lon < 0 or lon > 360:
                raise ValueError(f'{planet} longitude must be between 0 and 360')
        return v

    @field_validator('start_date', 'end_date')
    @classmethod
    def validate_date(cls, v):
        try:
            datetime.fromisoformat(v)
        except ValueError:
            raise ValueError('Date must be in ISO format (YYYY-MM-DD)')
        return v

    @field_validator('lat')
    @classmethod
    def validate_lat(cls, v):
        if v < -90 or v > 90:
            raise ValueError('Latitude must be between -90 and 90')
        return v

    @field_validator('lon')
    @classmethod
    def validate_lon(cls, v):
        if v < -180 or v > 180:
            raise ValueError('Longitude must be between -180 and 180')
        return v

    @field_validator('birth_year')
    @classmethod
    def validate_birth_year(cls, v):
        if v < 1800 or v > 2200:
            raise ValueError('Birth year must be between 1800 and 2200')
        return v

    @field_validator('birth_month')
    @classmethod
    def validate_birth_month(cls, v):
        if v < 1 or v > 12:
            raise ValueError('Birth month must be between 1 and 12')
        return v

    @field_validator('birth_day')
    @classmethod
    def validate_birth_day(cls, v):
        if v < 1 or v > 31:
            raise ValueError('Birth day must be between 1 and 31')
        return v

    @field_validator('birth_hour')
    @classmethod
    def validate_birth_hour(cls, v):
        if v < 0 or v > 23:
            raise ValueError('Birth hour must be between 0 and 23')
        return v

    @field_validator('birth_min')
    @classmethod
    def validate_birth_min(cls, v):
        if v < 0 or v > 59:
            raise ValueError('Birth minute must be between 0 and 59')
        return v

    @field_validator('step_days')
    @classmethod
    def validate_step_days(cls, v):
        if v and (v < 1 or v > 30):
            raise ValueError('Step days must be between 1 and 30')
        return v

def angle_separation(lon1: float, lon2: float) -> float:
    """Calculate angle separation between two longitudes"""
    diff = abs((lon1 - lon2) % 360)
    return diff if diff <= 180 else 360 - diff

@lru_cache(maxsize=262144)
def get_transit_lon(jd: float, planet_id: int) -> float:
    """Get transit planet longitude at Julian Day.

    Cached: the transit scan walks an identical JD sequence once per natal
    position and aspect, so without the cache each planet's ephemeris is
    recomputed ~50x per step. Cache keys are exact float reuses, so hits are
    bit-identical — results are unchanged, only repeated work is skipped.
    """
    xx, _ = swe.calc_ut(jd, planet_id, swe.FLG_SWIEPH | swe.FLG_SPEED)
    return xx[0]

def sep_func(jd: float, natal_lon: float, planet_id: int) -> float:
    """Calculate separation between transit and natal planet"""
    return angle_separation(get_transit_lon(jd, planet_id), natal_lon)

def gfunc(jd: float, natal_lon: float, planet_id: int, angle: float) -> float:
    """Function for finding aspect crossings"""
    return angle_separation(get_transit_lon(jd, planet_id), natal_lon) - angle

def bisect_root(j1: float, j2: float, natal_lon: float, planet_id: int, angle: float, tol: float = 1e-5) -> float:
    """Find exact aspect using bisection method"""
    f1 = gfunc(j1, natal_lon, planet_id, angle)
    f2 = gfunc(j2, natal_lon, planet_id, angle)

    if f1 == 0.0:
        return j1
    if f2 == 0.0:
        return j2
    if f1 * f2 > 0:
        return None

    a, b = j1, j2
    for _ in range(60):
        m = (a + b) / 2.0
        fm = gfunc(m, natal_lon, planet_id, angle)
        if abs(fm) < tol:
            return m
        if f1 * fm <= 0:
            b = m
            f2 = fm
        else:
            a = m
            f1 = fm
    return (a + b) / 2.0

def find_min_sep_jd(j1: float, j2: float, natal_lon: float, planet_id: int) -> float:
    """Find local minimum separation using ternary search"""
    a, b = j1, j2
    for _ in range(40):
        m1 = a + (b - a) / 3.0
        m2 = b - (b - a) / 3.0
        f1 = sep_func(m1, natal_lon, planet_id)
        f2 = sep_func(m2, natal_lon, planet_id)
        if f1 < f2:
            b = m2
        else:
            a = m1
    return (a + b) / 2.0

@app.post("/api/transits")
def get_transits(request: TransitRequest, api_key: str = Security(verify_api_key)):
    """Calculate exact transits using precision algorithms"""
    logger.info(f"Transit calculation requested: {request.start_date} to {request.end_date}")
    try:
        transits = []

        # Calculate natal houses and get cusps
        natal_jd = calculate_julian_day(
            request.birth_year, request.birth_month, request.birth_day,
            request.birth_hour, request.birth_min, request.lat, request.lon
        )
        natal_houses, natal_cusps = calculate_houses_for_jd(natal_jd, request.lat, request.lon, request.house_type)

        # Parse dates and convert to Julian Days
        start_dt = datetime.fromisoformat(request.start_date)
        end_dt = datetime.fromisoformat(request.end_date)

        start_jd = swe.julday(start_dt.year, start_dt.month, start_dt.day, 0.0, swe.GREG_CAL)
        end_jd = swe.julday(end_dt.year, end_dt.month, end_dt.day, 0.0, swe.GREG_CAL)

        # Planet IDs. The Moon is included for short-window daily scans
        # (TMG daily Moon reading) — callers keep long-window scans to the
        # slow planets, since the Moon perfects dozens of contacts per month.
        # Sun/Mercury/Venus/Mars added for the workbook transit journal, which
        # scans all ten transiting bodies over its two-year span; the scan
        # algorithm below is body-agnostic (step sizes already suit the Moon,
        # the fastest body).
        planet_ids = {
            "sun": swe.SUN,
            "moon": swe.MOON,
            "mercury": swe.MERCURY,
            "venus": swe.VENUS,
            "mars": swe.MARS,
            "jupiter": swe.JUPITER,
            "saturn": swe.SATURN,
            "uranus": swe.URANUS,
            "neptune": swe.NEPTUNE,
            "pluto": swe.PLUTO
        }

        # Tolerances (from Python code)
        tolerances = {
            "Conjunction": 0.002,
            "Square": 0.004,
            "Opposition": 0.006,
            "Quincunx": 0.004
        }

        # Step sizes (matching transits_runner.py for maximum precision)
        STEP_CONJ = 0.05  # Days
        STEP_OTHER = 0.1  # Days

        # For each transiting planet
        for transit_planet_name in request.transiting_planets:
            if transit_planet_name not in planet_ids:
                continue

            planet_id = planet_ids[transit_planet_name]

            # For each natal planet
            for natal_planet, natal_lon in request.natal_positions.items():

                # For each aspect
                for aspect_name, aspect_data in request.aspects.items():
                    angle = aspect_data["angle"]
                    tol = tolerances.get(aspect_name, 0.004)
                    last_root = None

                    # CONJUNCTIONS - find local minimums
                    if angle == 0.0:
                        jd = start_jd
                        prev_jd = jd
                        prev_sep = sep_func(jd, natal_lon, planet_id)
                        jd += STEP_CONJ

                        curr_jd = jd
                        curr_sep = sep_func(jd, natal_lon, planet_id)
                        jd += STEP_CONJ

                        while jd <= end_jd:
                            next_jd = jd
                            next_sep = sep_func(jd, natal_lon, planet_id)

                            # Check for local minimum
                            if prev_sep > curr_sep < next_sep:
                                jd_min = find_min_sep_jd(prev_jd, next_jd, natal_lon, planet_id)
                                sep_min = sep_func(jd_min, natal_lon, planet_id)

                                if abs(sep_min - angle) < tol:
                                    if last_root is None or abs(jd_min - last_root) > 1e-3:
                                        transits.append((jd_min, transit_planet_name, natal_planet, aspect_name, sep_min))
                                        last_root = jd_min

                            prev_jd, prev_sep = curr_jd, curr_sep
                            curr_jd, curr_sep = next_jd, next_sep
                            jd += STEP_CONJ

                    # OTHER ASPECTS - find sign changes with bisection
                    else:
                        jd = start_jd
                        while jd < end_jd:
                            jd2 = min(jd + STEP_OTHER, end_jd)

                            f1 = gfunc(jd, natal_lon, planet_id, angle)
                            f2 = gfunc(jd2, natal_lon, planet_id, angle)

                            root = None
                            if f1 == 0.0:
                                root = jd
                            elif f2 == 0.0:
                                root = jd2
                            elif f1 * f2 < 0.0:
                                root = bisect_root(jd, jd2, natal_lon, planet_id, angle)

                            if root is not None:
                                sep = angle_separation(get_transit_lon(root, planet_id), natal_lon)
                                if abs(sep - angle) < tol:
                                    if last_root is None or abs(root - last_root) > 1e-3:
                                        transits.append((root, transit_planet_name, natal_planet, aspect_name, sep))
                                        last_root = root

                            jd = jd2

        # Convert to output format
        result_transits = []
        for jd_ut, tname, nname, aspect_name, sep in transits:
            # Convert JD back to datetime
            y, m, d, fh = swe.revjul(jd_ut, swe.GREG_CAL)
            H = int(fh)
            M = int((fh - H) * 60)
            S = int((((fh - H) * 60) - M) * 60)
            dt = datetime(y, m, d, H, M, S)

            # Get positions (with speed, for motion-at-exactness)
            xx_t, _ = swe.calc_ut(jd_ut, planet_ids[tname], swe.FLG_SWIEPH | swe.FLG_SPEED)
            transit_lon = xx_t[0]
            transit_speed = xx_t[3]
            natal_lon_val = request.natal_positions[nname]
            # Moon + Sun at the exact moment — feeds the TMG Moon check-in
            # (phase from elongation, sign, natal house) with no extra calls.
            xx_moon, _ = swe.calc_ut(jd_ut, swe.MOON, swe.FLG_SWIEPH)
            xx_sun, _ = swe.calc_ut(jd_ut, swe.SUN, swe.FLG_SWIEPH)

            transit_sign_data = lon_to_sign_degree(transit_lon)
            natal_sign_data = lon_to_sign_degree(natal_lon_val)

            # Determine which natal house each planet is in (Placidus/Koch/etc)
            transit_planet_house = get_planet_house(transit_lon, natal_cusps)
            natal_planet_house = get_planet_house(natal_lon_val, natal_cusps)

            # Determine whole sign houses (based on natal ascendant)
            natal_asc_lon = natal_houses["ascendant"]["longitude"]
            transit_planet_ws_house = get_whole_sign_house(transit_lon, natal_asc_lon)
            natal_planet_ws_house = get_whole_sign_house(natal_lon_val, natal_asc_lon)

            result_transits.append({
                "date": dt.isoformat(),
                "transit_planet": tname,
                "natal_planet": nname,
                "aspect": aspect_name,
                "separation": round(sep, 6),
                "transit_longitude": round(transit_lon, 6),
                "natal_longitude": round(natal_lon_val, 6),
                "transit_sign": transit_sign_data["sign"],
                "transit_degree": round(transit_sign_data["degree"], 4),
                "natal_sign": natal_sign_data["sign"],
                "natal_degree": round(natal_sign_data["degree"], 4),
                "transit_planet_house": transit_planet_house,
                "natal_planet_house": natal_planet_house,
                "transit_planet_ws_house": transit_planet_ws_house,
                "natal_planet_ws_house": natal_planet_ws_house,
                "speed": round(transit_speed, 6),
                "is_retro": transit_speed < 0,
                "moon_lon": round(xx_moon[0], 6),
                "sun_lon": round(xx_sun[0], 6)
            })

        # Sort by date
        result_transits.sort(key=lambda x: x["date"])

        return {
            "transits": result_transits,
            "count": len(result_transits)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating transits: {str(e)}")

# ── Stations ──────────────────────────────────────────────────────────────────
# Exact station events (retrograde/direct turns) for the slow planets over a
# window. Feeds TMG transit-sequence detection (station-between rule) and
# station-in-orb report call-outs.

STATION_PLANET_IDS = {
    "mercury": swe.MERCURY,
    "venus": swe.VENUS,
    "mars": swe.MARS,
    "jupiter": swe.JUPITER,
    "saturn": swe.SATURN,
    "uranus": swe.URANUS,
    "neptune": swe.NEPTUNE,
    "pluto": swe.PLUTO,
}

class StationsRequest(BaseModel):
    bodies: List[str] = ["jupiter", "saturn", "uranus", "neptune", "pluto"]
    start_date: str
    end_date: str

    @field_validator('start_date', 'end_date')
    @classmethod
    def validate_station_dates(cls, v):
        try:
            datetime.fromisoformat(v)
        except ValueError:
            raise ValueError('Date must be ISO format YYYY-MM-DD')
        return v

    @field_validator('bodies')
    @classmethod
    def validate_station_bodies(cls, v):
        unknown = [b for b in v if b not in STATION_PLANET_IDS]
        if unknown:
            raise ValueError(f"Bodies that station are {sorted(STATION_PLANET_IDS)}; unknown: {unknown}")
        return v

def get_transit_speed(jd: float, planet_id: int) -> float:
    """Apparent daily motion in longitude at Julian Day"""
    xx, _ = swe.calc_ut(jd, planet_id, swe.FLG_SWIEPH | swe.FLG_SPEED)
    return xx[3]

def bisect_station(j1: float, j2: float, planet_id: int, tol: float = 1e-4) -> float:
    """Find the speed zero-crossing (station moment) by bisection"""
    f1 = get_transit_speed(j1, planet_id)
    a, b = j1, j2
    for _ in range(60):
        if (b - a) < tol:
            break
        m = (a + b) / 2.0
        fm = get_transit_speed(m, planet_id)
        if f1 * fm <= 0:
            b = m
        else:
            a = m
            f1 = fm
    return (a + b) / 2.0

STATION_SCAN_STEP_DAYS = 1.0  # slow-planet speed changes sign over weeks; daily scan cannot skip a turn


def scan_stations(bodies, start_jd: float, end_jd: float) -> list:
    """Every exact station (speed zero-crossing) of the given bodies in
    [start_jd, end_jd], bisected to ~10 s and sorted by instant. Shared by
    /api/stations and the annual report's retrograde section."""
    stations = []
    for body in bodies:
        planet_id = STATION_PLANET_IDS[body]
        jd = start_jd
        prev_speed = get_transit_speed(jd, planet_id)
        while jd < end_jd:
            jd_next = min(jd + STATION_SCAN_STEP_DAYS, end_jd)
            speed = get_transit_speed(jd_next, planet_id)
            if prev_speed * speed <= 0.0 and prev_speed != speed:
                jd_station = bisect_station(jd, jd_next, planet_id)
                lon = get_transit_lon(jd_station, planet_id)
                lon_data = lon_to_sign_degree(lon)
                stations.append({
                    "body": body,
                    "date": jd_to_iso(jd_station),
                    "jd": round(jd_station, 6),
                    "longitude": round(lon, 6),
                    "sign": lon_data["sign"],
                    "degree": round(lon_data["degree"], 4),
                    "type": "direct" if prev_speed < 0 else "retrograde"
                })
            prev_speed = speed
            jd = jd_next
    stations.sort(key=lambda s: s["jd"])
    return stations

@app.post("/api/stations")
def get_stations(request: StationsRequest, api_key: str = Security(verify_api_key)):
    """Exact station events (retrograde/direct turns) over a date window"""
    logger.info(f"Station scan requested: {request.start_date} to {request.end_date}")
    try:
        start_dt = datetime.fromisoformat(request.start_date)
        end_dt = datetime.fromisoformat(request.end_date)
        start_jd = swe.julday(start_dt.year, start_dt.month, start_dt.day, 0.0, swe.GREG_CAL)
        end_jd = swe.julday(end_dt.year, end_dt.month, end_dt.day, 0.0, swe.GREG_CAL)

        stations = scan_stations(request.bodies, start_jd, end_jd)
        return {"stations": stations, "count": len(stations)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating stations: {str(e)}")

INGRESS_PLANET_IDS = {
    "sun": swe.SUN,
    "moon": swe.MOON,
    "mercury": swe.MERCURY,
    "venus": swe.VENUS,
    "mars": swe.MARS,
    "jupiter": swe.JUPITER,
    "saturn": swe.SATURN,
    "uranus": swe.URANUS,
    "neptune": swe.NEPTUNE,
    "pluto": swe.PLUTO,
}

# Scan step per body, in days. The step only needs to be small enough that a
# body cannot cross two sign boundaries (30 deg) or revisit one unseen inside a
# single step; crossings themselves are refined by bisection to ~30 seconds.
INGRESS_STEP_DAYS = {
    "sun": 0.25, "moon": 0.1, "mercury": 0.25, "venus": 0.25, "mars": 0.25,
    "jupiter": 0.5, "saturn": 0.5, "uranus": 0.5, "neptune": 0.5, "pluto": 0.5,
}

class IngressRequest(BaseModel):
    start_date: str  # ISO format: "2026-09-09"
    end_date: str
    bodies: List[str] = list(INGRESS_PLANET_IDS.keys())
    # Birth data for natal house cusps (same contract as /api/transits)
    lat: float
    lon: float
    birth_year: int
    birth_month: int
    birth_day: int
    birth_hour: int
    birth_min: int
    house_type: Optional[str] = "placidus"

    @field_validator('start_date', 'end_date')
    @classmethod
    def validate_ingress_dates(cls, v):
        try:
            datetime.fromisoformat(v)
        except ValueError:
            raise ValueError('Date must be ISO format YYYY-MM-DD')
        return v

    @field_validator('bodies')
    @classmethod
    def validate_ingress_bodies(cls, v):
        unknown = [b for b in v if b not in INGRESS_PLANET_IDS]
        if unknown:
            raise ValueError(f"Known bodies are {sorted(INGRESS_PLANET_IDS)}; unknown: {unknown}")
        return v


def jd_to_iso(jd: float) -> str:
    y, m, d, fh = swe.revjul(jd, swe.GREG_CAL)
    H = int(fh)
    M = int((fh - H) * 60)
    S = int((((fh - H) * 60) - M) * 60)
    return datetime(y, m, d, H, M, S).isoformat()


def bisect_classification(j1: float, j2: float, classify, tol: float = 3.5e-4) -> float:
    """Refine the moment a classification (sign index / house number) flips
    between j1 and j2. Pure comparison bisection — no longitude-boundary root
    needed, so it is immune to the 0/360 wrap and to retrograde direction.
    tol 3.5e-4 days ~= 30 seconds."""
    c1 = classify(j1)
    while (j2 - j1) > tol:
        m = (j1 + j2) / 2.0
        if classify(m) == c1:
            j1 = m
        else:
            j2 = m
    return (j1 + j2) / 2.0


@app.post("/api/ingresses")
def get_ingresses(request: IngressRequest, api_key: str = Security(verify_api_key)):
    """Sign ingresses and natal-house-cusp crossings for transiting bodies over
    a date window, plus each body's position at window start and the natal
    cusps. Built for the TMG workbook transit journal: its entries pre-fill
    'moves from Sign X to Sign Y' and 'affects natal House(s) N' from these
    events. Retrograde crossings are reported with their actual direction."""
    logger.info(f"Ingress scan requested: {request.start_date} to {request.end_date} for {request.bodies}")
    try:
        # Natal Placidus cusps from birth data — identical path to /api/transits.
        natal_jd = calculate_julian_day(
            request.birth_year, request.birth_month, request.birth_day,
            request.birth_hour, request.birth_min, request.lat, request.lon
        )
        _, natal_cusps = calculate_houses_for_jd(natal_jd, request.lat, request.lon, request.house_type)

        start_dt = datetime.fromisoformat(request.start_date)
        end_dt = datetime.fromisoformat(request.end_date)
        start_jd = swe.julday(start_dt.year, start_dt.month, start_dt.day, 0.0, swe.GREG_CAL)
        end_jd = swe.julday(end_dt.year, end_dt.month, end_dt.day, 0.0, swe.GREG_CAL)
        if end_jd <= start_jd:
            raise HTTPException(status_code=422, detail="end_date must be after start_date")

        def sign_of(jd: float, pid: int) -> int:
            return int((get_transit_lon(jd, pid) % 360.0) // 30)

        def house_of(jd: float, pid: int) -> int:
            return get_planet_house(get_transit_lon(jd, pid), natal_cusps)

        events = []
        positions = {}
        for body in request.bodies:
            pid = INGRESS_PLANET_IDS[body]
            step = INGRESS_STEP_DAYS[body]

            lon0 = get_transit_lon(start_jd, pid)
            sign_data = lon_to_sign_degree(lon0)
            positions[body] = {
                "lon": round(lon0, 6),
                "sign": sign_data["sign"],
                "degree": round(sign_data["degree"], 4),
                "house": get_planet_house(lon0, natal_cusps),
                "retrograde": get_transit_speed(start_jd, pid) < 0,
            }

            jd = start_jd
            prev_sign = sign_of(jd, pid)
            prev_house = house_of(jd, pid)
            while jd < end_jd:
                jd_next = min(jd + step, end_jd)
                curr_sign = sign_of(jd_next, pid)
                curr_house = house_of(jd_next, pid)

                if curr_sign != prev_sign:
                    jd_x = bisect_classification(jd, jd_next, lambda j: sign_of(j, pid))
                    events.append({
                        "body": body, "type": "sign",
                        "date": jd_to_iso(jd_x), "jd": round(jd_x, 6),
                        "from": SIGNS[prev_sign], "to": SIGNS[curr_sign],
                        "retrograde": get_transit_speed(jd_x, pid) < 0,
                    })
                if curr_house != prev_house:
                    jd_x = bisect_classification(jd, jd_next, lambda j: house_of(j, pid))
                    events.append({
                        "body": body, "type": "house",
                        "date": jd_to_iso(jd_x), "jd": round(jd_x, 6),
                        "from": prev_house, "to": curr_house,
                        "retrograde": get_transit_speed(jd_x, pid) < 0,
                    })

                prev_sign, prev_house = curr_sign, curr_house
                jd = jd_next

        events.sort(key=lambda e: e["jd"])
        return {
            "positions": positions,
            "cusps": [round(c % 360.0, 6) for c in natal_cusps[:12]],
            "events": events,
            "count": len(events),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating ingresses: {str(e)}")


class OrbWindowsRequest(BaseModel):
    start_date: str  # ISO format: "2026-09-01"
    end_date: str
    bodies: List[str] = list(INGRESS_PLANET_IDS.keys())
    natal_positions: Dict[str, float]  # e.g. {"Sun": 26.57, "ASC": 109.35, ...}
    aspects: Dict[str, Dict]  # e.g. {"Conjunct": {"angle": 0, "orb": 8.0}, ...}

    @field_validator('start_date', 'end_date')
    @classmethod
    def validate_orb_window_dates(cls, v):
        try:
            datetime.fromisoformat(v)
        except ValueError:
            raise ValueError('Date must be ISO format YYYY-MM-DD')
        return v

    @field_validator('bodies')
    @classmethod
    def validate_orb_window_bodies(cls, v):
        unknown = [b for b in v if b not in INGRESS_PLANET_IDS]
        if unknown:
            raise ValueError(f"Known bodies are {sorted(INGRESS_PLANET_IDS)}; unknown: {unknown}")
        return v

    @field_validator('natal_positions')
    @classmethod
    def validate_orb_window_natal(cls, v):
        if not v:
            raise ValueError('Natal positions cannot be empty')
        for point, lon in v.items():
            if lon < 0 or lon > 360:
                raise ValueError(f'{point} longitude must be between 0 and 360')
        return v

    @field_validator('aspects')
    @classmethod
    def validate_orb_window_aspects(cls, v):
        if not v:
            raise ValueError('Aspects cannot be empty')
        for name, spec in v.items():
            angle = spec.get("angle")
            orb = spec.get("orb")
            if angle is None or angle < 0 or angle > 180:
                raise ValueError(f'{name}: angle must be between 0 and 180')
            if orb is None or orb <= 0 or orb > 15:
                raise ValueError(f'{name}: orb must be between 0 and 15')
        return v


@app.post("/api/orb-windows")
def get_orb_windows(request: OrbWindowsRequest, api_key: str = Security(verify_api_key)):
    """In-orb windows (enter/exit instants) for transiting bodies against natal
    positions, per aspect. Built for the TMG daily transit journal: each daily
    aspect line shows the date range it is active, i.e. while
    |separation - aspect angle| <= orb. Windows already open at start_date or
    still open at end_date are clamped and flagged. Edges are refined by the
    same comparison bisection as /api/ingresses (~30 s), which is immune to the
    0/360 wrap, the 180 deg separation maximum, and retrograde direction."""
    logger.info(f"Orb-window scan requested: {request.start_date} to {request.end_date} for {request.bodies}")
    try:
        start_dt = datetime.fromisoformat(request.start_date)
        end_dt = datetime.fromisoformat(request.end_date)
        start_jd = swe.julday(start_dt.year, start_dt.month, start_dt.day, 0.0, swe.GREG_CAL)
        end_jd = swe.julday(end_dt.year, end_dt.month, end_dt.day, 0.0, swe.GREG_CAL)
        if end_jd <= start_jd:
            raise HTTPException(status_code=422, detail="end_date must be after start_date")

        windows = []
        for body in request.bodies:
            pid = INGRESS_PLANET_IDS[body]
            step = INGRESS_STEP_DAYS[body]

            # One pass per body over the JD walk; every (natal point, aspect)
            # tracks its own open window. The ephemeris longitude per JD is
            # memoised (get_transit_lon), so the inner loops are float math.
            trackers = []
            for natal_point, natal_lon in request.natal_positions.items():
                for aspect_name, spec in request.aspects.items():
                    trackers.append({
                        "natal": natal_point, "natal_lon": natal_lon,
                        "aspect": aspect_name,
                        "angle": float(spec["angle"]), "orb": float(spec["orb"]),
                        "open_jd": None, "open_clamped": False,
                    })

            def in_orb(jd: float, tr) -> bool:
                sep = angle_separation(get_transit_lon(jd, pid), tr["natal_lon"])
                return abs(sep - tr["angle"]) <= tr["orb"]

            for tr in trackers:
                if in_orb(start_jd, tr):
                    tr["open_jd"] = start_jd
                    tr["open_clamped"] = True

            jd = start_jd
            while jd < end_jd:
                jd_next = min(jd + step, end_jd)
                for tr in trackers:
                    inside = in_orb(jd_next, tr)
                    was_inside = tr["open_jd"] is not None
                    if inside == was_inside:
                        continue
                    jd_x = bisect_classification(jd, jd_next, lambda j: in_orb(j, tr))
                    if inside:
                        tr["open_jd"] = jd_x
                        tr["open_clamped"] = False
                    else:
                        windows.append({
                            "body": body, "natal": tr["natal"], "aspect": tr["aspect"],
                            "enter": jd_to_iso(tr["open_jd"]), "exit": jd_to_iso(jd_x),
                            "enter_jd": round(tr["open_jd"], 6), "exit_jd": round(jd_x, 6),
                            "enter_clamped": tr["open_clamped"], "exit_clamped": False,
                        })
                        tr["open_jd"] = None
                        tr["open_clamped"] = False
                jd = jd_next

            for tr in trackers:
                if tr["open_jd"] is not None:
                    windows.append({
                        "body": body, "natal": tr["natal"], "aspect": tr["aspect"],
                        "enter": jd_to_iso(tr["open_jd"]), "exit": jd_to_iso(end_jd),
                        "enter_jd": round(tr["open_jd"], 6), "exit_jd": round(end_jd, 6),
                        "enter_clamped": tr["open_clamped"], "exit_clamped": True,
                    })

        windows.sort(key=lambda w: w["enter_jd"])
        return {"windows": windows, "count": len(windows)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating orb windows: {str(e)}")


class LongitudesRequest(BaseModel):
    instants: List[str]  # ISO datetimes, UT: "2026-09-13T19:00:00"
    bodies: List[str] = list(INGRESS_PLANET_IDS.keys())

    @field_validator('instants')
    @classmethod
    def validate_longitude_instants(cls, v):
        if not v:
            raise ValueError('instants cannot be empty')
        if len(v) > 400:
            raise ValueError('At most 400 instants per request')
        for instant in v:
            try:
                datetime.fromisoformat(instant)
            except ValueError:
                raise ValueError(f'Instant must be ISO format YYYY-MM-DDTHH:MM:SS, got: {instant}')
        return v

    @field_validator('bodies')
    @classmethod
    def validate_longitude_bodies(cls, v):
        unknown = [b for b in v if b not in INGRESS_PLANET_IDS]
        if unknown:
            raise ValueError(f"Known bodies are {sorted(INGRESS_PLANET_IDS)}; unknown: {unknown}")
        return v


@app.post("/api/longitudes")
def get_longitudes(request: LongitudesRequest, api_key: str = Security(verify_api_key)):
    """Ecliptic longitudes for transiting bodies at a list of UT instants.

    Built for the TMG daily transit journal: the month calendar stores each
    body's longitude at local noon per day, so the client can derive the
    current orb of an aspect window (|separation - aspect angle|) as pure
    arithmetic on service-computed positions — no ephemeris math in JS."""
    logger.info(f"Longitudes requested for {len(request.instants)} instants, bodies {request.bodies}")
    try:
        longitudes = {}
        for instant in request.instants:
            dt = datetime.fromisoformat(instant)
            jd = swe.julday(dt.year, dt.month, dt.day,
                            dt.hour + dt.minute / 60.0 + dt.second / 3600.0, swe.GREG_CAL)
            longitudes[instant] = {
                body: round(get_transit_lon(jd, INGRESS_PLANET_IDS[body]) % 360.0, 6)
                for body in request.bodies
            }
        return {"longitudes": longitudes, "count": len(longitudes)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating longitudes: {str(e)}")


# ── Planetary returns ─────────────────────────────────────────────────────────
# The current return cycle of each transiting body against its own natal
# longitude, plus the charts the TMG Planetary Returns report is drawn from:
# the return chart (cycle-start instant, birth location) and the transit chart
# (same instant, the seeker's current location — same longitudes, different
# house wheel, which the report expresses intentionally), plus the exact
# perfection instants of the body's aspects to its own natal position through
# the cycle. All house math stays here; the app only pairs longitudes.

# Geocentric return periods in days — search-horizon sizing only, never output.
# Mercury and Venus never stray far from the Sun, so their geocentric return
# period is the solar year, not their heliocentric orbital period.
RETURN_PERIOD_DAYS = {
    "sun": 365.26, "moon": 27.322, "mercury": 365.26, "venus": 365.26,
    "mars": 686.98, "jupiter": 4332.6, "saturn": 10759.2,
    "uranus": 30688.5, "neptune": 60182.0, "pluto": 90560.0,
}

# Walk step per body, in days. Small enough that a retrograde loop is sampled
# many times over (the shortest, Mercury's, spans ~24 days), so no crossing
# pair can hide inside one step; crossings are then bisected to ~1 second.
RETURN_STEP_DAYS = {
    "sun": 0.5, "moon": 0.25, "mercury": 0.25, "venus": 0.25, "mars": 0.5,
    "jupiter": 1.0, "saturn": 2.0, "uranus": 3.0, "neptune": 5.0, "pluto": 5.0,
}

# How far around the anchor the crossing search reaches, in periods. One full
# period back guarantees the previous return exists wherever the birth floor
# does not cut it off; the margin absorbs retrograde-driven cycle stretch.
RETURN_SEARCH_PERIODS = 1.35

RETURN_SELF_ASPECTS_DEFAULT = {
    "Square": 90.0, "Sextile": 60.0, "Trine": 120.0, "Opposition": 180.0,
}

# Bodies placed on the return/transit charts: the ten planets plus the True
# Node (the report's North Node; South is its antipode, derived by the app).
RETURN_CHART_BODY_IDS = dict(INGRESS_PLANET_IDS, true_node=swe.TRUE_NODE)


def validate_longitude_map(v: Dict[str, float]) -> Dict[str, float]:
    """A body → ecliptic longitude map, every value in [0, 360]."""
    for body, lon in v.items():
        if lon < 0 or lon > 360:
            raise ValueError(f'{body} longitude must be between 0 and 360')
    return v


def validate_latitude(v: float) -> float:
    if v < -90 or v > 90:
        raise ValueError('Latitude must be between -90 and 90')
    return v


def validate_longitude(v: float) -> float:
    if v < -180 or v > 180:
        raise ValueError('Longitude must be between -180 and 180')
    return v


class NatalChartRequest(BaseModel):
    """Birth data — local civil time + birth location (the natal-chart
    contract, identical to /api/transits and /api/ingresses). Every
    chart-based report request inherits these fields and their checks."""
    lat: float
    lon: float
    birth_year: int
    birth_month: int
    birth_day: int
    birth_hour: int
    birth_min: int
    house_type: Optional[str] = "placidus"

    @field_validator('lat')
    @classmethod
    def validate_natal_lat(cls, v):
        return validate_latitude(v)

    @field_validator('lon')
    @classmethod
    def validate_natal_lon(cls, v):
        return validate_longitude(v)


class ReturnsRequest(NatalChartRequest):
    # UT instant the cycle is anchored on ('YYYY-MM-DDTHH:MM:SS').
    anchor_instant: str
    bodies: List[str] = list(INGRESS_PLANET_IDS.keys())
    natal_positions: Dict[str, float]  # body → natal ecliptic longitude
    # Where the seeker is now — the transit chart's house wheel.
    current_lat: float
    current_lon: float
    self_aspects: Optional[Dict[str, float]] = None

    @field_validator('anchor_instant')
    @classmethod
    def validate_anchor_instant(cls, v):
        try:
            datetime.fromisoformat(v)
        except ValueError:
            raise ValueError('anchor_instant must be an ISO datetime (YYYY-MM-DDTHH:MM:SS)')
        return v

    @field_validator('bodies')
    @classmethod
    def validate_returns_bodies(cls, v):
        unknown = [b for b in v if b not in INGRESS_PLANET_IDS]
        if unknown:
            raise ValueError(f"Known bodies are {sorted(INGRESS_PLANET_IDS)}; unknown: {unknown}")
        if not v:
            raise ValueError('bodies cannot be empty')
        return v

    @field_validator('natal_positions')
    @classmethod
    def validate_returns_natal(cls, v):
        return validate_longitude_map(v)

    @field_validator('current_lat')
    @classmethod
    def validate_returns_current_lat(cls, v):
        return validate_latitude(v)

    @field_validator('current_lon')
    @classmethod
    def validate_returns_current_lon(cls, v):
        return validate_longitude(v)

    @field_validator('self_aspects')
    @classmethod
    def validate_returns_self_aspects(cls, v):
        if v is None:
            return v
        for name, angle in v.items():
            if angle <= 0 or angle > 180:
                raise ValueError(f'self-aspect {name} angle must be in (0, 180]')
        return v


def wrap180(x: float) -> float:
    """Signed angular offset in [-180, 180)."""
    return ((x + 180.0) % 360.0) - 180.0


def signed_offset(jd: float, planet_id: int, target_lon: float) -> float:
    return wrap180(get_transit_lon(jd, planet_id) - target_lon)


def bisect_signed_crossing(j1: float, j2: float, planet_id: int, target_lon: float,
                           tol: float = 1e-5) -> float:
    """Refine a signed zero-crossing of (body longitude − target) bracketed by
    [j1, j2]. The bracket never spans the antipode (callers reject wrap jumps),
    so the offset is continuous and plain bisection converges. tol 1e-5 days
    ~= 1 second."""
    f1 = signed_offset(j1, planet_id, target_lon)
    a, b = j1, j2
    for _ in range(60):
        m = (a + b) / 2.0
        fm = signed_offset(m, planet_id, target_lon)
        if abs(fm) < 1e-7 or (b - a) < tol:
            return m
        if f1 * fm <= 0:
            b = m
        else:
            a = m
            f1 = fm
    return (a + b) / 2.0


# A crossing only counts as a RETURN once the body has genuinely departed its
# natal degree. Newborn charts start ON the degree, and every body wobbles
# back across it during its first retrograde loop (Saturn ~10 months after
# birth) — a one-year-old is not having a Saturn return. 30° exceeds every
# retrograde-loop amplitude (Mars' ~19° is the widest), and a true return
# approaches from a full revolution, so no real return is ever gated out.
RETURN_DEPARTURE_DEG = 30.0


def find_return_crossings(planet_id: int, target_lon: float,
                          start_jd: float, end_jd: float, step: float,
                          departed: bool = True) -> list:
    """Every RETURN instant — the body's longitude crossing target_lon — in
    [start, end], in either direction (a retrograde return still yields its
    full multi-pass sequence). Sign-change detection on the wrapped offset; a
    jump through the antipode (|f1 − f2| > 180) is the wrap artifact, not a
    crossing, and is skipped.

    With departed=False (a scan that starts at the birth instant), crossings
    are ignored until the body has first moved RETURN_DEPARTURE_DEG away from
    target_lon — the post-natal retrograde re-crossings of the natal degree
    are natal wobble, not returns."""
    crossings = []
    jd = start_jd
    f1 = signed_offset(jd, planet_id, target_lon)
    while jd < end_jd:
        jd2 = min(jd + step, end_jd)
        f2 = signed_offset(jd2, planet_id, target_lon)
        if not departed and min(abs(f1), abs(f2)) >= RETURN_DEPARTURE_DEG:
            departed = True
        if departed and abs(f1 - f2) < 180.0 and f1 * f2 <= 0.0 and (f1 != 0.0 or f2 != 0.0):
            root = bisect_signed_crossing(jd, jd2, planet_id, target_lon)
            if not crossings or abs(root - crossings[-1]) > 1e-3:
                crossings.append(root)
        jd, f1 = jd2, f2
    return crossings


def find_self_aspect_hits(planet_id: int, natal_lon: float, angle: float,
                          start_jd: float, end_jd: float, step: float) -> list:
    """Exact perfection instants of one aspect angle between the transiting
    body and its own natal longitude, inside [start, end]. Angles below 180°
    are sign-changes of (separation − angle), refined by the shared bisection;
    180° is the separation's maximum, so oppositions are ternary-refined local
    maxima that actually reach it (mirrors the conjunction-minimum handling
    in /api/transits)."""
    hits = []
    if angle >= 180.0:
        prev_jd = start_jd
        prev_sep = sep_func(prev_jd, natal_lon, planet_id)
        curr_jd = min(prev_jd + step, end_jd)
        curr_sep = sep_func(curr_jd, natal_lon, planet_id)
        jd = curr_jd + step
        while jd <= end_jd:
            next_sep = sep_func(jd, natal_lon, planet_id)
            if prev_sep < curr_sep > next_sep:
                jd_max = find_max_sep_jd(prev_jd, jd, natal_lon, planet_id)
                if abs(sep_func(jd_max, natal_lon, planet_id) - 180.0) < 0.01:
                    if not hits or abs(jd_max - hits[-1]) > 1e-3:
                        hits.append(jd_max)
            prev_jd, prev_sep = curr_jd, curr_sep
            curr_jd, curr_sep = jd, next_sep
            jd += step
        return hits

    jd = start_jd
    f1 = gfunc(jd, natal_lon, planet_id, angle)
    while jd < end_jd:
        jd2 = min(jd + step, end_jd)
        f2 = gfunc(jd2, natal_lon, planet_id, angle)
        root = None
        if f1 == 0.0:
            root = jd
        elif f2 == 0.0:
            root = jd2
        elif f1 * f2 < 0.0:
            root = bisect_root(jd, jd2, natal_lon, planet_id, angle)
        if root is not None and (not hits or abs(root - hits[-1]) > 1e-3):
            hits.append(root)
        jd, f1 = jd2, f2
    return hits


def find_max_sep_jd(j1: float, j2: float, natal_lon: float, planet_id: int) -> float:
    """Local maximum separation via ternary search (opposition perfection)."""
    a, b = j1, j2
    for _ in range(40):
        m1 = a + (b - a) / 3.0
        m2 = b - (b - a) / 3.0
        if sep_func(m1, natal_lon, planet_id) > sep_func(m2, natal_lon, planet_id):
            b = m2
        else:
            a = m1
    return (a + b) / 2.0


def returns_body_state(jd: float, planet_id: int):
    """(longitude, speed) at a JD, with speed for retrograde/applying checks."""
    xx, _ = swe.calc_ut(jd, planet_id, swe.FLG_SWIEPH | swe.FLG_SPEED)
    return xx[0] % 360.0, xx[3]


def returns_placement(lon: float, speed: float, wheels: dict) -> dict:
    """One body's placement: sign/degree plus its house in every named wheel
    ('house' key per wheel, e.g. return_house / transit_house / natal_house)."""
    sign_data = lon_to_sign_degree(lon)
    placement = {
        "longitude": round(lon, 6),
        "sign": sign_data["sign"],
        "degree": round(sign_data["degree"], 4),
        "speed": round(speed, 6),
        "is_retro": speed < 0,
    }
    for wheel_name, cusps in wheels.items():
        placement[f"{wheel_name}_house"] = get_planet_house(lon, cusps)
    return placement


def returns_angles(houses_data: dict, natal_cusps) -> dict:
    """Ascendant + Midheaven of one wheel, each with the natal house its
    longitude falls in (their own-wheel houses are 1 and 10 by definition,
    so the natal placement is the informative one)."""
    return {
        key: {
            **houses_data[key],
            "natal_house": get_planet_house(houses_data[key]["longitude"], natal_cusps),
        }
        for key in ("ascendant", "midheaven")
    }


@app.post("/api/returns")
def get_returns(request: ReturnsRequest, api_key: str = Security(verify_api_key)):
    """Per body: the current return cycle around anchor_instant (previous and
    next exact conjunctions with the natal longitude — the cycle start clamps
    to birth when the first return has not happened yet), the return chart at
    cycle start (birth location) and the transit house wheel at the same
    instant (current location), and the exact self-aspect perfections through
    the cycle, each placed on the day-one transit wheel."""
    logger.info(f"Returns requested for {request.bodies} around {request.anchor_instant}")
    try:
        anchor_dt = datetime.fromisoformat(request.anchor_instant)
        anchor_jd = swe.julday(
            anchor_dt.year, anchor_dt.month, anchor_dt.day,
            anchor_dt.hour + anchor_dt.minute / 60.0 + anchor_dt.second / 3600.0,
            swe.GREG_CAL,
        )
        birth_jd = calculate_julian_day(
            request.birth_year, request.birth_month, request.birth_day,
            request.birth_hour, request.birth_min, request.lat, request.lon,
        )
        if anchor_jd < birth_jd:
            raise HTTPException(status_code=422, detail="anchor_instant is before the birth instant")

        missing = [b for b in request.bodies if b not in request.natal_positions]
        if missing:
            raise HTTPException(status_code=422, detail=f"natal_positions missing bodies: {missing}")

        _, natal_cusps = calculate_houses_for_jd(birth_jd, request.lat, request.lon, request.house_type)
        self_aspects = request.self_aspects or RETURN_SELF_ASPECTS_DEFAULT

        returns = {}
        for body in request.bodies:
            planet_id = INGRESS_PLANET_IDS[body]
            target_lon = request.natal_positions[body] % 360.0
            period = RETURN_PERIOD_DAYS[body]
            step = RETURN_STEP_DAYS[body]

            search_start = max(birth_jd, anchor_jd - RETURN_SEARCH_PERIODS * period)
            search_end = anchor_jd + RETURN_SEARCH_PERIODS * period
            # A scan floored at birth starts ON the natal degree — apply the
            # departure gate so post-natal wobble never counts as a return. A
            # scan starting mid-flight is already a full revolution in.
            crossings = find_return_crossings(planet_id, target_lon, search_start, search_end, step,
                                              departed=search_start > birth_jd)

            prev_hits = [jd for jd in crossings if jd <= anchor_jd]
            next_hits = [jd for jd in crossings if jd > anchor_jd]
            clamped_to_birth = len(prev_hits) == 0
            cycle_start_jd = prev_hits[-1] if prev_hits else birth_jd
            cycle_end_jd = next_hits[0] if next_hits else None

            return_houses, return_cusps = calculate_houses_for_jd(
                cycle_start_jd, request.lat, request.lon, request.house_type)
            transit_houses, transit_cusps = calculate_houses_for_jd(
                cycle_start_jd, request.current_lat, request.current_lon, request.house_type)

            wheels = {
                "return": return_cusps,
                "transit": transit_cusps,
                "natal": natal_cusps,
            }
            planets = {}
            for chart_body, chart_pid in RETURN_CHART_BODY_IDS.items():
                lon, speed = returns_body_state(cycle_start_jd, chart_pid)
                planets[chart_body] = returns_placement(lon, speed, wheels)
            # South Node: the True Node's antipode, placed on every wheel by
            # its own longitude (quadrant houses are not symmetric, so the
            # antipode's house is a real cusp lookup, not "house + 6").
            node = planets["true_node"]
            planets["south_node"] = returns_placement(
                (node["longitude"] + 180.0) % 360.0, node["speed"], wheels)

            aspect_hits = []
            if cycle_end_jd is not None:
                for aspect_name, angle in self_aspects.items():
                    for hit_jd in find_self_aspect_hits(
                            planet_id, target_lon, angle, cycle_start_jd, cycle_end_jd, step):
                        lon, speed = returns_body_state(hit_jd, planet_id)
                        sign_data = lon_to_sign_degree(lon)
                        aspect_hits.append({
                            "aspect": aspect_name,
                            "date": jd_to_iso(hit_jd),
                            "longitude": round(lon, 6),
                            "sign": sign_data["sign"],
                            "degree": round(sign_data["degree"], 4),
                            "transit_house": get_planet_house(lon, transit_cusps),
                            "natal_house": get_planet_house(lon, natal_cusps),
                            "is_retro": speed < 0,
                        })
                aspect_hits.sort(key=lambda h: h["date"])

            returns[body] = {
                "cycle": {
                    "start": jd_to_iso(cycle_start_jd),
                    "end": jd_to_iso(cycle_end_jd) if cycle_end_jd is not None else None,
                    "clamped_to_birth": clamped_to_birth,
                    "end_found": cycle_end_jd is not None,
                },
                "planets": planets,
                "return_angles": returns_angles(return_houses, natal_cusps),
                "transit_angles": returns_angles(transit_houses, natal_cusps),
                "self_aspects": aspect_hits,
            }

        return {"anchor_instant": request.anchor_instant, "returns": returns}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating returns: {str(e)}")


# ── Monthly transit report ───────────────────────────────────────────────────
# Chart-free sky events after an instant: the next new and full moon, and the
# next sign ingress of each requested body. Built for the TMG Monthly Transit
# Report (admin Astrology Reports tab): one row per event, coloured by the
# sign's element. No natal data — everything here is mundane astronomy.

MONTHLY_DEFAULT_BODIES = ["sun", "mercury", "venus", "mars"]

# Scan step for the Sun–Moon elongation, in days. The phase half-cycle is
# ~14.8 days, so a 0.25-day step cannot skip a lunation; instants are then
# bisected to ~30 seconds.
LUNATION_STEP_DAYS = 0.25
# Longer than any synodic month (29.27–29.83 days).
LUNATION_HORIZON_DAYS = 32.0
# Longer than any body's longest stay in one sign (Mars' retrograde loop can
# hold it in a sign for ~7 months; Venus ~4; Mercury ~2.5).
INGRESS_HORIZON_DAYS = 400.0


class MonthlyTransitsRequest(BaseModel):
    # UT instant the search begins at ('YYYY-MM-DDTHH:MM:SS'); every event
    # returned is strictly after it.
    start_instant: str
    bodies: List[str] = list(MONTHLY_DEFAULT_BODIES)

    @field_validator('start_instant')
    @classmethod
    def validate_monthly_start(cls, v):
        try:
            datetime.fromisoformat(v)
        except ValueError:
            raise ValueError('start_instant must be an ISO datetime (YYYY-MM-DDTHH:MM:SS)')
        return v

    @field_validator('bodies')
    @classmethod
    def validate_monthly_bodies(cls, v):
        unknown = [b for b in v if b not in INGRESS_PLANET_IDS]
        if unknown:
            raise ValueError(f"Known bodies are {sorted(INGRESS_PLANET_IDS)}; unknown: {unknown}")
        if not v:
            raise ValueError('bodies cannot be empty')
        return v


def lunar_phase_half(jd: float) -> int:
    """0 while the Moon is waxing (elongation from the Sun in [0, 180)),
    1 while waning. A 1→0 flip is a new moon, a 0→1 flip a full moon."""
    elongation = (get_transit_lon(jd, swe.MOON) - get_transit_lon(jd, swe.SUN)) % 360.0
    return int(elongation // 180.0)


def lunation_event(jd: float) -> dict:
    sun = lon_to_sign_degree(get_transit_lon(jd, swe.SUN))
    moon = lon_to_sign_degree(get_transit_lon(jd, swe.MOON))
    return {
        "date": jd_to_iso(jd), "jd": round(jd, 6),
        "sun_sign": sun["sign"], "sun_degree": round(sun["degree"], 4),
        "moon_sign": moon["sign"], "moon_degree": round(moon["degree"], 4),
    }


def find_next_lunations(start_jd: float) -> dict:
    """The first new moon and first full moon strictly after start_jd."""
    found = {"new_moon": None, "full_moon": None}
    jd = start_jd
    prev = lunar_phase_half(jd)
    end_jd = start_jd + LUNATION_HORIZON_DAYS
    while jd < end_jd and (found["new_moon"] is None or found["full_moon"] is None):
        jd_next = min(jd + LUNATION_STEP_DAYS, end_jd)
        curr = lunar_phase_half(jd_next)
        if curr != prev:
            jd_x = bisect_classification(jd, jd_next, lunar_phase_half)
            key = "new_moon" if curr == 0 else "full_moon"
            if found[key] is None:
                found[key] = lunation_event(jd_x)
        prev = curr
        jd = jd_next
    return found


def find_next_ingress(start_jd: float, body: str) -> Optional[dict]:
    """The first sign boundary crossing of a body strictly after start_jd, in
    whichever direction it is moving (a retrograde re-entry counts — it is
    reported with its direction)."""
    pid = INGRESS_PLANET_IDS[body]
    step = INGRESS_STEP_DAYS[body]

    def sign_of(jd: float) -> int:
        return int((get_transit_lon(jd, pid) % 360.0) // 30)

    jd = start_jd
    prev_sign = sign_of(jd)
    end_jd = start_jd + INGRESS_HORIZON_DAYS
    while jd < end_jd:
        jd_next = min(jd + step, end_jd)
        curr_sign = sign_of(jd_next)
        if curr_sign != prev_sign:
            jd_x = bisect_classification(jd, jd_next, sign_of)
            return {
                "date": jd_to_iso(jd_x), "jd": round(jd_x, 6),
                "from": SIGNS[prev_sign], "to": SIGNS[curr_sign],
                "retrograde": get_transit_speed(jd_x, pid) < 0,
            }
        prev_sign = curr_sign
        jd = jd_next
    return None


@app.post("/api/monthly-transits")
def get_monthly_transits(request: MonthlyTransitsRequest, api_key: str = Security(verify_api_key)):
    """Chart-free sky events after start_instant: the next new moon and full
    moon (with the Sun's and Moon's signs at the instant) and, per requested
    body, its sign at the start and its next sign ingress (either direction).
    Everything is strictly after the start instant."""
    logger.info(f"Monthly transits requested after {request.start_instant} for {request.bodies}")
    try:
        start_dt = datetime.fromisoformat(request.start_instant)
        start_jd = swe.julday(
            start_dt.year, start_dt.month, start_dt.day,
            start_dt.hour + start_dt.minute / 60.0 + start_dt.second / 3600.0,
            swe.GREG_CAL,
        )
        lunations = find_next_lunations(start_jd)
        missing = [k for k, v in lunations.items() if v is None]
        if missing:
            raise HTTPException(status_code=500, detail=f"No {missing} found within {LUNATION_HORIZON_DAYS} days")

        positions = {}
        ingresses = {}
        for body in request.bodies:
            lon0 = get_transit_lon(start_jd, INGRESS_PLANET_IDS[body])
            sign_data = lon_to_sign_degree(lon0)
            positions[body] = {
                "sign": sign_data["sign"],
                "degree": round(sign_data["degree"], 4),
                "retrograde": get_transit_speed(start_jd, INGRESS_PLANET_IDS[body]) < 0,
            }
            ingress = find_next_ingress(start_jd, body)
            if ingress is None:
                raise HTTPException(status_code=500, detail=f"No {body} ingress found within {INGRESS_HORIZON_DAYS} days")
            ingresses[body] = ingress

        return {
            "start_instant": request.start_instant,
            "lunations": lunations,
            "positions": positions,
            "ingresses": ingresses,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating monthly transits: {str(e)}")


# ── Annual transit report ────────────────────────────────────────────────────
# One natal chart, one year from a start instant: the Sun's exact conjunctions
# with the natal Sun and the four angles, every solar and lunar eclipse with
# its natal house, every retrograde period that overlaps the year (station
# to station, with the degrees), and each outer planet's current sign (when
# it was entered) and its next sign change — every placement on the NATAL
# house wheel. Built for the TMG Annual Transit Report (admin Astrology
# Reports tab). All house math stays here; the app only pairs longitudes.

ANNUAL_RETRO_BODIES = ["mercury", "venus", "mars", "jupiter", "saturn", "uranus", "neptune", "pluto"]
ANNUAL_INGRESS_BODIES = ["jupiter", "saturn", "uranus", "neptune", "pluto"]
ANNUAL_SUN_TARGET_KEYS = ["sun", "ascendant", "ic", "descendant", "midheaven"]

# The Sun crosses any fixed longitude once per tropical year (365.24 d); a
# 367-day search from the start instant therefore finds exactly one crossing.
ANNUAL_SUN_SEARCH_DAYS = 367.0
ANNUAL_SUN_STEP_DAYS = 0.5
# A retrograde period is at most ~5.5 months (Neptune/Pluto ~160 d); scanning
# stations this far either side of the year catches every overlapping pair.
ANNUAL_STATION_PAD_DAYS = 200.0
# Longest stay of any body in one sign: Pluto ~32 years (Taurus, 1852–1884).
ANNUAL_INGRESS_HORIZON_DAYS = 35.0 * 365.25


class AnnualTransitsRequest(NatalChartRequest):
    # UT instant the report year begins at ('YYYY-MM-DDTHH:MM:SS').
    start_instant: str
    span_days: int = 365
    # Natal longitudes the transiting Sun is searched against, keyed by
    # ANNUAL_SUN_TARGET_KEYS (the app passes the stored chart's values so the
    # report agrees with the chart on screen). Birth data for the natal house
    # cusps comes from NatalChartRequest (same contract as /api/returns).
    sun_targets: Dict[str, float]
    retro_bodies: List[str] = list(ANNUAL_RETRO_BODIES)
    ingress_bodies: List[str] = list(ANNUAL_INGRESS_BODIES)

    @field_validator('start_instant')
    @classmethod
    def validate_annual_start(cls, v):
        try:
            datetime.fromisoformat(v)
        except ValueError:
            raise ValueError('start_instant must be an ISO datetime (YYYY-MM-DDTHH:MM:SS)')
        return v

    @field_validator('span_days')
    @classmethod
    def validate_annual_span(cls, v):
        if v < 1 or v > 400:
            raise ValueError('span_days must be between 1 and 400')
        return v

    @field_validator('sun_targets')
    @classmethod
    def validate_annual_targets(cls, v):
        unknown = [k for k in v if k not in ANNUAL_SUN_TARGET_KEYS]
        if unknown:
            raise ValueError(f"sun_targets keys are {ANNUAL_SUN_TARGET_KEYS}; unknown: {unknown}")
        for key, lon in v.items():
            if lon < 0 or lon > 360:
                raise ValueError(f'{key} longitude must be between 0 and 360')
        return v

    @field_validator('retro_bodies')
    @classmethod
    def validate_annual_retro_bodies(cls, v):
        unknown = [b for b in v if b not in STATION_PLANET_IDS]
        if unknown:
            raise ValueError(f"Bodies that station are {sorted(STATION_PLANET_IDS)}; unknown: {unknown}")
        return v

    @field_validator('ingress_bodies')
    @classmethod
    def validate_annual_ingress_bodies(cls, v):
        unknown = [b for b in v if b not in INGRESS_PLANET_IDS]
        if unknown:
            raise ValueError(f"Known bodies are {sorted(INGRESS_PLANET_IDS)}; unknown: {unknown}")
        return v



def annual_placement(jd: float, planet_id: int, natal_cusps) -> dict:
    """A body's longitude/sign/degree/speed at an instant plus its NATAL house."""
    lon, speed = returns_body_state(jd, planet_id)
    sign_data = lon_to_sign_degree(lon)
    return {
        "date": jd_to_iso(jd),
        "jd": round(jd, 6),
        "longitude": round(lon, 6),
        "sign": sign_data["sign"],
        "degree": round(sign_data["degree"], 4),
        "speed": round(speed, 6),
        "retrograde": speed < 0,
        "natal_house": get_planet_house(lon, natal_cusps),
    }


def eclipse_type_label(retflag: int, lunar: bool) -> str:
    if retflag & swe.ECL_ANNULAR_TOTAL:
        return "hybrid"
    if retflag & swe.ECL_TOTAL:
        return "total"
    if retflag & swe.ECL_ANNULAR:
        return "annular"
    if retflag & swe.ECL_PENUMBRAL:
        return "penumbral"
    if retflag & swe.ECL_PARTIAL:
        return "partial"
    return "lunar" if lunar else "solar"


def find_eclipses(start_jd: float, end_jd: float, natal_cusps) -> list:
    """Every solar and lunar eclipse whose maximum falls in [start, end], with
    the eclipsed luminary's sign (Sun for a solar eclipse, Moon for a lunar
    one — the sign the eclipse is named by) and its natal house. Penumbral
    lunar eclipses are included: astrologers count them, and the template's
    sample lists the penumbral eclipse of 2027-02-20."""
    eclipses = []
    for kind, finder, planet_id in (
        ("solar", lambda jd: swe.sol_eclipse_when_glob(jd, swe.FLG_SWIEPH, 0), swe.SUN),
        ("lunar", lambda jd: swe.lun_eclipse_when(jd, swe.FLG_SWIEPH, 0), swe.MOON),
    ):
        jd = start_jd
        while True:
            retflag, tret = finder(jd)
            jd_max = tret[0]
            if jd_max > end_jd:
                break
            placement = annual_placement(jd_max, planet_id, natal_cusps)
            del placement["speed"], placement["retrograde"]
            eclipses.append({"kind": kind, "type": eclipse_type_label(retflag, kind == "lunar"), **placement})
            jd = jd_max + 1.0
    eclipses.sort(key=lambda e: e["jd"])
    return eclipses


def find_retrograde_periods(bodies, start_jd: float, end_jd: float, natal_cusps) -> list:
    """Retrograde periods (station retrograde → station direct) of each body
    that overlap [start, end]. A period is included when any part of it falls
    inside the year, so a retrograde already under way at the start counts."""
    scan_start = start_jd - ANNUAL_STATION_PAD_DAYS
    scan_end = end_jd + ANNUAL_STATION_PAD_DAYS
    stations = scan_stations(bodies, scan_start, scan_end)
    periods = []
    for body in bodies:
        own = [s for s in stations if s["body"] == body]
        planet_id = STATION_PLANET_IDS[body]
        for i, station in enumerate(own):
            if station["type"] != "retrograde":
                continue
            direct = next((s for s in own[i + 1:] if s["type"] == "direct"), None)
            retro_jd = station["jd"]
            direct_jd = direct["jd"] if direct else None
            overlaps = retro_jd < end_jd and (direct_jd is None or direct_jd > start_jd)
            if not overlaps:
                continue
            periods.append({
                "body": body,
                "start": annual_placement(retro_jd, planet_id, natal_cusps),
                "end": annual_placement(direct_jd, planet_id, natal_cusps) if direct_jd is not None else None,
            })
    periods.sort(key=lambda p: p["start"]["jd"])
    return periods


def find_sign_boundary(planet_id: int, start_jd: float, step: float, forward: bool) -> Optional[float]:
    """The nearest instant a body's sign changes, walking forward or backward
    from start_jd up to ANNUAL_INGRESS_HORIZON_DAYS, bisected to ~30 s. When
    walking backward the returned instant is the moment the body ENTERED the
    sign it holds at start_jd (in whichever direction it was moving)."""
    def sign_of(jd: float) -> int:
        return int((get_transit_lon(jd, planet_id) % 360.0) // 30)

    direction = 1.0 if forward else -1.0
    limit = start_jd + direction * ANNUAL_INGRESS_HORIZON_DAYS
    jd = start_jd
    prev_sign = sign_of(jd)
    while (jd < limit) if forward else (jd > limit):
        jd_next = jd + direction * step
        if sign_of(jd_next) != prev_sign:
            lo, hi = (jd, jd_next) if forward else (jd_next, jd)
            return bisect_classification(lo, hi, sign_of)
        jd = jd_next
    return None


def find_sign_transitions(bodies, start_jd: float, natal_cusps) -> list:
    """Per body: the sign it holds at start_jd with the instant it entered
    that sign (its most recent ingress into it, any direction), and its next
    sign change after start_jd (any direction — a retrograde re-entry counts
    and is flagged), each placed on the natal wheel."""
    transitions = []
    for body in bodies:
        planet_id = INGRESS_PLANET_IDS[body]
        step = INGRESS_STEP_DAYS[body]
        entered_jd = find_sign_boundary(planet_id, start_jd, step, forward=False)
        next_jd = find_sign_boundary(planet_id, start_jd, step, forward=True)
        if entered_jd is None or next_jd is None:
            raise HTTPException(status_code=500, detail=f"No sign boundary for {body} within the search horizon")
        current_sign = lon_to_sign_degree(get_transit_lon(start_jd, planet_id))["sign"]
        # Sample a hair past each boundary so the placement reports the sign
        # actually entered rather than the boundary degree itself.
        entered = annual_placement(entered_jd + 1e-4, planet_id, natal_cusps)
        entered["date"] = jd_to_iso(entered_jd)
        entered["jd"] = round(entered_jd, 6)
        nxt = annual_placement(next_jd + 1e-4, planet_id, natal_cusps)
        nxt["date"] = jd_to_iso(next_jd)
        nxt["jd"] = round(next_jd, 6)
        transitions.append({
            "body": body,
            "current": {**entered, "sign": current_sign},
            "next": {**nxt, "from": current_sign},
        })
    return transitions


def find_sun_conjunctions(targets: Dict[str, float], start_jd: float, natal_cusps) -> dict:
    """The first exact conjunction of the transiting Sun with each natal
    target longitude after start_jd (one per tropical year)."""
    hits = {}
    for key, target_lon in targets.items():
        crossings = find_return_crossings(
            swe.SUN, target_lon % 360.0, start_jd, start_jd + ANNUAL_SUN_SEARCH_DAYS,
            ANNUAL_SUN_STEP_DAYS, departed=True)
        if not crossings:
            raise HTTPException(status_code=500, detail=f"No Sun conjunction with {key} found within a year")
        hits[key] = annual_placement(crossings[0], swe.SUN, natal_cusps)
    return hits


@app.post("/api/annual-transits")
def get_annual_transits(request: AnnualTransitsRequest, api_key: str = Security(verify_api_key)):
    """One chart's transit year from start_instant: Sun conjunctions with the
    natal targets, eclipses, overlapping retrograde periods, and the outer
    planets' current and next signs — every placement with its natal house."""
    logger.info(f"Annual transits requested from {request.start_instant} for {request.span_days} days")
    try:
        start_dt = datetime.fromisoformat(request.start_instant)
        start_jd = swe.julday(
            start_dt.year, start_dt.month, start_dt.day,
            start_dt.hour + start_dt.minute / 60.0 + start_dt.second / 3600.0,
            swe.GREG_CAL,
        )
        end_jd = start_jd + float(request.span_days)
        birth_jd = calculate_julian_day(
            request.birth_year, request.birth_month, request.birth_day,
            request.birth_hour, request.birth_min, request.lat, request.lon,
        )
        if start_jd < birth_jd:
            raise HTTPException(status_code=422, detail="start_instant is before the birth instant")
        _, natal_cusps = calculate_houses_for_jd(birth_jd, request.lat, request.lon, request.house_type)

        return {
            "start_instant": request.start_instant,
            "end_instant": jd_to_iso(end_jd),
            "cusps": [round(c % 360.0, 6) for c in natal_cusps[:12]],
            "sun_conjunctions": find_sun_conjunctions(request.sun_targets, start_jd, natal_cusps),
            "eclipses": find_eclipses(start_jd, end_jd, natal_cusps),
            "retrogrades": find_retrograde_periods(request.retro_bodies, start_jd, end_jd, natal_cusps),
            "sign_transitions": find_sign_transitions(request.ingress_bodies, start_jd, natal_cusps),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating annual transits: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


# ── Lifetime returns ─────────────────────────────────────────────────────────
# Every exact return of each body over a whole life, from the birth instant,
# plus the opposition passes of the slow bodies that oppose their natal degree
# once in a lifetime (Uranus, mid-life). Built for the TMG Lifetime Returns
# report (admin Astrology Reports tab): a table of return dates by age. Lunar
# returns are excluded by design (thirteen a year — a monthly product, not a
# lifetime one). The crossing walk is the /api/returns one — the departure
# gate applies from birth, so post-natal wobble is never a return.

LIFETIME_RETURN_BODIES = ["mercury", "venus", "sun", "mars", "jupiter", "saturn", "uranus"]
LIFETIME_OPPOSITION_BODIES = ["uranus"]
# Ages 20–125 on the report; the scan runs to the 126th birthday so age 125 is complete.
LIFETIME_SPAN_YEARS_DEFAULT = 126
LIFETIME_SPAN_YEARS_MAX = 130


class LifetimeReturnsRequest(NatalChartRequest):
    natal_positions: Dict[str, float]  # body → natal ecliptic longitude
    bodies: List[str] = list(LIFETIME_RETURN_BODIES)
    opposition_bodies: List[str] = list(LIFETIME_OPPOSITION_BODIES)
    span_years: int = LIFETIME_SPAN_YEARS_DEFAULT

    @field_validator('natal_positions')
    @classmethod
    def validate_lifetime_natal(cls, v):
        return validate_longitude_map(v)

    @field_validator('bodies', 'opposition_bodies')
    @classmethod
    def validate_lifetime_bodies(cls, v):
        unknown = [b for b in v if b not in INGRESS_PLANET_IDS or b == "moon"]
        if unknown:
            raise ValueError(f"Lifetime bodies are {sorted(b for b in INGRESS_PLANET_IDS if b != 'moon')}; unknown: {unknown}")
        return v

    @field_validator('span_years')
    @classmethod
    def validate_lifetime_span(cls, v):
        if v < 1 or v > LIFETIME_SPAN_YEARS_MAX:
            raise ValueError(f'span_years must be between 1 and {LIFETIME_SPAN_YEARS_MAX}')
        return v


def lifetime_crossing(jd: float, planet_id: int) -> dict:
    """One exact crossing instant: UT date, longitude, sign/degree, direction."""
    lon, speed = returns_body_state(jd, planet_id)
    sign_data = lon_to_sign_degree(lon)
    return {
        "date": jd_to_iso(jd),
        "longitude": round(lon, 6),
        "sign": sign_data["sign"],
        "degree": round(sign_data["degree"], 4),
        "is_retro": speed < 0,
    }


def lifetime_crossings(bodies, natal_positions, birth_jd: float, end_jd: float,
                       antipode: bool) -> dict:
    """Per body, every crossing of its natal longitude (or of the antipode —
    the opposition) from birth to end_jd. A scan from birth of the natal
    degree needs the departure gate; the antipode is 180° away at birth, so
    it is already 'departed'."""
    out = {}
    for body in bodies:
        planet_id = INGRESS_PLANET_IDS[body]
        target_lon = request_target_lon(natal_positions[body], antipode)
        crossings = find_return_crossings(
            planet_id, target_lon, birth_jd, end_jd, RETURN_STEP_DAYS[body], departed=antipode)
        out[body] = [lifetime_crossing(jd, planet_id) for jd in crossings]
    return out


def request_target_lon(natal_lon: float, antipode: bool) -> float:
    return (natal_lon + (180.0 if antipode else 0.0)) % 360.0


@app.post("/api/lifetime-returns")
def get_lifetime_returns(request: LifetimeReturnsRequest, api_key: str = Security(verify_api_key)):
    """Every exact return of each requested body from birth through
    span_years, and every opposition pass of the opposition bodies — dates
    only (the app buckets them by age). Retrograde multi-pass returns yield
    every pass, flagged."""
    logger.info(f"Lifetime returns requested for {request.bodies} over {request.span_years} years")
    try:
        missing = sorted({b for b in request.bodies + request.opposition_bodies if b not in request.natal_positions})
        if missing:
            raise HTTPException(status_code=422, detail=f"natal_positions missing bodies: {missing}")
        birth_jd = calculate_julian_day(
            request.birth_year, request.birth_month, request.birth_day,
            request.birth_hour, request.birth_min, request.lat, request.lon,
        )
        end_jd = birth_jd + request.span_years * 365.25
        return {
            "birth_instant": jd_to_iso(birth_jd),
            "end_instant": jd_to_iso(end_jd),
            "span_years": request.span_years,
            "returns": lifetime_crossings(request.bodies, request.natal_positions, birth_jd, end_jd, antipode=False),
            "oppositions": lifetime_crossings(request.opposition_bodies, request.natal_positions, birth_jd, end_jd, antipode=True),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating lifetime returns: {str(e)}")
