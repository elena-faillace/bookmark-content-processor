chrome.runtime.onMessage.addListener((msg) => {
  if (msg.action !== "removeBookmark") return;
  chrome.bookmarks.search({ url: msg.url }, (results) => {
    for (const bookmark of results) {
      chrome.bookmarks.remove(bookmark.id);
    }
  });
});
