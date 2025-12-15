console.log("Rapid Apply popup loaded");

const API_BASE = "http://localhost:8000";

function apiFetch(path, { method = "GET", body = null, headers = {} } = {}) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(
      { action: "apiFetch", path, method, body, headers },
      (resp) => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
          return;
        }
        resolve(resp);
      }
    );
  });
}

const statusEl = document.getElementById("status");
const jobMetaEl = document.getElementById("job-meta");
const previewEl = document.getElementById("preview");
const captureBtn = document.getElementById("capture");
const chatEl = document.getElementById("chat");
const todayCountEl = document.getElementById("today-count");

const resumeSelect = document.getElementById("resume-select");
const generateCoverLetterBtn = document.getElementById(
  "generate-cover-letter"
);
const coverLetterOutputEl = document.getElementById("cover-letter-output");

const questionsInput = document.getElementById("questions-input");
const suggestionsInput = document.getElementById("suggestions-input");
const answerQuestionsBtn = document.getElementById("answer-questions");
const answersOutputEl = document.getElementById("answers-output");
const markSubmittedBtn = document.getElementById("mark-submitted");

let lastJob = null; // { job_id, title, company, url }
let lastApplicationId = null; // created when answering questions

const STORAGE_KEY = "rapid_apply_last_job";
let lastQuestions = []; // captured application questions (best-effort)
let chatMessages = []; // [{role, title, text, ts}]

function _setMetaFromLastJob() {
  if (!jobMetaEl) return;
  if (!lastJob || !lastJob.job_id) {
    jobMetaEl.textContent = "No job captured yet.";
    return;
  }
  jobMetaEl.textContent = `Job #${lastJob.job_id}: ${lastJob.title || "Untitled"} @ ${
    lastJob.company || "Unknown company"
  }`;
}

async function saveLastJobToStorage() {
  try {
    if (!chrome?.storage?.local) return;
    await chrome.storage.local.set({
      [STORAGE_KEY]: {
        lastJob,
        lastApplicationId,
        lastQuestions,
        chatMessages,
        draftQuestions: questionsInput?.value || "",
        draftSuggestions: suggestionsInput?.value || "",
        savedAt: Date.now(),
      },
    });
  } catch (e) {
    console.warn("Failed to persist last job", e);
  }
}

function _appendChatMessage(role, title, text) {
  const msg = {
    role,
    title: title || "",
    text: String(text || ""),
    ts: Date.now(),
  };
  chatMessages.push(msg);
  _renderChat();
  saveLastJobToStorage();
}

function _renderChat() {
  if (!chatEl) return;
  chatEl.innerHTML = "";
  for (const m of chatMessages) {
    const div = document.createElement("div");
    div.className = `msg ${m.role || "assistant"}`;
    const meta = document.createElement("div");
    meta.className = "meta";
    meta.textContent =
      (m.role === "user" ? "You" : "Assistant") + (m.title ? ` • ${m.title}` : "");
    const body = document.createElement("div");
    body.textContent = m.text || "";
    div.appendChild(meta);
    div.appendChild(body);
    chatEl.appendChild(div);
  }
  // keep latest in view
  chatEl.scrollTop = chatEl.scrollHeight;
}

async function refreshTodayCount() {
  try {
    const resp = await apiFetch("/api/dashboard/stats?user_id=1");
    const d = resp?.data?.data || {};
    const n = d.today_submitted ?? d.submitted ?? 0;
    if (todayCountEl) todayCountEl.textContent = `Today submitted: ${n || 0}`;
  } catch {
    // ignore
  }
}

function _mergeQuestionsIntoTextarea(questions) {
  const q = (questions || []).map((s) => String(s || "").trim()).filter(Boolean);
  if (!q.length) return;
  const existing = (questionsInput.value || "").split("\n").map((s) => s.trim()).filter(Boolean);
  const seen = new Set(existing.map((s) => s.toLowerCase()));
  const merged = [...existing];
  for (const item of q) {
    const key = item.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    merged.push(item);
  }
  questionsInput.value = merged.join("\n");
}

