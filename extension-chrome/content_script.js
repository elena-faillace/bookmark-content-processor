window.addEventListener("message", (event) => {
  const { type, url, title } = event.data || {};
  if (!url) return;
  if (type === "REMOVE_BOOKMARK") {
    chrome.runtime.sendMessage({ action: "removeBookmark", url });
  } else if (type === "ADD_BOOKMARK") {
    chrome.runtime.sendMessage({ action: "addBookmark", url, title: title || "" });
  }
});
