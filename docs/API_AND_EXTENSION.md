# API & Extension Communication Reference

A map of every HTTP endpoint the server exposes, every call the browser extensions make, and how the extension scripts talk to each other and to the search UI. Update this file whenever you add an endpoint or change how the extension communicates.

---

## Server

The API runs locally at **`http://localhost:8484`**, managed by Supervisor. Source: `app/api.py`.

---

## HTTP Endpoints

### `GET /`
Serves the search UI.
- **Response:** `ui/search.html` (static file)
- **Called by:** browser (direct navigation)

---

### `POST /save`
Saves a URL to ChromaDB with semantic embedding.
- **Request body (JSON):**
  ```json
  { "url": "https://example.com", "title": "Page title" }
  ```
- **Response (JSON):**
  ```json
  { "status": "saved", "url": "...", "embedded": true }
  ```
  `embedded: false` means text extraction failed and the URL string itself was embedded as a fallback.
- **Called by:** browser extension popup (`popup.js`) on button click
- **Side effects:** calls `extract_text()` → `embed_and_store()` or `store_url_only()`; also saves to browser bookmarks via `chrome.bookmarks.create()`

---

### `GET /bookmarks?offset=<n>&limit=<n>`
Returns all saved bookmarks, paginated, sorted by date descending.
- **Query params:** `offset` (default `0`), `limit` (default `50`)
- **Response (JSON):**
  ```json
  {
    "items": [
      { "url": "...", "title": "...", "date": "2026-03-26T10:00:00+00:00", "text_extracted": true },
      ...
    ],
    "total": 120,
    "offset": 0,
    "limit": 50
  }
  ```
- **Called by:** search UI Browse view for paginated listing

---

### `GET /search?q=<query>`
Semantic search over saved bookmarks.
- **Query param:** `q` — natural language search string (min length 1)
- **Response (JSON):**
  ```json
  { "query": "travel", "results": [{ "url": "...", "title": "..." }, ...] }
  ```
  Results are ordered by cosine similarity (most relevant first), up to 10 results.
- **Called by:** search UI (`ui/search.html`) on form submit or Enter key

---

### `DELETE /bookmark?url=<url>`
Removes a bookmark from ChromaDB and records it in the deleted-bookmarks database.
- **Query param:** `url` — exact URL to delete
- **Response (JSON):**
  ```json
  { "status": "deleted", "url": "..." }
  ```
- **Errors:** `404` if the URL is not in ChromaDB
- **Called by:** search UI after user confirms deletion
- **Side effects:** records the URL + title in `deleted.db` so it is excluded from future imports and cleaned up from all browser profiles on next startup; also triggers browser bookmark removal via `postMessage` to the extension (see below)

---

### `GET /deleted`
Returns all deleted bookmarks, most recent first.
- **Response (JSON):**
  ```json
  {
    "deleted": [
      { "url": "...", "title": "...", "deleted_at": "2026-03-26T10:00:00+00:00" },
      ...
    ]
  }
  ```
- **Called by:** search UI (Trash panel); extension `background.js` on browser startup to clean up all profiles

---

### `POST /deleted/restore`
Removes a URL from the deleted-bookmarks list and re-saves it to ChromaDB.
- **Request body (JSON):**
  ```json
  { "url": "https://example.com", "title": "Page title" }
  ```
- **Response (JSON):**
  ```json
  { "status": "restored", "url": "..." }
  ```
- **Errors:** `404` if the URL is not in the deleted list
- **Called by:** search UI Trash panel on "Recover" click
- **Side effects:** re-embeds the URL; search UI also fires `window.postMessage({ type: "ADD_BOOKMARK", ... })` so the extension re-adds the bookmark to the browser

---

### `GET /import/bookmarks/preview`
Checks how many Chrome bookmarks are not yet saved, without importing anything. Excludes URLs already in the deleted-bookmarks list.
- **Response (JSON):**
  ```json
  { "to_import": 5, "already_saved": 38, "total_found": 43 }
  ```
- **Called by:** search UI on page load (to show the unsaved-bookmarks warning) and when the Import button is clicked

---