async function loadLastJobFromStorage() {
  try {
    if (!chrome?.storage?.local) return;
    const res = await chrome.storage.local.get([STORAGE_KEY]);
    const state = res?.[STORAGE_KEY];
    if (!state) return;

    lastJob = state.lastJob || null;
    lastApplicationId = state.lastApplicationId || null;
    lastQuestions = state.lastQuestions || [];
    chatMessages = state.chatMessages || [];
    if (typeof state.draftQuestions === "string") questionsInput.value = state.draftQuestions;
    if (typeof state.draftSuggestions === "string") suggestionsInput.value = state.draftSuggestions;
    _setMetaFromLastJob();
    if (lastQuestions?.length) {
      _mergeQuestionsIntoTextarea(lastQuestions);
    }
    _renderChat();
    refreshTodayCount();

    if (markSubmittedBtn) {
      markSubmittedBtn.disabled = !lastApplicationId;
    }
  } catch (e) {
    console.warn("Failed to load last job", e);
  }
}

async function loadResumesForUser(userId = 1) {
  try {
    const resp = await apiFetch(`/api/generate/resumes?user_id=${userId}`);
    const data = resp.data;
    if (!resp.ok || data.status !== "success") throw new Error(data.detail || "Failed to load resumes");
    const resumes = data.data || [];
    resumeSelect.innerHTML = "";
    if (!resumes.length) {
      const opt = document.createElement("option");
      opt.value = "";
      opt.textContent = "No resumes found (upload in app)";
      resumeSelect.appendChild(opt);
      resumeSelect.disabled = true;
      return;
    }
    for (const r of resumes) {
      const opt = document.createElement("option");
      opt.value = String(r.id);
      opt.textContent = `${r.id} – ${r.filename || "Resume"} (${r.role || "role?"})`;
      resumeSelect.appendChild(opt);
    }
    resumeSelect.disabled = false;
  } catch (err) {
    console.error("Failed to load resumes", err);
    resumeSelect.innerHTML = "";
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = "Error loading resumes";
    resumeSelect.appendChild(opt);
    resumeSelect.disabled = true;
  }
}

// Load resumes as soon as popup opens
loadResumesForUser(1);
loadLastJobFromStorage();
refreshTodayCount();

async function captureFromCurrentTab() {
  statusEl.textContent = "Capturing JD from current tab...";
  previewEl.textContent = "";
  jobMetaEl.textContent = "Looking for job on this page...";

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab) {
      statusEl.textContent = "No active tab found.";
      return;
    }

    // Ensure content script is injected (in case matches didn't run it)
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      files: ["content.js"],
    });

    chrome.tabs.sendMessage(
      tab.id,
      { action: "captureJD" },
      async (response) => {
        if (chrome.runtime.lastError) {
          statusEl.textContent = "Content script not loaded or error occurred.";
          previewEl.textContent = chrome.runtime.lastError.message;
          return;
        }

        if (!response) {
          statusEl.textContent = "No response from content script.";
          return;
        }

        if (!response.job_description) {
          statusEl.textContent = "No JD captured. Check selectors.";
          previewEl.textContent = JSON.stringify(response, null, 2);
          return;
        }

        // Show raw JD preview
        previewEl.textContent = response.job_description;
        if (Array.isArray(response.questions) && response.questions.length) {
          lastQuestions = response.questions;
          _mergeQuestionsIntoTextarea(lastQuestions);
          await saveLastJobToStorage();
        }
        _appendChatMessage(
          "assistant",
          "Captured",
          `Captured JD (${response.job_description.length} chars)${
            response.questions?.length ? ` • Questions: ${response.questions.length}` : ""
          }`
        );

        // Also send to backend capture-job to get a job_id we can reuse
        statusEl.textContent = "Sending job to backend...";
        try {
          const payload = {
            user_id: 1, // MVP: single user
            job_url: response.job_url || tab.url,
            company_name: response.company_name || null,
            company_url: response.company_url || null,
            job_title: response.job_title || null,
            job_description: response.job_description,
            source: "ashby",
          };

          const resp = await apiFetch("/api/extension/capture-job", { method: "POST", body: payload });
          const data = resp.data;
          if (!resp.ok || data.status !== "success") throw new Error(data.detail || "Capture-job API error");

          const jobData = data.data.job;
          lastJob = {
            job_id: data.data.job_id,
            title: jobData.title,
            company: jobData.company,
            url: jobData.url,
          };
          lastApplicationId = null; // reset when job changes

          _setMetaFromLastJob();
          await saveLastJobToStorage();
          statusEl.textContent = "JD captured and saved. You can now generate a cover letter or answers.";
        } catch (apiErr) {
          console.error("capture-job error", apiErr);
          statusEl.textContent = "Captured JD, but failed to save to backend.";
        }
      }
    );
  } catch (err) {
    console.error("capture error", err);
    statusEl.textContent = "Error capturing JD.";
    previewEl.textContent = String(err);
  }
}

