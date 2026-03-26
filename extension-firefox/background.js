chrome.runtime.onMessage.addListener((msg) => {
  if (msg.action === "removeBookmark") {
    chrome.bookmarks.search({ url: msg.url }, (results) => {
      for (const bookmark of results) {
        chrome.bookmarks.remove(bookmark.id);
      }
    });
  } else if (msg.action === "addBookmark") {
    chrome.bookmarks.create({ url: msg.url, title: msg.title || "" });
  }
});

async function cleanupDeleted() {
  try {
    const res = await fetch("http://localhost:8484/deleted");
    if (!res.ok) return;
    const { deleted } = await res.json();
    for (const { url } of deleted) {
      chrome.bookmarks.search({ url }, (results) => {
        for (const bookmark of results) {
          chrome.bookmarks.remove(bookmark.id);
        }
      });
    }
  } catch (_) {}
}

chrome.runtime.onStartup.addListener(cleanupDeleted);
