# SafeRoute — Person 2 Safety Features

## What was added

- SOS confirmation flow, location capture from Person 1's `SafeRoute.getLocation()` hook, local SOS history, and an optional backend request.
- Emergency contacts: add, edit, delete, and call using the device dialer.
- Incident reporting: category, description, place, current coordinates, optional image filename, and local report history.
- Emergency information: name, blood group, medical notes, and other emergency notes.
- Responsive safety-centre dialog integrated with Person 1's existing Report, Contacts, and SOS controls.

## Important scope / current behavior

The supplied Person 1 ZIP is a static HTML/CSS/vanilla-JavaScript application. It does not contain React, Node.js, `package.json`, an Express server, or an existing API. To preserve Person 1's working project, these features were added in the same vanilla-JavaScript structure rather than converting the app to a different framework.

Without a backend URL, records are stored in this browser's `localStorage`. This is suitable for UI demonstration, not production multi-user storage. SOS does **not** send SMS, WhatsApp, or calls automatically. The app clearly tells the user to call India's emergency number 112 for immediate help. The optional incident photo is validated but only its filename is recorded; binary upload needs a backend upload endpoint.

## Run

1. Extract the ZIP.
2. Open `saferoute-ui/index.html` in a browser, or use VS Code Live Server (recommended because browser geolocation and some browser APIs work more consistently on localhost/HTTPS).
3. Allow location permission if prompted.
4. Use the top navigation: Report, Contacts, Emergency Info. Use the red SOS button on the map to test the confirmation flow.

Leaflet and map tiles are loaded from public CDNs, so an internet connection is needed for the map.

## Backend integration contract for Person 4

Set `window.SafeRouteSafetyConfig` **before** loading `js/safety.js` (in `index.html`) to enable API calls:

```js
window.SafeRouteSafetyConfig = {
  apiBaseUrl: "http://localhost:3000",
  headers: {}, // add the agreed auth header here; do not hard-code secrets in frontend code
  endpoints: {
    contacts: "/api/safety/contacts",
    reports: "/api/safety/incidents",
    info: "/api/safety/emergency-info",
    sos: "/api/safety/sos"
  }
};
```

Expected request bodies:

- `POST /api/safety/contacts`: `{ id, name, phone, updatedAt }`
- `POST /api/safety/incidents`: `{ id, type, description, place, location: { latitude, longitude } | null, photoName, createdAt, status }`
- `PUT /api/safety/emergency-info`: `{ name, bloodGroup, medical, notes, updatedAt }`
- `POST /api/safety/sos`: `{ id, location: { latitude, longitude } | null, contactIds: [], message, createdAt, status }`

The frontend expects successful 2xx responses. For production, Person 4 should implement authentication, ownership checks, validation, persistent database storage, rate limiting/audit logs for SOS, and proper error responses. The backend should send notifications only through a configured and consented SMS/WhatsApp provider. Do not trust client-provided user IDs or contact IDs without checking ownership.

## Handover notes for Person 3

- Person 1's map/location API remains available as `window.SafeRoute.getLocation()` and `window.SafeRoute.map`.
- SOS and incident records include the current coordinates when browser location is available.
- Person 3 can continue implementing live location, route calculation, and risk analysis without changing `js/safety.js`.

## Files changed

- `index.html` — loads `js/safety.js` after Person 1's `js/app.js`.
- `js/safety.js` — Person 2's complete front-end safety module.

Person 1's original `css/style.css`, `js/app.js`, and `js/data.js` are retained unchanged.
