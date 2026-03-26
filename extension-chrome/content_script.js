window.addEventListener("message", (event) => {
  if (event.data?.type !== "REMOVE_BOOKMARK" || !event.data.url) return;
  chrome.runtime.sendMessage({ action: "removeBookmark", url: event.data.url });
});
