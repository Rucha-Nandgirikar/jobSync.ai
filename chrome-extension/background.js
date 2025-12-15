// Background service worker for Rapid Apply

const API_BASE = "http://localhost:8000";

chrome.runtime.onInstalled.addListener(async () => {
  console.log("Rapid Apply extension installed");
  // Make the extension action open the side panel (Chrome 114+).
  try {
    if (chrome.sidePanel?.setPanelBehavior) {
      await chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
    }
  } catch (e) {
    console.warn("Failed to set side panel behavior", e);
  }
});

async function handleApiFetch(msg) {
  const path = msg.path || msg.url || "";
  const url = path.startsWith("http") ? path : `${API_BASE}${path}`;
  const method = (msg.method || "GET").toUpperCase();

  const headers = Object.assign({}, msg.headers || {});
  let body = msg.body;
  if (body && typeof body === "object" && !(body instanceof ArrayBuffer)) {
    headers["Content-Type"] = headers["Content-Type"] || "application/json";
    body = JSON.stringify(body);
  }

  const res = await fetch(url, {
    method,
    headers,
    body: method === "GET" || method === "HEAD" ? undefined : body,
  });

  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }

  return { ok: res.ok, status: res.status, data };
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request?.action === "apiFetch") {
    (async () => {
      try {
        const result = await handleApiFetch(request);
        sendResponse(result);
      } catch (e) {
        sendResponse({ ok: false, status: 0, data: String(e) });
      }
    })();
    return true;
  }
  return false;
});




