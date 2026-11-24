# SafeRoute integrated project

SafeRoute keeps the supplied vanilla-JavaScript map, safety centre, location search, routing, and route-risk UI, and adds a local Python + SQLite backend.

## Run locally

Requirements: Python 3.10 or newer. No Python packages are needed.

1. Extract the ZIP.
2. Open a terminal in `saferoute-ui`.
3. Start the combined API and web server:

   ```bash
   python server.py
   ```

   On Windows, `py server.py` also works.
4. Open `http://127.0.0.1:8000` (use this same origin for API and browser app).
5. Create a normal user account with a password of at least 10 characters. Use **Sign in / Create account** in the top bar.
6. Open **Admin** after signing in as the seeded administrator.

The SQLite database is created one directory above the web root as `saferoute.db`. Set `SAFEROUTE_DB` to choose another file. Set `SAFEROUTE_HOST` and `SAFEROUTE_PORT` to change the bind address and port.

### Administrator account

First run seeds `admin@saferoute.local` with password `ChangeMe123!`. Change the password before sharing or deploying the demo by setting `SAFEROUTE_ADMIN_PASSWORD` before the first server start and deleting the generated database if it was already initialized. `SAFEROUTE_ADMIN_EMAIL` can override the email. This is a classroom/demo server and is not hardened for public production use.

## Included backend

- SQLite schema for accounts, hashed passwords, incident reports, emergency contacts, emergency information, SOS records, and admin audit entries.
- Account registration, sign-in, sign-out, and authenticated API access via in-memory bearer tokens (sessions reset when the server restarts).
- Per-account storage for contacts and emergency information; incident reports are visible in the shared map feed and admin review page.
- Admin summary, user list, incident status review, and campus routing failure/recovery simulation.
- Passwords are PBKDF2-HMAC-SHA256 hashed with per-user salts. Browser sessions are held in local storage for the demo.

The UI preserves local browser copies as a convenience. Incident/contact/info/SOS API saves require signing in. Emergency contacts and emergency information are written to the server for the signed-in account; they are not automatically sent anywhere. SOS requests are stored as records only.

## External services and credentials

No paid API key or external credential is required. The browser sends nearby-place and destination-search requests through the local Python server first, which then calls public OpenStreetMap Overpass and Nominatim services; if the proxy is unavailable, the browser tries the public services directly. Those services require internet access and may throttle or be unavailable. In that case the map keeps the bundled campus markers available for route demos. The walking router, Leaflet CDN, and map tiles also use public OpenStreetMap services. Browser geolocation requires permission and works reliably on localhost or HTTPS. SOS does not send SMS, WhatsApp, or phone calls; use India's emergency number 112 for immediate help. Risk estimates and the campus routing graph are educational demonstrations, not operational safety guarantees.

## Routing/failure/recovery simulation

The Admin page simulates a small undirected campus network. Select a link failure and the API recalculates the shortest reachable path (Dijkstra). For example, failing B–C causes A–D–C–E to be selected; the changed path represents recovery via an alternate route. If no path exists, status is unreachable.

## Checks

From this folder run:

```bash
python -m unittest discover -s tests -v
python -m py_compile server.py
```

Files `PERSON-2-README.md` and `PERSON-3-README.md` retain the original team handoff notes.

