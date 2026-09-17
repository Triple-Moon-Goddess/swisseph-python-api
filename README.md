# Swiss Ephemeris REST API

REST API for astrological calculations using Swiss Ephemeris.

## Build

```bash
docker build -t swisseph-api .
docker run -p 8000:8000 -e API_KEY=your-key swisseph-api
```

## Deploy to Railway

1. Fork this repository
2. Connect to Railway.app
3. Set environment variable: `API_KEY=your-generated-key`
4. Deploy

## API Endpoints

- `GET /` - Health check
- `POST /api/planets` - Planetary positions
- `POST /api/houses` - House cusps
- `POST /api/chart` - Complete chart
- `POST /api/transits` - Transit calculations
- `POST /api/stations` - Retrograde/direct stations
- `POST /api/ingresses` - Sign + natal-house ingresses over a window
- `POST /api/orb-windows` - In-orb windows against natal points
- `POST /api/longitudes` - Longitudes at UT instants
- `POST /api/returns` - Planetary return cycles + return/transit charts
- `POST /api/monthly-transits` - Next new/full moon + next sign ingress per body (chart-free)

All endpoints require `X-API-Key` header (except health check).

## License

This program is licensed under **GNU Affero General Public License v3.0 (AGPL-3.0)**.

See [LICENSE](LICENSE) for full text.

This software uses **Swiss Ephemeris** by Astrodienst AG, which is also AGPL-3.0 licensed.
Website: https://www.astro.com/swisseph/

## Copyright

Copyright (C) 2025 Triple Moon Goddess Astrology
Contact: Lisa@triplemoongoddess.com

Swiss Ephemeris Copyright (C) 1997-2021 Astrodienst AG, Switzerland

## No Warranty

This program is distributed WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the AGPL-3.0 license for details.