### `POST /import/bookmarks`
Imports all Chrome bookmarks not yet in ChromaDB. Skips URLs in the deleted-bookmarks list. Streams progress via Server-Sent Events.
- **Response:** `text/event-stream`, one JSON event per bookmark:
  ```
  data: {"imported": 1, "total": 5}
  data: {"imported": 2, "total": 5}
  ...
  data: {"done": true, "imported": 5, "total": 5}
  ```
- **Called by:** search UI after the user confirms the import dialog
- **Source of bookmarks:** reads Chrome's `Bookmarks` JSON file directly from the filesystem via `app/bookmarks_import.py`

---

## Deleted Bookmarks Database

`deleted.db` (SQLite, same directory as the server) holds every URL the user has intentionally deleted. It is never automatically cleared — entries are only removed by an explicit restore.

**Purpose:** acts as a cross-browser blocklist. Each extension fetches `GET /deleted` on browser startup and removes any matching bookmarks from that browser's profile. This means deleting once propagates to Chrome, Firefox, and any future browsers on the next launch.

**Schema:**
```sql
CREATE TABLE deleted_bookmarks (
    url        TEXT PRIMARY KEY,
    title      TEXT NOT NULL DEFAULT '',
    deleted_at TEXT NOT NULL   -- ISO-8601 UTC
);
```

---

## Browser Extensions

Two separate extensions with identical behaviour, one per browser:

| | Chrome | Firefox |
|---|---|---|
| Manifest version | 3 | 2 |
| Folder | `extension-chrome/` | `extension-firefox/` |
| Tab query API | `chrome.tabs` | `browser.tabs` |
| Popup declaration | `action` | `browser_action` |

### What the extension popup does (`popup.js`)

1. Reads the active tab's URL and title via `tabs.query`
2. `POST /save` → saves to the local server
3. On success: calls `chrome.bookmarks.create({ url, title })` → saves to browser bookmarks

### Extension scripts

| File | Context | Purpose |
|---|---|---|
| `popup.js` | Extension popup | Save current tab to server + browser bookmarks |
| `background.js` | Background service worker (Chrome) / background page (Firefox) | Handles `removeBookmark` and `addBookmark` messages; runs `cleanupDeleted()` on browser startup |
| `content_script.js` | Injected into `http://localhost:8484/*` | Bridges the search UI and the extension — listens for `postMessage` from the page and forwards to `background.js` |

---

## Extension ↔ Search UI Communication

The search UI is a plain web page and cannot call browser APIs directly. All bookmark operations go through a three-step bridge:

### Delete
```
search UI (localhost:8484)
  window.postMessage({ type: "REMOVE_BOOKMARK", url }, "*")

content_script.js  [injected into the tab by the extension]
  chrome.runtime.sendMessage({ action: "removeBookmark", url })

background.js
  chrome.bookmarks.search({ url })  →  chrome.bookmarks.remove(id)
```

### Recover (restore from Trash)
```
search UI
  POST /deleted/restore  (re-embeds in ChromaDB, removes from deleted.db)
  window.postMessage({ type: "ADD_BOOKMARK", url, title }, "*")

content_script.js
  chrome.runtime.sendMessage({ action: "addBookmark", url, title })

background.js
  chrome.bookmarks.create({ url, title })
```

### Startup cleanup (cross-browser enforcement)
```
background.js  [fires on chrome.runtime.onStartup]
  GET /deleted  →  list of all deleted URLs
  for each: chrome.bookmarks.search({ url })  →  chrome.bookmarks.remove(id)
```

**Why each layer is needed:**
- The page cannot call `chrome.bookmarks` — that API is only available in extension contexts.
- The content script can talk to both sides: it runs inside the tab (so it receives `postMessage` from the page) and it is extension code (so it can call `chrome.runtime.sendMessage`).
- The background script is the only context that has `chrome.bookmarks` access and runs persistently.

**Important:** the content script is only injected into tabs that load `http://localhost:8484/*` **after** the extension is active. If the tab was already open when the extension was (re)loaded, refresh it.

---

## Permissions Summary

| Permission | Why |
|---|---|
| `activeTab`, `tabs` | Read the current tab's URL and title in the popup |
| `bookmarks` | Create and remove browser bookmarks |
| `http://localhost:8484/*` | Firefox: allow `fetch` to the local server; both: allow content script injection |
