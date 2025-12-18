# Swiss Ephemeris System - Quick Reference Card

## 🚀 Quick Start Checklist

- [ ] Generate API key: `openssl rand -hex 32`
- [ ] Deploy to Railway from GitHub
- [ ] Set `API_KEY` in Railway variables
- [ ] Update `API_KEY` in both Google Scripts
- [ ] Test connection from menu
- [ ] Calculate first chart!

## 🔗 Important URLs

**Your API:** https://swisseph-python-api-production.up.railway.app
**Railway Dashboard:** https://railway.app
**GitHub Repo:** https://github.com/TripleMoonGoddess/swisseph-python-api

## 📋 Menu Commands

### Natal Charts
- **Process Charts (Placidus)** - Standard Western houses
- **Process Charts (Whole Sign)** - Ancient house system

### Transits
- **Calculate Transits - Placidus (365 Days)** - Year ahead with Placidus
- **Calculate Transits - Whole Sign (365 Days)** - Year ahead with Whole Sign

### Testing
- **Test API Connection** - Verify natal chart API
- **Test Transit API Connection** - Verify transits API
- **Test Asteroids** - Check asteroid calculations

## 📊 Input Format

**ChartInput Sheet Columns:**
```
name | year | month | day | hour | minute | ampm | city | state | country
```

**Example:**
```
A10001 | 1990 | 5 | 15 | 2 | 30 | PM | New York | NY | USA
```

## 🎯 What Gets Calculated

### Planets & Points (15 total)
Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto, Chiron, Ceres, Pallas, Juno, Vesta, North Node, South Node, Lilith

### Houses (5 systems)
Placidus, Whole Sign, Koch, Equal, Campanus

### Aspects (6 types)
Conjunction (0°), Opposition (180°), Trine (120°), Square (90°), Sextile (60°), Quincunx (150°)

### Transit Aspects (4 types)
Conjunction (0°), Square (90°), Opposition (180°), Quincunx (150°)

## 🔧 Configuration Locations

### NatalCharts_SelfHosted.gs
```javascript
Line 10: API_BASE_URL
Line 13: API_KEY
Line 16: INPUT_SHEET
Line 19: HOUSE_SYSTEMS
```

### Transits_SelfHosted_Updated.gs
```javascript
Line 10: API_BASE_URL
Line 13: API_KEY
Line 16: INPUT_SHEET
Line 20: PERIOD_DAYS (default: 365)
Line 23: HOUSE_SYSTEM (default: 'placidus')
```

## 🐛 Troubleshooting

| Problem | Solution |
|---------|----------|
| "API key is missing" | Check `X-API-Key` header in scripts |
| "Invalid API key" | Verify key matches Railway variable |
| "Geocoding failed" | Check location spelling, add state/country |
| Charts calculate slowly | Normal for first run, ~2-3 sec per chart |
| Transits taking long | 365 days takes ~5-10 seconds |
| Railway deployment failed | Check Railway logs, verify Dockerfile |

## 📞 API Endpoints

### Health Check (Public)
```
GET /
No authentication required
```

### Planets
```
POST /api/planets
Headers: X-API-Key: your-key
Body: { year, month, day, hour, min, lat, lon }
```

### Houses
```
POST /api/houses
Headers: X-API-Key: your-key
Body: { year, month, day, hour, min, lat, lon, house_type }
```

### Complete Chart
```
POST /api/chart
Headers: X-API-Key: your-key
Body: { year, month, day, hour, min, lat, lon, house_type }
```

### Transits
```
POST /api/transits
Headers: X-API-Key: your-key
Body: { natal_positions, start_date, end_date, lat, lon,
        birth_year, birth_month, birth_day, birth_hour, birth_min,
        house_type, transiting_planets, aspects }
```

## 💰 Costs

**Railway Free Tier:**
- 500 hours/month runtime
- ~500 calculations/month
- $0/month

**Railway Paid Tier:**
- Unlimited runtime
- Unlimited calculations
- $5/month

## ⚡ Performance

