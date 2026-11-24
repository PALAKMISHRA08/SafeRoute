# Person 3 — Location Features

## Files changed/added
- `js/location.js` — NEW: live nearby police/hospital search, nearest-service selection, destination geocoding, walking route provider, and route risk scoring.
- `js/app.js` — small integration changes: exposes current location/places, supports free-text destination search, and uses actual route distance/time returned by the walking router.
- `index.html` — loads `location.js` after `app.js` and before `safety.js`.

Person 1's CSS, map UI, data.js, and Person 2's safety.js are retained.

## Data sources
- Nearby police/hospitals: OpenStreetMap Overpass API, within 5 km of the current location.
- Destination search: OpenStreetMap Nominatim.
- Walking route: OpenStreetMap routing.openstreetmap.de foot router.
- Incident risk: unsafe demo locations in `data.js` plus incident reports saved by Person 2 in this browser's localStorage.

## Run
Open the `saferoute-ui` folder in VS Code. In the VS Code terminal run:

```bash
py -m http.server 5500
```

Then open `http://localhost:5500` in Chrome or Edge. Allow location permission. Internet access is required for live map tiles and public OpenStreetMap services.

## Test
1. Click `Refresh nearby` and check that police/hospital markers and dashboard counts update.
2. Click `Nearest police` and `Nearest hospital` to route to the closest loaded result.
3. Type a place name/address in the destination field and click `Find safest route`.
4. Check that route, distance, walking time, and risk level appear.
5. Submit an incident in Person 2's Report page with location permission enabled; a report with coordinates is considered by risk analysis on the same browser.

## Important limitations
- Public OpenStreetMap services are community-run demo services and may throttle or be unavailable. Do not send rapid repeated requests.
- OpenStreetMap coverage can be incomplete. A missing marker does not prove no service exists nearby.
- Risk is a demo heuristic based on known unsafe pins/reports near the route, not a real-time crime prediction or guarantee of safety.
- The project is not a substitute for emergency services. In India, call 112 for immediate emergency help.
