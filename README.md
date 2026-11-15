# Swiss Ephemeris REST API

REST API for astrological calculations using Swiss Ephemeris.

## Build

```bash
docker build -t swisseph-api .
docker run -p 8000:8000 -e API_KEY=your-key swisseph-api
# On Cloud Run with no public invoker, IAM can be the only gate instead:
#   AUTH_MODE=cloud-run-iam  (no API_KEY)
```

## Tests

Every `test_*.py` runs inside the built image, which has no pip (`test_no_pip_in_image.py`). `Dockerfile.test` adds the tests and httpx without replacing any of the image's packages:

```bash
docker buildx build --platform linux/amd64 --load -t swisseph-api .
docker buildx build --platform linux/amd64 --load --build-arg IMAGE=swisseph-api -f Dockerfile.test -t swisseph-api-test .
docker run --rm --platform linux/amd64 -e AUTH_MODE=cloud-run-iam --entrypoint sh swisseph-api-test \
  -c 'for t in test_*.py; do python "$t" || echo "FAILED $t"; done'
```

## Ephemeris files

`ephe/` holds Swiss Ephemeris data from Astrodienst's official source (https://www.astro.com/ftp/swisseph/ephe/); the planet, moon and main-asteroid files (`sepl_18`, `semo_18`, `seas_18`) are the 2026-05-26 release based on JPL DE441. Chiron, Ceres, Pallas, Juno and Vesta come from `seas_18.se1`; `ast2/se02060.se1` is numbered Chiron. At startup `download_asteroids.py` checks each numbered-asteroid file has a real `SWISSEPH` header and fetches it again over HTTPS if not. `test_ephe_files.py` fails if any `ephe/` file is HTML.

## API Endpoints

- `GET /` - Health check
- `POST /api/planets` - Planetary positions
- `POST /api/houses` - House cusps
- `POST /api/chart` - Complete chart
- `POST /api/transits` - Transit calculations (limits: `end_date` after `start_date` and at most 731 days later; at most 24 `natal_positions`, 6 `aspects`, 10 `transiting_planets` with no duplicates; anything over gets 422)
- `POST /api/stations` - Retrograde/direct stations
- `POST /api/ingresses` - Sign + natal-house ingresses over a window
- `POST /api/orb-windows` - In-orb windows against natal points
- `POST /api/longitudes` - Longitudes at UT instants
- `POST /api/returns` - Planetary return cycles + return/transit charts
- `POST /api/monthly-transits` - Next new/full moon + next sign ingress per body (chart-free)
- `POST /api/annual-transits` - One chart's transit year: Sun–angle conjunctions, eclipses, retrograde periods, outer-planet sign changes (natal houses)
- `POST /api/lifetime-returns` - Every exact return of each body from birth (Mercury → Uranus, Moon excluded) plus Uranus opposition passes, dates only

Every endpoint except the health check requires the `X-API-Key` header when `API_KEY` is set. With `AUTH_MODE=cloud-run-iam` and no `API_KEY`, Cloud Run IAM (an identity token from an account holding `roles/run.invoker`) is the only gate. With neither set, the server refuses to start.

## License

This program is licensed under **GNU Affero General Public License v3.0 (AGPL-3.0)**.

See [LICENSE](LICENSE) for full text. Source: https://github.com/Triple-Moon-Goddess/swisseph-python-api

This software uses **Swiss Ephemeris** by Astrodienst AG, which is also AGPL-3.0 licensed.
Website: https://www.astro.com/swisseph/

## Copyright

Copyright (C) 2025 Triple Moon Goddess Astrology
Contact: Lisa@triplemoongoddess.com

Swiss Ephemeris Copyright (C) 1997-2021 Astrodienst AG, Switzerland

## No Warranty

This program is distributed WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the AGPL-3.0 license for details.