| Operation | Time | Notes |
|-----------|------|-------|
| Single natal chart | 2-3 sec | Includes geocoding |
| 10 natal charts | 20-30 sec | Batch processing |
| 365-day transits | 5-10 sec | Per chart |
| API response | <500ms | Server calculation only |

## 🔐 Security Best Practices

✅ **DO:**
- Use strong API key (32+ characters)
- Keep API key private
- Set in environment variables
- Rotate key periodically

❌ **DON'T:**
- Share API key publicly
- Commit key to public repos
- Use simple/guessable keys
- Reuse keys across projects

## 📁 Output Sheets

### Natal Chart: `{name}_{house_system}`
Contains: Planet positions, houses, ASC/MC, aspects

### Transits (Placidus): `Transits_{name}`
Contains: Date, planets, aspects, Placidus houses

### Transits (Whole Sign): `Transits_{name}_WS`
Contains: Date, planets, aspects, Whole Sign houses

## 🎨 Sheet Color Codes

- **Natal Charts:** Blue header (#4A86E8)
- **Transits (Placidus):** Green header (#6AA84F)
- **Transits (Whole Sign):** Purple header (#9B59B6)

## 📚 Documentation Files

| File | Audience | Content |
|------|----------|---------|
| README.md | Everyone | Overview & links |
| BUSINESS_DOCUMENTATION.md | Non-technical | What it does, why it's valuable |
| TECHNICAL_DOCUMENTATION.md | Developers | API details, code structure |
| API_KEY_SETUP.md | Setup | Security configuration |
| QUICK_REFERENCE.md | Daily use | This file! |

## 🆘 Emergency Commands

**Test API locally:**
```bash
cd python-api-server
export API_KEY="test-key"
uvicorn server:app --reload
```

**Check Railway logs:**
```
Railway dashboard → Your project → Deployments → View logs
```

**Regenerate API key:**
```bash
openssl rand -hex 32
# Update Railway variable
# Update both Google scripts
```

**Redeploy to Railway:**
```bash
git add .
git commit -m "Update"
git push origin main
# Auto-deploys in 2-3 minutes
```

## 📞 Get Help

1. **Check this reference** - Most common issues covered
2. **Read full docs** - TECHNICAL_DOCUMENTATION.md
3. **Check Railway logs** - For deployment issues
4. **GitHub issues** - For bugs/features
5. **Community forums** - For astrology tech help

## 🎓 Learning Resources

**Swiss Ephemeris:**
- Official: https://www.astro.com/swisseph/
- Programming: https://astrorigin.com/pyswisseph/

**FastAPI:**
- Docs: https://fastapi.tiangolo.com/

**Google Apps Script:**
- Reference: https://developers.google.com/apps-script

**Railway:**
- Docs: https://docs.railway.app/

## ✨ Pro Tips

💡 **Batch Processing:** Enter multiple charts in input sheet, process all at once

💡 **House Comparison:** Run both Placidus and Whole Sign, compare in separate tabs

💡 **Transit Planning:** Calculate transits at start of year, reference throughout

💡 **Client Prep:** Pre-calculate client charts before consultations

💡 **Data Export:** Use Google Sheets export to Excel/PDF for reports

💡 **Backup:** Google Sheets auto-saves, but export periodically for safety

💡 **Sharing:** Share view-only copies with clients (remove API key first!)

## 🔄 Common Workflows

### New Client Chart
1. Add to ChartInput sheet
2. Process Charts (Placidus)
3. Review chart tab
4. Calculate transits if needed
5. Share or export

### Monthly Transit Check
1. Run Calculate Transits once
2. Check dates for current month
3. Note important aspects
4. Plan consultations accordingly

### House System Study
1. Process same chart with Placidus
2. Process same chart with Whole Sign
3. Compare tabs side-by-side
4. Note differences in planet houses

### Batch Processing
1. Prepare input sheet with all data
2. Run Process Charts once
3. All charts appear in separate tabs
4. Export or share as needed

---

**Keep this card handy for daily use!**

**Last Updated:** December 18, 2025
**Version:** 1.0.0
