"""
Swiss Ephemeris Python API Server
Uses the same Swiss Ephemeris library as your working scripts!
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import swisseph as swe
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from timezonefinder import TimezoneFinder
import pytz

app = FastAPI(title="Swiss Ephemeris API", version="1.0.0")

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
def get_planets(request: ChartRequest):
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
def get_houses(request: ChartRequest):
    """Get house cusps"""
    try:
        # Calculate Julian Day (with timezone conversion based on location)
        jd = calculate_julian_day(request.year, request.month, request.day,
                                 request.hour, request.min, request.lat, request.lon)

        # Get house system
        house_system = HOUSE_SYSTEMS.get(request.house_type, b"P")

        # Calculate houses
        cusps, ascmc = swe.houses(jd, request.lat, request.lon, house_system)

        result = {}

        # Add ascendant and midheaven
        asc_data = lon_to_sign_degree(ascmc[0])
        mc_data = lon_to_sign_degree(ascmc[1])

        result["ascendant"] = {
            "longitude": ascmc[0],
            "full_degree": asc_data["full_degree"],
            **asc_data
        }

        result["midheaven"] = {
            "longitude": ascmc[1],
            "full_degree": mc_data["full_degree"],
            **mc_data
        }

        # Add all 12 houses
        for i in range(12):
            house_lon = cusps[i]
            house_data = lon_to_sign_degree(house_lon)
            result[f"house{i+1}"] = {
                "longitude": house_lon,
                "full_degree": house_data["full_degree"],
                **house_data
            }

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating houses: {str(e)}")

@app.post("/api/chart")
def get_chart(request: ChartRequest):
    """Get complete chart data (planets + houses)"""
    try:
        planets = get_planets(request)
        houses = get_houses(request)

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
def get_transits(request: TransitRequest):
    """Calculate exact transits using precision algorithms"""
    try:
        transits = []

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
                "natal_degree": round(natal_sign_data["degree"], 4)
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
