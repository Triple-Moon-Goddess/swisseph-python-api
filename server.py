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

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(title="Swiss Ephemeris API", version="1.0.0")

# API Key Security
API_KEY = os.getenv("API_KEY", "your-secret-key-here")
API_KEY_HASH = hashlib.sha256(API_KEY.encode()).hexdigest()  # For secure logging
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(api_key: str = Security(api_key_header)):
    """Verify the API key from request header"""
    if api_key is None:
        logger.warning("API key missing")
        raise HTTPException(status_code=403, detail="API key is missing")

    if api_key != API_KEY:
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
    logger.info(f"Planets calculation requested for {request.year}-{request.month}-{request.day}")
    try:
        # Calculate Julian Day (with timezone conversion based on location)
        jd = calculate_julian_day(request.year, request.month, request.day,
                                 request.hour, request.min, request.lat, request.lon)

        result = {}

        # Calculate each planet
        for name, planet_id in PLANETS.items():
            try:
                # All bodies use Swiss Ephemeris with .se1 files
                print(f"Calculating {name} (id={planet_id})...")
                xx, ret = swe.calc_ut(jd, planet_id, swe.FLG_SWIEPH | swe.FLG_SPEED)
                print(f"  Success: {name} longitude={xx[0]}")

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
    logger.info(f"Houses calculation requested for {request.year}-{request.month}-{request.day}")
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
    logger.info(f"Complete chart requested for {request.year}-{request.month}-{request.day}")
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

@app.post("/api/stations")
def get_stations(request: StationsRequest, api_key: str = Security(verify_api_key)):
    """Exact station events (retrograde/direct turns) over a date window"""
    logger.info(f"Station scan requested: {request.start_date} to {request.end_date}")
    try:
        start_dt = datetime.fromisoformat(request.start_date)
        end_dt = datetime.fromisoformat(request.end_date)
        start_jd = swe.julday(start_dt.year, start_dt.month, start_dt.day, 0.0, swe.GREG_CAL)
        end_jd = swe.julday(end_dt.year, end_dt.month, end_dt.day, 0.0, swe.GREG_CAL)

        STEP_DAYS = 1.0  # slow-planet speed changes sign over weeks; daily scan cannot skip a turn
        stations = []
        for body in request.bodies:
            planet_id = STATION_PLANET_IDS[body]
            jd = start_jd
            prev_speed = get_transit_speed(jd, planet_id)
            while jd < end_jd:
                jd_next = min(jd + STEP_DAYS, end_jd)
                speed = get_transit_speed(jd_next, planet_id)
                if prev_speed * speed <= 0.0 and prev_speed != speed:
                    jd_station = bisect_station(jd, jd_next, planet_id)
                    y, m, d, fh = swe.revjul(jd_station, swe.GREG_CAL)
                    H = int(fh)
                    M = int((fh - H) * 60)
                    S = int((((fh - H) * 60) - M) * 60)
                    lon_data = lon_to_sign_degree(get_transit_lon(jd_station, planet_id))
                    stations.append({
                        "body": body,
                        "date": datetime(y, m, d, H, M, S).isoformat(),
                        "jd": round(jd_station, 6),
                        "longitude": round(get_transit_lon(jd_station, planet_id), 6),
                        "sign": lon_data["sign"],
                        "degree": round(lon_data["degree"], 4),
                        "type": "direct" if prev_speed < 0 else "retrograde"
                    })
                prev_speed = speed
                jd = jd_next

        stations.sort(key=lambda s: s["jd"])
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