captureBtn.addEventListener("click", captureFromCurrentTab);

generateCoverLetterBtn.addEventListener("click", async () => {
  if (!lastJob || !lastJob.job_id) {
    statusEl.textContent = "Capture a job first.";
    return;
  }

  const selected = resumeSelect.value;
  if (!selected) {
    statusEl.textContent = "Select a resume first.";
    return;
  }
  const resumeId = parseInt(selected, 10);

  generateCoverLetterBtn.disabled = true;
  statusEl.textContent = "Generating cover letter...";
  coverLetterOutputEl.textContent = "";

  try {
    const resp = await apiFetch("/api/generate/cover-letter-advanced", {
      method: "POST",
      body: { job_id: lastJob.job_id, resume_id: resumeId },
    });
    const data = resp.data;
    if (!resp.ok || data.status !== "success") throw new Error(data.detail || "Cover letter API error");

    const cl = data.data.cover_letter || "";
    const files = data.data.files || {};

    const out =
      (cl || "").trim() ||
      "Cover letter generated but response did not include content.";
    _appendChatMessage("assistant", "Cover Letter", out);

    if (files.docx_path) {
      const lines = [];
      if (files.docx_path) {
        lines.push(`DOCX saved at: ${files.docx_path}`);
      }
      _appendChatMessage("assistant", "Files", lines.join("\n"));
    }

    statusEl.textContent = "Cover letter generated.";
  } catch (err) {
    console.error("cover-letter error", err);
    statusEl.textContent = "Error generating cover letter.";
    coverLetterOutputEl.textContent = String(err);
  } finally {
    generateCoverLetterBtn.disabled = false;
  }
});

async function ensureApplicationForCurrentJob(resumeId) {
  if (lastApplicationId) {
    return lastApplicationId;
  }
  if (!lastJob || !lastJob.job_id) {
    throw new Error("No job captured yet.");
  }

  // MVP: single user_id = 1
  const payload = {
    user_id: 1,
    job_id: lastJob.job_id,
    resume_id: resumeId,
    status: "draft",
  };

  const resp = await apiFetch("/api/dashboard/applications", { method: "POST", body: payload });
  const data = resp.data;
  if (!resp.ok || data.status !== "success") throw new Error(data.detail || "Failed to create application");
  lastApplicationId = data.data.application_id;
  if (markSubmittedBtn) {
    markSubmittedBtn.disabled = !lastApplicationId;
  }
  await saveLastJobToStorage();
  return lastApplicationId;
}

