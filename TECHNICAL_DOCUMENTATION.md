# Swiss Ephemeris Astrology API - Technical Documentation

## Table of Contents
1. [System Architecture](#system-architecture)
2. [Technology Stack](#technology-stack)
3. [API Endpoints](#api-endpoints)
4. [Authentication](#authentication)
5. [Google Apps Script Integration](#google-apps-script-integration)
6. [Deployment](#deployment)
7. [Code Structure](#code-structure)
8. [Development Setup](#development-setup)
9. [Extending the System](#extending-the-system)

---

## System Architecture

### Overview
A three-tier architecture for calculating astrological charts and transits:

```
┌─────────────────────┐
│  Google Sheets UI   │
│  (User Interface)   │
└──────────┬──────────┘
           │ Google Apps Script
           │ (API Calls)
           ▼
┌─────────────────────┐
│   FastAPI Server    │
│  (Business Logic)   │
│   Railway.app       │
└──────────┬──────────┘
           │ Python pyswisseph
           │ (Calculations)
           ▼
┌─────────────────────┐
│  Swiss Ephemeris    │
│  (.se1 data files)  │
└─────────────────────┘
```

### Components

**Frontend: Google Sheets + Apps Script**
- User-friendly spreadsheet interface
- No installation required
- Automatic geocoding via Google Maps API
- Menu-driven operations

**Backend: FastAPI (Python)**
- RESTful API endpoints
- Swiss Ephemeris C library via pyswisseph
- Timezone conversion with TimezoneFinder
- API key authentication

**Hosting: Railway.app**
- Automatic deployment from GitHub
- Environment variable management
- HTTPS/SSL included
- Free tier available

---

## Technology Stack

### Backend
- **Python 3.11+**
- **FastAPI** - Modern web framework
- **pyswisseph** - Swiss Ephemeris library bindings
- **timezonefinder** - Location to timezone conversion
- **pytz** - Timezone handling
- **uvicorn** - ASGI server
- **slowapi** - Rate limiting middleware
- **python-json-logger** - Structured JSON logging
- **pydantic** - Data validation and settings management

### Frontend
- **Google Apps Script** (JavaScript ES6)
- **Google Sheets** - Data entry and visualization
- **Google Maps Geocoding API** - Location resolution

### Infrastructure
- **Railway.app** - Cloud hosting
- **GitHub** - Version control & CI/CD
- **Docker** - Containerization

---

## API Endpoints

### Base URL
```
https://swisseph-python-api-production.up.railway.app
```

### Authentication
All endpoints (except `/`) require API key in header:
```
X-API-Key: your-api-key-here
```

### Endpoints

#### `GET /`
Health check endpoint (public, no auth required)

**Response:**
```json
{
  "status": "ok",
  "service": "Swiss Ephemeris API",
  "version": "1.0.0",
  "endpoints": {
    "planets": "/api/planets",
    "houses": "/api/houses",
    "chart": "/api/chart"
  }
}
```

---

#### `POST /api/planets`
Get planetary positions for a specific date/time/location

**Request Body:**
```json
{
  "year": 1990,
  "month": 5,
  "day": 15,
  "hour": 14,
  "min": 30,
  "lat": 40.7128,
  "lon": -74.0060
}
```

**Response:**
```json
{
  "sun": {
    "longitude": 54.123456,
    "full_degree": 54.123456,
    "sign": "Taurus",
    "degree": 24.123456,
    "speed": 0.958,
    "isRetro": "false"
  },
  "moon": { ... },
  "mercury": { ... }
  // ... all planets, asteroids, nodes
}
```

**Planets Included:**
- Sun, Moon, Mercury, Venus, Mars
- Jupiter, Saturn, Uranus, Neptune, Pluto
- Chiron, Ceres, Pallas, Juno, Vesta
- True Node (North Node), Lilith (Black Moon)

---

#### `POST /api/houses`
Get house cusps and angles for a specific date/time/location

**Request Body:**
```json
{
  "year": 1990,
  "month": 5,
  "day": 15,
  "hour": 14,
  "min": 30,
  "lat": 40.7128,
  "lon": -74.0060,
  "house_type": "placidus"  // or "whole_sign", "koch", "equal", "campanus"
}
```

**Response:**
```json
{
  "ascendant": {
    "longitude": 120.456789,
    "sign": "Leo",
    "degree": 0.456789
  },
  "midheaven": { ... },
  "house1": { ... },
  "house2": { ... }
  // ... through house12
}
```

---

#### `POST /api/chart`
Get complete chart (planets + houses) in one call

**Request Body:** Same as `/api/planets` plus `house_type`

**Response:**
```json
{
  "planets": { ... },  // Same as /api/planets
  "houses": { ... }    // Same as /api/houses
}
```

---

#### `POST /api/transits`
Calculate exact transit aspects over a date range

**Request Body:**
```json
{
  "natal_positions": {
    "Sun": 54.123,
    "Moon": 120.456,
    "Mercury": 45.789
  },
  "start_date": "2025-01-01",
  "end_date": "2025-12-31",
  "lat": 40.7128,
  "lon": -74.0060,
  "birth_year": 1990,
  "birth_month": 5,
  "birth_day": 15,
  "birth_hour": 14,
  "birth_min": 30,
  "house_type": "placidus",
  "transiting_planets": ["jupiter", "saturn", "uranus", "neptune", "pluto"],
  "aspects": {
    "Conjunction": { "angle": 0, "orb": 1.0 },
    "Square": { "angle": 90, "orb": 1.0 },
    "Opposition": { "angle": 180, "orb": 1.0 },
    "Quincunx": { "angle": 150, "orb": 1.0 }
  },
  "step_days": 7
}
```

**Response:**
```json
{
  "transits": [
    {
      "date": "2025-03-15T10:30:00",
      "transit_planet": "jupiter",
      "natal_planet": "Sun",
      "aspect": "Conjunction",
      "separation": 0.000123,
      "transit_longitude": 54.123456,
      "natal_longitude": 54.123333,
      "transit_sign": "Taurus",
      "transit_degree": 24.1234,
      "natal_sign": "Taurus",
      "natal_degree": 24.1233,
      "transit_planet_house": 5,
      "natal_planet_house": 10,
      "transit_planet_ws_house": 6,
      "natal_planet_ws_house": 10
    }
  ],
  "count": 1
}
```

**Algorithm Details:**
- **Conjunctions**: Uses ternary search to find local minimum separations
- **Other Aspects**: Uses bisection method to find exact crossings
- **Precision**: ~0.002° for conjunctions, ~0.004-0.006° for other aspects
- **Performance**: Optimized step sizes (0.2-0.4 days) for fast calculation

---

## Authentication

### API Key Setup

**1. Generate a secure key:**
```bash
openssl rand -hex 32
```

**2. Set in Railway:**
- Go to Railway dashboard
- Select your project → Variables tab
- Add: `API_KEY` = `your-generated-key`

**3. Use in requests:**
```javascript
// Google Apps Script
const options = {
  method: 'post',
  headers: {
    'X-API-Key': 'your-api-key-here'
  },
  payload: JSON.stringify(data)
};
```

**Security:**
- All data endpoints require valid API key
- Returns 403 for missing/invalid keys
- Health check endpoint (/) remains public

**API Key Rotation Policy:**
- Recommended rotation: Every 90 days
- Generate new key: `openssl rand -hex 32`
- Update Railway environment variable
- Update both Google Apps Scripts with new key
- Monitor logs for old key usage before retiring

---

## Security Features

### Defense-in-Depth Architecture

The API implements multiple layers of security protection:

**Layer 1: API Key Authentication**
- Header-based authentication (`X-API-Key`)
- Environment variable configuration
- Secure logging with key hashing (SHA-256)
- Invalid attempts logged with IP address

**Layer 2: Rate Limiting**
```python
# Endpoint-specific limits
/api/planets:  100 requests/minute
/api/houses:   100 requests/minute
/api/chart:    100 requests/minute
/api/transits: 20 requests/minute  # Lower due to computational cost
```
- Uses `slowapi` library
- IP-based throttling
- Returns 429 (Too Many Requests) when exceeded
- Protects against DoS attacks and abuse

**Layer 3: CORS Restrictions**
```python
# Only allowed origins
https://docs.google.com
https://script.google.com
https://accounts.google.com
```
- Prevents unauthorized browser-based access
- Blocks cross-origin requests from unknown domains
- Development mode allows localhost

**Layer 4: Security Headers**
All responses include hardened security headers:
- `X-Content-Type-Options: nosniff` - Prevent MIME sniffing
- `X-Frame-Options: DENY` - Prevent clickjacking
- `X-XSS-Protection: 1; mode=block` - Enable XSS filtering
- `Strict-Transport-Security: max-age=31536000; includeSubDomains` - Force HTTPS
- `Content-Security-Policy: default-src 'self'` - Restrict resource loading
- `Referrer-Policy: strict-origin-when-cross-origin` - Limit referrer data
- `Permissions-Policy: geolocation=(), microphone=(), camera=()` - Disable sensitive APIs

**Layer 5: Input Validation**
Comprehensive validation on all request fields using Pydantic:

```python
# Date/Time validation
- year: 1800-2200
- month: 1-12
- day: 1-31
- hour: 0-23
- minute: 0-59

# Geographic validation
- latitude: -90 to 90
- longitude: -180 to 180

# Astrological validation
- house_type: must be in allowed list
- natal_positions: validated longitude ranges (0-360)
- aspect_names: validated against known aspects
- orbs: positive numbers only
```

**Layer 6: Structured Logging**
```python
# JSON-formatted logs for security monitoring
{
  "timestamp": "2025-12-18T10:30:45.123Z",
  "level": "WARNING",
  "message": "Invalid API key attempt",
  "client_ip": "192.168.1.1",
  "endpoint": "/api/chart",
  "method": "POST"
}
```
- All authentication attempts logged
- Failed validations tracked
- API key hash logged (not plaintext)
- Enables security incident investigation
- Compatible with log aggregation tools (Splunk, ELK, etc.)

### Security Best Practices

**For Administrators:**
1. Rotate API keys every 90 days
2. Monitor logs for suspicious activity
3. Review rate limit settings periodically
4. Keep dependencies updated (`pip list --outdated`)
5. Never commit API keys to version control
6. Use strong, random API keys (32+ characters)

**For Users:**
7. Keep API keys confidential
8. Don't share Google Sheets with untrusted parties
9. Use pseudonymization for client data (codes, not names)
10. Regularly audit who has access to the system

### Incident Response

**If API key is compromised:**
1. Immediately generate new key: `openssl rand -hex 32`
2. Update Railway environment variable
3. Update both Google Apps Scripts
4. Review logs for unauthorized usage
5. Document incident and response

**If suspicious activity detected:**
1. Check structured logs for patterns
2. Identify source IP addresses
3. Review rate limit violations
4. Consider temporary API key rotation
5. Contact Railway support if needed

### Compliance

The security architecture supports:
- **GDPR compliance** - Minimal data collection, pseudonymization
- **SOC 2 controls** - Authentication, logging, access control
- **HIPAA considerations** - De-identification of sensitive data (if applicable)
- **Privacy by Design** - Security built into architecture, not bolted on

---

## Google Apps Script Integration

### Files Structure

```
NatalCharts_SelfHosted.gs      # Natal chart calculations
Transits_SelfHosted_Updated.gs # Transit calculations
```

### Configuration

Both scripts require:
```javascript
const CONFIG = {
  API_BASE_URL: 'https://your-api.railway.app',
  API_KEY: 'your-secret-key',
  INPUT_SHEET: 'ChartInput',
  HOUSE_SYSTEM: 'placidus'
};
```

### Menu Functions

**Natal Charts:**
- `Process Charts (Placidus)` - Calculate charts with Placidus houses
- `Process Charts (Whole Sign)` - Calculate charts with Whole Sign houses

**Transits:**
- `Calculate Transits - Placidus (365 Days)` - Placidus house transits
- `Calculate Transits - Whole Sign (365 Days)` - Whole Sign house transits

**Testing:**
- `Test API Connection` - Verify natal chart API
- `Test Transit API Connection` - Verify transits API
- `Test Asteroids` - Check asteroid calculations
- `Test Aspects` - Verify aspect calculations

### Input Format

**ChartInput Sheet:**
| name | year | month | day | hour | minute | ampm | city | state | country |
|------|------|-------|-----|------|--------|------|------|-------|---------|
| A10001 | 1967 | 4 | 17 | 6 | 40 | AM | Englewood | NJ | USA |

### Output Sheets

**Natal Charts:** `{name}_{house_system}`
- Planetary positions with houses
- House cusps
- ASC/MC
- Aspect table

**Transits:** `Transits_{name}` or `Transits_{name}_WS`
- Date, transiting planet, natal planet
- Aspect type and separation
- House positions (both Placidus and Whole Sign)

---

## Deployment

### Initial Deployment

**1. Prepare Repository:**
```bash
cd /Users/lisa/swisseph/python-api-server
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/swisseph-python-api.git
git push -u origin main
```

**2. Deploy to Railway:**
- Go to railway.app
- New Project → Deploy from GitHub
- Select your repository
- Railway auto-detects Python/Dockerfile
- Wait for deployment (~3-5 minutes)

**3. Configure Environment:**
- Go to Variables tab
- Add `API_KEY` environment variable
- Railway will redeploy automatically

**4. Get API URL:**
- Copy the generated Railway URL
- Update Google Apps Scripts with this URL

### Continuous Deployment

Railway automatically deploys on every push to `main`:
```bash
git add .
git commit -m "Update feature"
git push origin main
# Railway deploys automatically in ~2-3 minutes
```

### Railway Configuration

**`railway.toml`:**
```toml
[build]
builder = "DOCKERFILE"

[deploy]
healthcheckPath = "/"
```

**`Dockerfile`:**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Code Structure

### Python API (`server.py`)

**Main Components:**
```python
# 1. Configuration & Setup
app = FastAPI()
API_KEY = os.getenv("API_KEY")
Structured JSON logging setup
Rate limiter configuration
Restricted CORS middleware (Google domains only)
Security headers middleware

# 2. Authentication & Security
verify_api_key() - API key validation with logging
add_security_headers() - Security headers middleware
Rate limiting decorators on all endpoints

# 3. Helper Functions
lon_to_sign_degree() - Convert longitude to sign/degree
calculate_julian_day() - Date/time to Julian Day with timezone
calculate_houses_for_jd() - Calculate houses for any JD
get_planet_house() - Determine planet's house (Placidus)
get_whole_sign_house() - Determine planet's house (Whole Sign)

# 4. API Endpoints
@app.get("/") - Health check
@app.post("/api/planets") - Planet positions
@app.post("/api/houses") - House cusps
@app.post("/api/chart") - Complete chart
@app.post("/api/transits") - Transit calculations

# 5. Transit Algorithms
angle_separation() - Calculate angle between planets
get_transit_lon() - Get transiting planet position
sep_func() - Separation function for optimization
gfunc() - Aspect function for root finding
bisect_root() - Find exact aspect crossing
find_min_sep_jd() - Find conjunction minimum
```

### Google Apps Script Structure

**Common Functions:**
```javascript
// Configuration
CONFIG / TRANSIT_CONFIG

// Geocoding
geocodeLocation() - Google Maps API integration

// Time Conversion
convertTo24Hour() - 12hr to 24hr format

// API Calls
getPlanetaryPositions() - Call /api/chart
getNatalPositions() - Get natal data for transits
findTransits() - Call /api/transits

// House Calculations
getHouseNumber() - Determine planet's house

// Aspects
findAspects() - Calculate aspects between planets

// Output
writeChartToSheet() - Format and write natal chart
writeTransitsToSheet() - Format and write transits
writeTransitsWholeSignsToSheet() - Format whole sign transits

// Menu
onOpen() - Create custom menu
processCharts() - Main natal chart processor
processTransits() - Main transit processor
processTransitsWholeSigns() - Whole sign transit processor
```

---

## Development Setup

### Local Development

**1. Clone Repository:**
```bash
git clone https://github.com/YOUR_USERNAME/swisseph-python-api.git
cd swisseph-python-api
```

**2. Create Virtual Environment:**
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

**3. Install Dependencies:**
```bash
pip install -r requirements.txt
```

**4. Download Ephemeris Files:**
```bash
python download_asteroids.py
```

**5. Set Environment Variable:**
```bash
export API_KEY="test-key-for-development"
```

**6. Run Server:**
```bash
uvicorn server:app --reload --port 8000
```

**7. Test:**
```bash
curl http://localhost:8000/
```

### Testing API Locally

**Test with curl:**
```bash
curl -X POST http://localhost:8000/api/planets \
  -H "Content-Type: application/json" \
  -H "X-API-Key: test-key-for-development" \
  -d '{
    "year": 1990,
    "month": 5,
    "day": 15,
    "hour": 14,
    "min": 30,
    "lat": 40.7128,
    "lon": -74.0060
  }'
```

**Test with Python:**
```python
import requests

response = requests.post(
    'http://localhost:8000/api/planets',
    headers={'X-API-Key': 'test-key-for-development'},
    json={
        'year': 1990,
        'month': 5,
        'day': 15,
        'hour': 14,
        'min': 30,
        'lat': 40.7128,
        'lon': -74.0060
    }
)
print(response.json())
```

---

## Extending the System

### Adding New Planets/Points

**1. Update PLANETS dictionary in `server.py`:**
```python
PLANETS = {
    "sun": swe.SUN,
    # ... existing planets ...
    "eris": 136199,  # Add new dwarf planet
}
```

**2. Download data file (if needed):**
```python
# In download_asteroids.py
ASTEROIDS = [
    # ... existing ...
    (136199, "Eris"),
]
```

### Adding New Aspects

**1. Update aspect configuration in transit request:**
```javascript
aspects: {
  "Conjunction": { angle: 0, orb: 1.0 },
  "Trine": { angle: 120, orb: 1.0 },  // Add new aspect
  // ... others
}
```

**2. Update tolerance in API:**
```python
tolerances = {
    "Conjunction": 0.002,
    "Trine": 0.004,  # Add tolerance
    # ... others
}
```

### Adding New House Systems

**1. Update HOUSE_SYSTEMS:**
```python
HOUSE_SYSTEMS = {
    "placidus": b"P",
    "whole_sign": b"W",
    "regiomontanus": b"R",  # Add new system
}
```

**2. Update Google Apps Script:**
```javascript
HOUSE_SYSTEMS: {
  P: 'placidus',
  W: 'whole_sign',
  R: 'regiomontanus'  // Add new
}
```

### Custom Calculations

Add custom endpoints for specialized calculations:

```python
@app.post("/api/progressions")
def get_progressions(request: ProgressionRequest, api_key: str = Security(verify_api_key)):
    """Calculate secondary progressions"""
    # Your custom logic here
    pass
```

---

## Troubleshooting

### Common Issues

**"API key is missing" Error:**
- Check header name is exactly `X-API-Key`
- Verify key is set in Google Apps Script config
- Check for typos

**"Geocoding failed" Error:**
- Verify location data is accurate
- Check Google Maps API quota
- Try with full address (city, state, country)

**Slow Transit Calculations:**
- Reduce `PERIOD_DAYS` (currently 365)
- Increase `step_days` (currently 7)
- Limit aspects or planets

**Railway Deployment Fails:**
- Check Railway logs for errors
- Verify `requirements.txt` is up to date
- Ensure ephemeris files are in `ephe/` directory
- Check Dockerfile syntax

### Debug Mode

Enable detailed logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Performance Optimization

**Transit Calculations:**
- Current: ~2-3 seconds for 365 days
- Optimize by adjusting step sizes
- Cache natal house calculations
- Use parallel processing for multiple charts

---

## Version History

**v1.0.0 (Current)**
- Natal chart calculations (planets + houses)
- Transit calculations with house positions
- Placidus and Whole Sign house systems
- API key authentication
- Google Sheets integration
- Railway deployment

---

## Support & Resources

**Documentation:**
- Swiss Ephemeris: https://www.astro.com/swisseph/
- pyswisseph: https://astrorigin.com/pyswisseph/
- FastAPI: https://fastapi.tiangolo.com/

**Repository:**
- GitHub: https://github.com/TripleMoonGoddess/swisseph-python-api

**Contact:**
- Create GitHub issue for bugs/features
- Check Railway logs for deployment issues

---

**Last Updated:** December 18, 2025
**Maintained By:** Lisa / Triple Moon Goddess
