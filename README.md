# Swiss Ephemeris Astrology System

Professional astrology calculations powered by Swiss Ephemeris, delivered through Google Sheets.

## Quick Links

⚠️ **[NO SUPPORT POLICY](NO_SUPPORT.md)** - READ THIS FIRST - No support obligation, you're on your own!

📘 **[Business Documentation](BUSINESS_DOCUMENTATION.md)** - For non-technical users, what this system does and why it's valuable

🔧 **[Technical Documentation](TECHNICAL_DOCUMENTATION.md)** - For developers, complete technical reference and API documentation

🔑 **[API Key Setup Guide](python-api-server/API_KEY_SETUP.md)** - Security setup instructions

## What This Is

A professional-grade astrology calculation REST API powered by Swiss Ephemeris:
- **Swiss Ephemeris** - Industry-standard astronomical calculations
- **FastAPI Server** - Fast, modern REST API
- **Self-Hosted** - Deploy your own private instance
- **Railway Hosting** - Easy cloud deployment (or host anywhere)

## Features

✨ **Natal Charts**
- All planets, asteroids, nodes, Lilith
- Multiple house systems (Placidus, Whole Sign, Koch, Equal, Campanus)
- Complete aspect tables
- Batch processing

🌟 **Transits**
- 365-day transit tracking
- Exact aspect timing
- House positions (Placidus & Whole Sign)
- Jupiter, Saturn, Uranus, Neptune, Pluto

🔒 **Security**
- API key authentication
- Private server
- Your data only

## License

This project is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**.

**What this means:**
- ✅ You can use this commercially (charge for astrology services)
- ✅ You can modify and distribute the code
- ✅ Source code must remain open and available
- ✅ Network use requires providing source code access

This software uses **Swiss Ephemeris** by Astrodienst AG, which is also AGPL-3.0 licensed.

For full license text, see [LICENSE](LICENSE) file.

**Commercial Use:** You may charge clients for astrology readings and services using this software. The AGPL requires that you provide access to the source code to anyone using your service over a network.

## Quick Start

### Prerequisites
- GitHub account (free)
- Railway account (free tier available)
- Google account (for Google Sheets)
- Terminal access (for generating API key)

### Step 1: Fork/Clone This Repository

**Option A: Fork on GitHub (Recommended)**
1. Click "Fork" button at top of this repository
2. You now have your own copy!

**Option B: Clone to your machine**
```bash
git clone https://github.com/TripleMoonGoddess/swisseph-python-api.git
cd swisseph-python-api
```

### Step 2: Deploy to Railway

1. **Create Railway Account**
   - Go to https://railway.app
   - Sign up with GitHub
   - Free tier: 500 hours/month ($5/month unlimited)

2. **Deploy from GitHub**
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose your forked repository
   - Railway auto-detects Python and deploys (~3 minutes)

3. **Get Your API URL**
   - Click on your service
   - Go to "Settings" tab
   - Find "Public Domain" (e.g., `https://yourapp.up.railway.app`)
   - Copy this URL - you'll need it!

### Step 3: Generate and Configure API Key

1. **Generate Secure Key**
   ```bash
   openssl rand -hex 32
   ```
   Copy the output (64 characters)

2. **Set in Railway**
   - In Railway project, click "Variables" tab
   - Click "New Variable"
   - Name: `API_KEY`
   - Value: (paste your generated key)
   - Click "Add"
   - Railway will automatically redeploy (~2 minutes)

3. **Save Your Key**
   - Keep this key secure!
   - You'll need it for Google Sheets setup

### Step 4: Test Your API

Test that it's working:

```bash
# Test health check (no API key needed)
curl https://yourapp.up.railway.app/

# Test with API key
curl -X POST https://yourapp.up.railway.app/api/chart \
  -H "X-API-Key: your-api-key-here" \
  -H "Content-Type: application/json" \
  -d '{
    "year": 1967,
    "month": 4,
    "day": 17,
    "hour": 6,
    "min": 40,
    "lat": 40.8933,
    "lon": -73.9714,
    "house_type": "placidus"
  }'
```

You should get JSON back with planetary positions and houses! 🎉

### Step 5: Build Your Client

Now build whatever interface you want:

**Python Script:**
```python
import requests

def get_chart(year, month, day, hour, min, lat, lon):
    response = requests.post(
        'https://yourapp.up.railway.app/api/chart',
        headers={'X-API-Key': 'your-api-key'},
        json={
            'year': year, 'month': month, 'day': day,
            'hour': hour, 'min': min,
            'lat': lat, 'lon': lon,
            'house_type': 'placidus'
        }
    )
    return response.json()

chart = get_chart(1967, 4, 17, 6, 40, 40.8933, -73.9714)
print(chart)
```

