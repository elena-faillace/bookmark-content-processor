const btn = document.getElementById("saveBtn");
const statusEl = document.getElementById("status");

btn.addEventListener("click", async () => {
  btn.disabled = true;
  statusEl.textContent = "Saving...";
  statusEl.className = "";

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const url = tab.url;
    const title = tab.title || "";

    if (!url || (!url.startsWith("http://") && !url.startsWith("https://"))) {
      statusEl.textContent = "Cannot save this page (no HTTP URL).";
      statusEl.className = "err";
      btn.disabled = false;
      return;
    }

    const res = await fetch("http://localhost:8484/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, title }),
    });

    if (res.ok) {
      statusEl.textContent = "Saved!";
      statusEl.className = "ok";
    } else {
      const data = await res.json().catch(() => ({}));
      statusEl.textContent = `Error: ${data.detail || res.statusText}`;
      statusEl.className = "err";
    }
  } catch (err) {
    statusEl.textContent = "Could not reach the local server.";
    statusEl.className = "err";
  } finally {
    btn.disabled = false;
  }
});
