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

app = FastAPI(title="Swiss Ephemeris API", version="1.0.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set ephemeris path - try multiple locations
import os
# First try our custom path, then pyswisseph package data, then let swisseph use defaults
ephe_paths = [
    '/app/ephe',
    os.path.join(os.path.dirname(swe.__file__), 'data'),
    None  # Let swisseph use its default search paths
]

for path in ephe_paths:
    if path and os.path.exists(path):
        swe.set_ephe_path(path)
        break
    elif path is None:
        # Don't set path, let swisseph use defaults
        pass

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
    "chiron": swe.CHIRON,
    "ceres": swe.CERES,
    "pallas": swe.PALLAS,
    "juno": swe.JUNO,
    "vesta": swe.VESTA,
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

def calculate_julian_day(year: int, month: int, day: int, hour: int, minute: int):
    """Calculate Julian Day"""
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
        # Calculate Julian Day
        jd = calculate_julian_day(request.year, request.month, request.day,
                                 request.hour, request.min)

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
        # Calculate Julian Day
        jd = calculate_julian_day(request.year, request.month, request.day,
                                 request.hour, request.min)

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

@app.post("/api/transits")
def get_transits(request: TransitRequest):
    """Calculate transits - server-side scanning for speed"""
    try:
        transits = []

        # Parse dates
        start_dt = datetime.fromisoformat(request.start_date)
        end_dt = datetime.fromisoformat(request.end_date)

        # Map planet names to IDs
        planet_ids = {
            "jupiter": swe.JUPITER,
            "saturn": swe.SATURN,
            "uranus": swe.URANUS,
            "neptune": swe.NEPTUNE,
            "pluto": swe.PLUTO
        }

        # For each transiting planet
        for transit_planet_name in request.transiting_planets:
            if transit_planet_name not in planet_ids:
                continue

            planet_id = planet_ids[transit_planet_name]

            # For each natal planet
            for natal_planet, natal_lon in request.natal_positions.items():

                # For each aspect
                for aspect_name, aspect_data in request.aspects.items():

                    # Scan dates
                    current_dt = start_dt
                    while current_dt <= end_dt:
                        # Calculate Julian Day
                        jd = swe.julday(current_dt.year, current_dt.month, current_dt.day,
                                       current_dt.hour + current_dt.minute / 60.0, swe.GREG_CAL)

                        # Get transiting planet position
                        try:
                            xx, ret = swe.calc_ut(jd, planet_id, swe.FLG_SWIEPH | swe.FLG_SPEED)
                        except:
                            xx, ret = swe.calc_ut(jd, planet_id, swe.FLG_MOSEPH | swe.FLG_SPEED)

                        transit_lon = xx[0]

                        # Check if aspect is forming
                        separation = angle_separation(transit_lon, natal_lon)
                        orb_from_exact = abs(separation - aspect_data["angle"])

                        if orb_from_exact <= aspect_data["orb"]:
                            # Found a transit!
                            transit_sign_data = lon_to_sign_degree(transit_lon)
                            natal_sign_data = lon_to_sign_degree(natal_lon)

                            transits.append({
                                "date": current_dt.isoformat(),
                                "transit_planet": transit_planet_name,
                                "natal_planet": natal_planet,
                                "aspect": aspect_name,
                                "separation": round(separation, 6),
                                "orb": round(orb_from_exact, 6),
                                "transit_longitude": round(transit_lon, 6),
                                "natal_longitude": round(natal_lon, 6),
                                "transit_sign": transit_sign_data["sign"],
                                "transit_degree": round(transit_sign_data["degree"], 4),
                                "natal_sign": natal_sign_data["sign"],
                                "natal_degree": round(natal_sign_data["degree"], 4)
                            })

                            # Skip ahead to avoid duplicates
                            current_dt += timedelta(days=30)
                            continue

                        # Move to next date
                        current_dt += timedelta(days=request.step_days)

        # Sort by date
        transits.sort(key=lambda x: x["date"])

        return {
            "transits": transits,
            "count": len(transits)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating transits: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
