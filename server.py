"""
Swiss Ephemeris Python API Server
Uses the same Swiss Ephemeris library as your working scripts!
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import swisseph as swe
from datetime import datetime
from typing import Optional

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
swe.set_ephe_path('/app/ephe')

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
    "vesta": swe.VESTA
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
                # Calculate planet position
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
                    "isRetro": "true" if speed < 0 else "false"
                }
            except Exception as e:
                print(f"Error calculating {name}: {e}")
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
