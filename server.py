"""
Swiss Ephemeris Python API Server
Uses the same Swiss Ephemeris library as your working scripts!
"""

from fastapi import FastAPI, HTTPException, Security, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
import swisseph as swe
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from timezonefinder import TimezoneFinder
import pytz
import os

app = FastAPI(title="Swiss Ephemeris API", version="1.0.0")

# API Key Security
API_KEY = os.getenv("API_KEY", "your-secret-key-here")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(api_key: str = Security(api_key_header)):
    """Verify the API key from request header"""
    if api_key is None:
        raise HTTPException(status_code=403, detail="API key is missing")
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

# Request models
class ChartRequest(BaseModel):
    year: int
    month: int
    day: int
    hour: int
    min: int
    lat: float
    lon: float
    house_type: Optional[str] = "placidus"

# Helper functions
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
                    "isRetro": "true" if speed < 0 else "false"
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
                    "isRetro": "true" if speed < 0 else "false"
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

# Transit Request Model
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

def angle_separation(lon1: float, lon2: float) -> float:
    """Calculate angle separation between two longitudes"""
    diff = abs((lon1 - lon2) % 360)
    return diff if diff <= 180 else 360 - diff

def get_transit_lon(jd: float, planet_id: int) -> float:
    """Get transit planet longitude at Julian Day"""
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

        # Planet IDs
        planet_ids = {
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

        # Step sizes (optimized for speed while maintaining precision)
        STEP_CONJ = 0.2  # Days (was 0.05)
        STEP_OTHER = 0.4  # Days (was 0.1)

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

            # Get positions
            transit_lon = get_transit_lon(jd_ut, planet_ids[tname])
            natal_lon_val = request.natal_positions[nname]

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
                "natal_planet_ws_house": natal_planet_ws_house
            })

        # Sort by date
        result_transits.sort(key=lambda x: x["date"])

        return {
            "transits": result_transits,
            "count": len(result_transits)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating transits: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
