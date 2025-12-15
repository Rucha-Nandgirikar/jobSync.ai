// Rapid Apply content script
// Runs on Ashby job pages (see manifest.json matches)

console.log("Rapid Apply content script loaded");

const STORAGE_KEY = "rapid_apply_last_job";
let _lastUrl = window.location.href;

function canonicalizeAshbyUrl(url) {
  try {
    const u = new URL(url);
    u.hash = "";
    u.search = "";
    if (u.pathname.endsWith("/application")) {
      u.pathname = u.pathname.slice(0, -"/application".length);
    }
    // trim trailing slash
    if (u.pathname.length > 1 && u.pathname.endsWith("/")) {
      u.pathname = u.pathname.slice(0, -1);
    }
    return u.toString();
  } catch {
    return url;
  }
}

function _uniqStrings(items) {
  const out = [];
  const seen = new Set();
  for (const s of items || []) {
    const t = String(s || "").replace(/\s+/g, " ").trim();
    if (!t) continue;
    const key = t.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(t);
  }
  return out;
}

function extractAshbyQuestions() {
  // Ashby application tab uses aria-controls="form" and tabpanel id="form"
  const root =
    document.querySelector("#form") ||
    document.querySelector('[aria-labelledby="job-application-form"]') ||
    document;

  // Best signal: stable Ashby class for question headings.
  // (The hashed classes around it can change between deploys.)
  const headingQuestions = Array.from(
    root.querySelectorAll(".ashby-application-form-question-title")
  )
    .map((el) => (el.innerText || el.textContent || "").trim())
    .filter(Boolean);

  // Heuristic: grab visible-ish label/legend/question texts near inputs
  const labels = Array.from(root.querySelectorAll("label"))
    .map((el) => el.innerText || el.textContent || "")
    .map((t) => t.trim());

  const legends = Array.from(root.querySelectorAll("legend"))
    .map((el) => el.innerText || el.textContent || "")
    .map((t) => t.trim());

  // Some Ashby forms use div/p tags for questions; include common patterns
  const questionish = Array.from(
    root.querySelectorAll("[data-testid*='question'], [class*='question'], p, h2, h3, h4")
  )
    .map((el) => (el.innerText || el.textContent || "").trim())
    .filter((t) => t && t.length >= 8 && t.length <= 240)
    .filter((t) => t.includes("?") || /tell|describe|why|how|what|experience/i.test(t));

  // Prefer the explicit Ashby headings, then fall back to heuristics.
  const combined = headingQuestions.length
    ? [...headingQuestions, ...labels, ...legends, ...questionish]
    : [...labels, ...legends, ...questionish];

  return _uniqStrings(combined);
}

function extractAshbyJob() {
  const url = canonicalizeAshbyUrl(window.location.href);

  const titleEl = document.querySelector("h1");
  const companyEl =
    document.querySelector('[data-testid="company-name"]') ||
    document.querySelector("header a");

  // Try specific Ashby overview container first, then fall back.
  // Note: on the /application route, #overview may still exist but be inactive;
  // we still prefer it for stable JD extraction.
  const jdEl =
    document.querySelector("#overview div._descriptionText_oj0x8_198") ||
    document.querySelector('div._descriptionText_oj0x8_198') ||
    document.querySelector('#overview div[class^="_descriptionText_"]') ||
    document.querySelector('div[class^="_descriptionText_"]') ||
    document.querySelector('[data-testid="job-description"]') ||
    document.querySelector('#overview') ||
    document.querySelector('div.ashby-job-posting-right-pane') ||
    document.querySelector("main");

  const job_title = titleEl ? titleEl.innerText.trim() : null;
  const company_name = companyEl ? companyEl.innerText.trim() : null;
  const job_description = jdEl ? jdEl.innerText.trim() : "";

  console.log("Rapid Apply extractAshbyJob: jdEl found?", !!jdEl, "length", job_description.length);

  return {
    job_url: url,
    company_name,
    company_url: companyEl && companyEl.href ? companyEl.href : window.location.origin,
    job_title,
    job_description,
    questions: extractAshbyQuestions(),
  };
}

function _isApplicationRoute() {
  try {
    return window.location.pathname.includes("/application");
  } catch {
    return false;
  }
}

async function extractAshbyJobWithRetries({ maxAttempts = 10, intervalMs = 300 } = {}) {
  for (let i = 0; i < maxAttempts; i++) {
    const job = extractAshbyJob();
    const hasJD = job.job_description && job.job_description.length >= 20;
    const hasQs = Array.isArray(job.questions) && job.questions.length > 0;

    // On application route, wait a bit for questions to render.
    if (_isApplicationRoute() && hasJD && !hasQs) {
      await new Promise((r) => setTimeout(r, intervalMs));
      continue;
    }
    return job;
  }
  return extractAshbyJob();
}

async function _persistLastJob(job, backendResponse) {
  try {
    if (!chrome?.storage?.local) return;
    const jobData = backendResponse?.data?.job || {};
    const lastJob = {
      job_id: backendResponse?.data?.job_id || null,
      title: jobData.title || job.job_title || null,
      company: jobData.company || job.company_name || null,
      url: jobData.url || job.job_url || window.location.href,
    };
    await chrome.storage.local.set({
      [STORAGE_KEY]: {
        lastJob,
        lastApplicationId: null,
        lastQuestions: _uniqStrings(job.questions || []),
        savedAt: Date.now(),
      },
    });
  } catch (e) {
    console.warn("Rapid Apply: failed to persist last job", e);
  }
}

async function sendJobToBackendIfPresent() {
  const job = extractAshbyJob();
  if (!job.job_description || job.job_description.length < 20) {
    console.log("Rapid Apply: JD too short or missing; not sending to backend.");
    return;
  }

  const payload = {
    user_id: 1,
    job_url: job.job_url,
    company_name: job.company_name,
    company_url: job.company_url,
    job_title: job.job_title,
    job_description: job.job_description,
    source: "ashby",
  };

  console.log("Rapid Apply: sending captured JD to backend", payload);
  try {
    const result = await chrome.runtime.sendMessage({
      action: "apiFetch",
      path: "/api/extension/capture-job",
      method: "POST",
      body: payload,
    });
    console.log("Rapid Apply backend response:", result);
    if (result?.ok && result?.data?.status === "success") {
      await _persistLastJob(job, result.data);
    }
  } catch (err) {
    console.error("Rapid Apply capture error:", err);
  }
}

// Respond to popup "captureJD" requests
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "captureJD") {
    (async () => {
      const job = await extractAshbyJobWithRetries();
      console.log(
        "Rapid Apply captureJD job:",
        job?.job_url,
        "jdLen=",
        (job?.job_description || "").length,
        "questions=",
        Array.isArray(job?.questions) ? job.questions.length : 0
      );
      sendResponse(job);
    })();
    return true;
  }
  return true; // allow async if we add it later
});

// First load
window.addEventListener("load", () => {
  sendJobToBackendIfPresent();
});

// Ashby is often a SPA; detect URL changes and re-run capture.
setInterval(() => {
  const href = window.location.href;
  if (href !== _lastUrl) {
    _lastUrl = href;
    // Small delay for the new route to render content.
    setTimeout(() => {
      sendJobToBackendIfPresent();
    }, 800);
  }
}, 1000);
