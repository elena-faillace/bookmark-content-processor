const btn = document.getElementById("saveBtn");
const status = document.getElementById("status");

btn.addEventListener("click", async () => {
  btn.disabled = true;
  status.textContent = "Saving...";
  status.className = "";

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const url = tab.url;

    if (!url || (!url.startsWith("http://") && !url.startsWith("https://"))) {
      status.textContent = "Cannot save this page (no HTTP URL).";
      status.className = "err";
      btn.disabled = false;
      return;
    }

    const res = await fetch("http://localhost:8000/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });

    if (res.ok) {
      status.textContent = "Saved!";
      status.className = "ok";
    } else {
      const data = await res.json().catch(() => ({}));
      status.textContent = `Error: ${data.detail || res.statusText}`;
      status.className = "err";
    }
  } catch (err) {
    status.textContent = "Could not reach the local server.";
    status.className = "err";
  } finally {
    btn.disabled = false;
  }
});
