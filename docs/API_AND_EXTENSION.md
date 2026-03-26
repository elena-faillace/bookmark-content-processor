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
Removes a bookmark from ChromaDB.
- **Query param:** `url` — exact URL to delete
- **Response (JSON):**
  ```json
  { "status": "deleted", "url": "..." }
  ```
- **Errors:** `404` if the URL is not in the database
- **Called by:** search UI after user confirms deletion; also triggers browser bookmark removal via `postMessage` to extension (see below)

---

### `GET /import/bookmarks/preview`
Checks how many Chrome bookmarks are not yet saved, without importing anything.
- **Response (JSON):**
  ```json
  { "to_import": 5, "already_saved": 38, "total_found": 43 }
  ```
- **Called by:** search UI on page load (to show the unsaved-bookmarks warning) and when the Import button is clicked

---

### `POST /import/bookmarks`
Imports all Chrome bookmarks not yet in ChromaDB. Streams progress via Server-Sent Events.
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
| `background.js` | Background service worker (Chrome) / background page (Firefox) | Receives messages from the content script; calls `chrome.bookmarks.remove()` |
| `content_script.js` | Injected into `http://localhost:8484/*` | Bridges the search UI and the extension — listens for `postMessage` from the page and forwards to `background.js` |

---

## Extension ↔ Search UI Communication

The search UI is a plain web page and cannot call browser APIs directly. When the user deletes a bookmark, the removal from browser bookmarks is done through a three-step bridge:

```
search UI (localhost:8484)
  window.postMessage({ type: "REMOVE_BOOKMARK", url }, "*")

content_script.js  [injected into the tab by the extension]
  chrome.runtime.sendMessage({ action: "removeBookmark", url })

background.js  [extension background process]
  chrome.bookmarks.search({ url })
  chrome.bookmarks.remove(bookmark.id)
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