async function markCurrentApplicationSubmitted() {
  if (!lastApplicationId) {
    statusEl.textContent = "No application yet. Answer questions first (or create one).";
    return;
  }
  markSubmittedBtn.disabled = true;
  statusEl.textContent = "Marking as submitted...";
  try {
    const resp = await apiFetch(`/api/dashboard/applications/${lastApplicationId}`, {
      method: "POST",
      body: { status: "submitted" },
    });
    const data = resp.data;
    if (!resp.ok || data.status !== "success") throw new Error(data.detail || "Failed to update application status");
    statusEl.textContent = "Marked as submitted (counts will update on dashboard).";
    await saveLastJobToStorage();
    await refreshTodayCount();

    // Clear fields ONLY when user marks submitted.
    lastJob = null;
    lastApplicationId = null;
    lastQuestions = [];
    chatMessages = [];
    previewEl.textContent = "";
    questionsInput.value = "";
    suggestionsInput.value = "";
    answersOutputEl.textContent = "";
    coverLetterOutputEl.textContent = "";
    _setMetaFromLastJob();
    if (markSubmittedBtn) markSubmittedBtn.disabled = true;
    _renderChat();
    await saveLastJobToStorage();
  } catch (err) {
    console.error("mark-submitted error", err);
    statusEl.textContent = "Failed to mark as submitted.";
    answersOutputEl.textContent = String(err);
  } finally {
    markSubmittedBtn.disabled = false;
  }
}

if (markSubmittedBtn) {
  markSubmittedBtn.addEventListener("click", markCurrentApplicationSubmitted);
  markSubmittedBtn.disabled = !lastApplicationId;
}

answerQuestionsBtn.addEventListener("click", async () => {
  if (!lastJob || !lastJob.job_id) {
    statusEl.textContent = "Capture a job first.";
    return;
  }

  const selected = resumeSelect.value;
  if (!selected) {
    statusEl.textContent = "Select a resume first.";
    return;
  }
  const resumeId = parseInt(selected, 10);

  const raw = (questionsInput.value || "").split("\n");
  const questions = raw.map((q) => q.trim()).filter((q) => q.length > 0);
  if (!questions.length) {
    statusEl.textContent = "Enter at least one question.";
    return;
  }

  answerQuestionsBtn.disabled = true;
  statusEl.textContent = "Generating answers...";
  answersOutputEl.textContent = "";

  try {
    const applicationId = await ensureApplicationForCurrentJob(resumeId);
    _appendChatMessage(
      "user",
      "Suggestions",
      (suggestionsInput.value || "").trim() || "(none)"
    );
    _appendChatMessage("user", "Questions", questions.join("\n"));

    const resp = await apiFetch("/api/questions/answer", {
      method: "POST",
      body: {
        application_id: applicationId,
        job_id: lastJob.job_id,
        resume_id: resumeId,
        user_suggestions: (suggestionsInput.value || "").trim() || null,
        // JD-free mode: generate answers using ONLY resume + suggestions
        ignore_jd: true,
        questions,
      },
    });
    const data = resp.data;
    if (!resp.ok || data.status !== "success") throw new Error(data.detail || "Questions API error");

    const answers = data.data.answers || [];
    if (!answers.length) {
      answersOutputEl.textContent = "No answers returned.";
    } else {
      const lines = [];
      for (const entry of answers) {
        lines.push(`Q: ${entry.question}\nA: ${entry.answer}\n`);
      }
      const out = lines.join("\n");
      answersOutputEl.textContent = out;
      _appendChatMessage("assistant", "Answers", out);
    }

    statusEl.textContent = "Answers generated.";
    if (markSubmittedBtn) {
      markSubmittedBtn.disabled = !applicationId;
    }
    await saveLastJobToStorage();
  } catch (err) {
    console.error("answer-questions error", err);
    statusEl.textContent = "Error generating answers.";
    answersOutputEl.textContent = String(err);
  } finally {
    answerQuestionsBtn.disabled = false;
  }
});
