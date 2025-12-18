# Swiss Ephemeris Astrology System

Professional astrology calculations powered by Swiss Ephemeris, delivered through Google Sheets.

## Quick Links

📘 **[Business Documentation](BUSINESS_DOCUMENTATION.md)** - For non-technical users, what this system does and why it's valuable

🔧 **[Technical Documentation](TECHNICAL_DOCUMENTATION.md)** - For developers, complete technical reference and API documentation

🔑 **[API Key Setup Guide](python-api-server/API_KEY_SETUP.md)** - Security setup instructions

## What This Is

A professional-grade astrology calculation platform that combines:
- **Swiss Ephemeris** - Industry-standard astronomical calculations
- **FastAPI Server** - Your own private calculation API
- **Google Sheets** - User-friendly interface
- **Railway Hosting** - Secure cloud deployment

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

## Quick Start

### 1. Deploy API Server
```bash
# Clone and deploy to Railway
git push origin main
# Railway auto-deploys in ~3 minutes
```

### 2. Configure Security
```bash
# Generate API key
openssl rand -hex 32

# Set in Railway → Variables
API_KEY=your-generated-key
```

### 3. Setup Google Sheets
- Add scripts: `NatalCharts_SelfHosted.gs` and `Transits_SelfHosted_Updated.gs`
- Update `API_KEY` in both scripts
- Run from menu

## Documentation Structure

```
swisseph/
├── README.md (this file)
├── BUSINESS_DOCUMENTATION.md - Business overview
├── TECHNICAL_DOCUMENTATION.md - Technical details
│
├── python-api-server/
│   ├── server.py - FastAPI application
│   ├── API_KEY_SETUP.md - Security guide
│   ├── requirements.txt - Python dependencies
│   ├── Dockerfile - Container config
│   └── ephe/ - Swiss Ephemeris data files
│
├── NatalCharts_SelfHosted.gs - Google Apps Script (natal)
└── Transits_SelfHosted_Updated.gs - Google Apps Script (transits)
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
- **Frontend:** Google Apps Script, Google Sheets
- **Hosting:** Railway.app
- **Data:** Swiss Ephemeris .se1 files

## Repository

GitHub: https://github.com/TripleMoonGoddess/swisseph-python-api

## Costs

- **Development:** Free (open source)
- **Hosting:** Free tier or $5/month unlimited
- **Total:** $0-5/month

## Support

- 📖 Check documentation first
- 🐛 GitHub issues for bugs
- 💡 GitHub discussions for features
- 📧 Email for private inquiries

## License

This system uses Swiss Ephemeris, which is licensed under GPL or commercial license.
See: https://www.astro.com/swisseph/

## Credits

- **Swiss Ephemeris** by Astrodienst
- **pyswisseph** by Stanislas Marquis
- **Created by** Lisa / Triple Moon Goddess
- **Built with** Claude Code by Anthropic

## Version

**Current:** 1.0.0
**Updated:** December 18, 2025

---

**Get Started:** Read [BUSINESS_DOCUMENTATION.md](BUSINESS_DOCUMENTATION.md) or [TECHNICAL_DOCUMENTATION.md](TECHNICAL_DOCUMENTATION.md)
