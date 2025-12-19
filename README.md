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

### Step 4: Setup Google Sheets

1. **Create New Google Sheet**
   - Go to sheets.google.com
   - Create new blank spreadsheet
   - Name it: "Astrology Charts" (or whatever you like)

2. **Add Scripts**
   - Click **Extensions → Apps Script**
   - Delete the default `myFunction()` code
   - Create first file: Click + next to "Files"
   - Name: `NatalCharts_SelfHosted.gs`
   - Copy code from `NatalCharts_SelfHosted.gs` in this repo
   - Paste into editor

3. **Add Second Script**
   - Click + again to add another file
   - Name: `Transits_SelfHosted_Updated.gs`
   - Copy code from `Transits_SelfHosted_Updated.gs` in this repo
   - Paste into editor

4. **Configure Both Scripts**

   In `NatalCharts_SelfHosted.gs`, update these lines:
   ```javascript
   const CONFIG = {
     API_BASE_URL: 'https://yourapp.up.railway.app',  // Your Railway URL
     API_KEY: 'your-generated-key-here',  // Your API key from Step 3
   ```

   In `Transits_SelfHosted_Updated.gs`, update:
   ```javascript
   const TRANSIT_CONFIG = {
     API_BASE_URL: 'https://yourapp.up.railway.app',  // Same Railway URL
     API_KEY: 'your-generated-key-here',  // Same API key
   ```

5. **Save Scripts**
   - Click "Save" button (disk icon)
   - Close Apps Script tab

### Step 5: Setup Input Sheet

1. Back in Google Sheets, refresh the page
2. You should see new menu: **"Astrology Charts"**
3. Click **Astrology Charts → Setup Input Sheet**
4. This creates "ChartInput" sheet with sample data

### Step 6: Test Your Setup

1. **Test API Connection**
   - Click **Astrology Charts → Test API Connection**
   - Should see: "✅ API is working!"
   - If error, check your API_KEY and API_BASE_URL

2. **Calculate Your First Chart**
   - Go to "ChartInput" sheet
   - Enter birth data:
     - name: Your name or code (e.g., "A10001")
     - year, month, day, hour, minute
     - city, state, country
   - Click **Astrology Charts → Process Charts (Placidus)**
   - New sheet appears with your chart! 🎉

3. **Calculate Transits** (optional)
   - Click **Astrology Charts → Calculate Transits - Placidus (365 Days)**
   - New sheet shows year of transits
   - Takes 30-60 seconds for full year

### Step 7: Start Using It!

**For Each Chart:**
1. Add row to "ChartInput" sheet
2. Fill in birth data
3. Run menu command
4. Get instant professional chart!

**Batch Processing:**
- Add multiple rows
- Run once
- All charts generated automatically

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

## For Your Astrology Teacher

👋 **Hi! This is set up so Claude can help you!**

If you get stuck:
1. Copy any error message
2. Tell Claude: "I'm setting up the Swiss Ephemeris astrology system and got this error: [paste error]"
3. Claude will guide you through the fix!

The setup takes about 20-30 minutes. You don't need to know how to code - just follow the steps above and ask Claude if anything is confusing.

**What you'll need:**
- Gmail account (for Google Sheets)
- Credit card for Railway (but free tier is $0/month - they just need it on file)
- 30 minutes
- Claude to help! 😊

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