**Web App, Mobile App, Google Sheets, Excel VBA, etc.**
- See [TECHNICAL_DOCUMENTATION.md](TECHNICAL_DOCUMENTATION.md) for API endpoints
- Build any client you want!
- The API doesn't care what calls it

## Troubleshooting

### ❌ "API key missing" error
**Fix:** Update API_KEY in both Google Apps Scripts (Step 4.4)

### ❌ "Failed to fetch" error
**Fix:** Check API_BASE_URL matches your Railway domain exactly

### ❌ Menu doesn't appear
**Fix:** Refresh Google Sheets after adding scripts

### ❌ "Unknown error" or "Internal Server Error"
**Fix:**
1. Wait 2-3 minutes for Railway to finish deploying
2. Check Railway logs for errors
3. Verify API_KEY is set in Railway Variables

### ❌ Wrong birth location
**Fix:** Use full city name, state, country (e.g., "Portland, OR, USA" not just "Portland")

### 💡 Need Help?
- Your teacher can paste error messages into Claude for help
- Check [TECHNICAL_DOCUMENTATION.md](TECHNICAL_DOCUMENTATION.md) for details
- Open GitHub issue for bugs

## Using the API

Once deployed, you can call the API from any programming language or tool:

**Available Endpoints:**
- `GET /` - Health check
- `POST /api/planets` - Get planetary positions
- `POST /api/houses` - Get house cusps
- `POST /api/chart` - Get complete chart (planets + houses)
- `POST /api/transits` - Calculate transits

**Authentication:**
All endpoints require `X-API-Key` header (except health check).

**Documentation:**
See [TECHNICAL_DOCUMENTATION.md](TECHNICAL_DOCUMENTATION.md) for complete API reference with examples.

## Repository Structure

```
python-api-server/
├── README.md (this file)
├── server.py - FastAPI application
├── requirements.txt - Python dependencies
├── Dockerfile - Container config
├── railway.toml - Railway configuration
├── ephe/ - Swiss Ephemeris data files
│
├── Documentation:
├── TECHNICAL_DOCUMENTATION.md - Complete API reference
├── BUSINESS_DOCUMENTATION.md - Business overview
├── AGPL_COMPLIANCE.md - License guide
├── NO_SUPPORT.md - Support policy
│
└── License:
    ├── LICENSE - AGPL-3.0 full text
    └── NOTICE - Copyright notices
```

## For Different Audiences

### 👥 **Non-Technical Users**
Start with: [BUSINESS_DOCUMENTATION.md](BUSINESS_DOCUMENTATION.md)
- What the system does
- Why it's valuable
- How to use it
- Comparison with alternatives

### 👨‍💻 **Developers**
Start with: [TECHNICAL_DOCUMENTATION.md](TECHNICAL_DOCUMENTATION.md)
- API endpoints
- Code structure
- Deployment guide
- Extension instructions

### 🔐 **Setup Assistance**
Start with: [API_KEY_SETUP.md](python-api-server/API_KEY_SETUP.md)
- Generate API key
- Configure Railway
- Update scripts
- Test connection

## Technology Stack

- **Backend:** Python 3.11, FastAPI, pyswisseph
- **API:** REST/JSON
- **Hosting:** Railway.app (or any Docker host)
- **Data:** Swiss Ephemeris .se1 files
- **Client:** Build your own (Python, JavaScript, whatever!)

## Repository

GitHub: https://github.com/TripleMoonGoddess/swisseph-python-api

## Costs

- **Development:** Free (open source)
- **Hosting:** Free tier or $5/month unlimited
- **Total:** $0-5/month

## Support

**⚠️ No Support Obligation**

This is open source software provided "AS IS" with NO WARRANTY and NO SUPPORT OBLIGATION.

- 📖 Read the documentation - it's comprehensive
- 🤖 Use Claude AI to help with setup/troubleshooting
- 💬 Community support via GitHub discussions (if I choose to participate)
- 📧 Email: Lisa@triplemoongoddess.com (no guarantee of response)

**I am NOT obligated to:**
- Answer emails
- Provide technical support
- Fix bugs
- Add features
- Help with setup

**You're on your own!** That's the deal with free, open source software. Use Claude to help you - that's what it's for! 😊

## License

This system uses Swiss Ephemeris, which is licensed under GPL or commercial license.
See: https://www.astro.com/swisseph/

## Credits

- **Swiss Ephemeris** by Astrodienst
- **pyswisseph** by Stanislas Marquis
- **Created by** Lisa - Triple Moon Goddess Astrology
- **Contact:** Lisa@triplemoongoddess.com
- **Built with** Claude Code by Anthropic

## Version

**Current:** 1.0.0
**Updated:** December 18, 2025

---

**Get Started:** Read [BUSINESS_DOCUMENTATION.md](BUSINESS_DOCUMENTATION.md) or [TECHNICAL_DOCUMENTATION.md](TECHNICAL_DOCUMENTATION.md)
