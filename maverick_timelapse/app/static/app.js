"use strict";
import { defaultSchedule, scheduledStart } from "./schedule.mjs";
import { capturePresets, defaultPreset } from "./presets.mjs";
const form = document.getElementById("job-form");
const notice = document.getElementById("notice");
const player = document.getElementById("player");
const composer = document.getElementById("composer");
const formNotice = document.getElementById("form-notice");
const jobsContainer = document.getElementById("jobs");
const cards = new Map();
let refreshing = false;
let jobFilter = "all";
let latestJobs = [];
const cameraNames = new Map();

function showError(message) {
  const target = composer.open ? formNotice : notice;
  target.textContent = message;
  target.hidden = false;
  if (composer.open) target.scrollIntoView({ block: "nearest" });
}
function clearError() {
  for (const target of [notice, formNotice]) { target.hidden = true; target.textContent = ""; }
}
function openComposer() {
  if (composer.open) return;
  composer.showModal();
  if (!notice.hidden) { formNotice.textContent = notice.textContent; formNotice.hidden = false; }
  composer.querySelector(".form-body").scrollTop = 0;
  form.elements.name.focus({ preventScroll: true });
}
for (const id of ["new-recording", "empty-create"]) document.getElementById(id).addEventListener("click", openComposer);
for (const id of ["close-composer", "cancel-composer"]) document.getElementById(id).addEventListener("click", () => composer.close());
composer.addEventListener("close", () => { formNotice.hidden = true; });
async function api(path, options = {}) {
  const response = await fetch(`./api/${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", "X-Maverick-Request": "1", ...options.headers },
  });
  if (!response.ok) {
    let message = `Request failed (${response.status}).`;
    try {
      const error = await response.json();
      message = Array.isArray(error.detail) ? error.detail.map(item => item.msg).join(" ") : error.detail || message;
    } catch (_) { /* A proxy may return an HTML error page. */ }
    throw new Error(message);
  }
  return response.status === 204 ? null : response.json();
}
function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
function bytes(value) { return `${(value / 1024 ** 3).toFixed(2)} GiB`; }
function date(value) { return new Date(value * 1000).toLocaleString(); }
const presetSelect = document.getElementById("capture-preset");
const presetHelp = document.getElementById("preset-help");
presetSelect.replaceChildren();
for (const preset of capturePresets) {
  presetSelect.add(new Option(`${preset.name} — every ${preset.seconds}s`, preset.id));
}
presetSelect.add(new Option("Custom interval", "custom"));

function describePreset() {
  const preset = capturePresets.find(item => item.id === presetSelect.value);
  document.getElementById("preset-summary").textContent = preset ? preset.description.split(". ")[0] + "." : "Custom interval. Choose how often to capture a snapshot.";
  presetHelp.textContent = preset ? preset.description
    : "Choose any interval from 5 to 86,400 seconds. Shorter intervals capture more movement and use more storage. Choose an interval your camera can reliably refresh.";
}

function applyPreset() {
  const preset = capturePresets.find(item => item.id === presetSelect.value);
  if (preset) form.elements.interval_seconds.value = preset.seconds;
  describePreset();
  estimate();
}
presetSelect.addEventListener("change", applyPreset);
form.elements.interval_seconds.addEventListener("input", () => {
  // A manual edit is custom even when it happens to equal another preset.
  // Selecting Custom preserves the user's number rather than resetting it.
  presetSelect.value = "custom";
  describePreset();
});
presetSelect.value = defaultPreset;
applyPreset();

function estimate() {
  const interval = Number(form.elements.interval_seconds.value);
  const duration = Number(form.elements.duration_minutes.value);
  const fps = Number(form.elements.fps.value);
  document.getElementById("estimate").textContent = interval > 0 && duration > 0
    ? `${(Math.ceil(duration * 60 / interval) / fps).toFixed(1)} sec video · ${Math.ceil(duration * 60 / interval).toLocaleString()} frames at ${fps} FPS` : "Enter an interval and duration.";
}
form.addEventListener("input", estimate);
estimate();

function updateStartMode() {
  const scheduled = form.elements.start_mode.value === "scheduled";
  document.getElementById("scheduled-start").hidden = !scheduled;
  document.getElementById("start-help").textContent = scheduled
    ? "Recording begins at the date and time you choose below."
    : "Recording begins when you press Start recording.";
  for (const input of [form.elements.start_date, form.elements.start_time]) {
    input.disabled = !scheduled;
    input.setCustomValidity("");
  }
  document.getElementById("create-button").textContent = scheduled ? "Schedule recording" : "Start recording";
  if (scheduled && !form.elements.start_date.value && !form.elements.start_time.value) {
    const suggested = defaultSchedule();
    form.elements.start_date.value = suggested.date;
    form.elements.start_time.value = suggested.time;
  }
}
document.getElementById("start-mode").addEventListener("change", updateStartMode);
document.getElementById("start-timezone").textContent = `Choose a future time. Timezone: ${Intl.DateTimeFormat().resolvedOptions().timeZone}.`;
for (const input of [form.elements.start_date, form.elements.start_time]) {
  input.addEventListener("invalid", () => {
    input.setCustomValidity("Choose a complete date and time, or select Start now.");
  });
  input.addEventListener("input", () => input.setCustomValidity(""));
}
updateStartMode();

async function loadCameras() {
  const refreshButton = document.getElementById("refresh-cameras");
  refreshButton.disabled = true;
  try {
    const cameras = await api("cameras");
    cameraNames.clear();
    for (const camera of cameras) cameraNames.set(camera.entity_id, camera.name);
    const select = document.getElementById("camera");
    const selected = select.value;
    select.replaceChildren(new Option(cameras.length ? "Choose a camera" : "No camera entities found", ""));
    for (const camera of cameras) {
      const unavailable = ["unavailable", "unknown"].includes(camera.state);
      const option = new Option(`${camera.name}${unavailable ? " (unavailable)" : ""}`, camera.entity_id);
      option.disabled = unavailable;
      select.add(option);
    }
    select.value = selected;
    const available = cameras.filter(c => !["unavailable", "unknown"].includes(c.state));
    document.getElementById("create-button").disabled = !available.length;
    document.getElementById("camera-help").textContent = available.length
      ? "Choose a camera already connected to Home Assistant."
      : "No available cameras. Check your camera integration in Home Assistant, then refresh.";
  } catch (error) { showError(error.message); }
  finally { refreshButton.disabled = false; }
}
document.getElementById("refresh-cameras").addEventListener("click", () => { clearError(); loadCameras(); });

form.addEventListener("submit", async event => {
  event.preventDefault();
  const button = document.getElementById("create-button");
  button.disabled = true;
  clearError();
  try {
    const values = Object.fromEntries(new FormData(form));
    for (const key of ["interval_seconds", "duration_minutes", "fps"]) values[key] = Number(values[key]);
    values.start_at = values.start_mode === "scheduled"
      ? scheduledStart(values.start_date, values.start_time) : null;
    for (const key of ["start_mode", "start_date", "start_time", "capture_preset"]) delete values[key];
    await api("jobs", { method: "POST", body: JSON.stringify(values) });
    form.elements.name.value = "";
    form.elements.start_mode.value = "now";
    form.elements.start_date.value = "";
    form.elements.start_time.value = "";
    updateStartMode();
    composer.close();
    setFilter("all");
    await refreshJobs();
    await refreshStorage();
  } catch (error) { showError(error.message); }
  finally { button.disabled = false; }
});

function action(label, className, callback) {
  const button = element("button", className, label);
  button.type = "button";
  button.addEventListener("click", async () => {
    clearError(); button.disabled = true;
    try { await callback(); }
    catch (error) { showError(error.message); }
    finally { button.disabled = false; }
    await refreshJobs();
  });
  return button;
}
function duration(seconds) {
  if (seconds > 0 && seconds < 0.1) return "<0.1s";
  return seconds < 60 ? `${seconds.toFixed(1)}s` : `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`;
}
function watch(job) {
  document.getElementById("player-title").textContent = job.name;
  player.querySelector("video").src = `./api/jobs/${job.id}/video`;
  player.showModal();
}
const previewObserver = new IntersectionObserver(entries => {
  for (const entry of entries) if (entry.isIntersecting) {
    const video = entry.target;
    video.src = video.dataset.src;
    previewObserver.unobserve(video);
  }
}, { rootMargin: "100px" });
function previewIcon() {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 32 32");
  svg.setAttribute("aria-hidden", "true");
  const path = document.createElementNS(svg.namespaceURI, "path");
  path.setAttribute("d", "M6 8h20a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V10a2 2 0 0 1 2-2Zm4 0 2-3h8l2 3M21 17a5 5 0 1 1-10 0 5 5 0 0 1 10 0Z");
  svg.append(path);
  return svg;
}
function updateProgress(card, job) {
  if (job.status !== "capturing") return;
  const progress = card.querySelector("progress");
  if (!progress) return;
  const value = Math.max(0, Math.min(100, (Date.now() / 1000 - job.start_at) / (job.end_at - job.start_at) * 100));
  progress.value = value;
  card.querySelector(".progress-value").textContent = `${Math.floor(value)}%`;
}
function buildCard(job) {
  const card = element("article", "job");
  const preview = element("div", "preview");
  const fallback = element("div", "preview-placeholder");
  fallback.append(previewIcon(), element("span", "", job.status === "scheduled" ? "Starts at the scheduled time" : job.status === "completed" ? "MP4 video" : job.status === "rendering" ? "Preparing video…" : job.status === "failed" ? "No preview available" : "Waiting for a snapshot"));
  preview.append(fallback);
  if (job.status === "completed") {
    const video = element("video");
    video.muted = true; video.playsInline = true; video.preload = "metadata";
    video.setAttribute("aria-hidden", "true"); video.tabIndex = -1;
    video.dataset.src = `./api/jobs/${job.id}/video#t=0.001`;
    video.addEventListener("loadeddata", () => { video.classList.add("loaded"); fallback.hidden = true; });
    video.addEventListener("error", () => { video.remove(); fallback.hidden = false; });
    preview.append(video);
    previewObserver.observe(video);
    const play = element("button", "preview-play");
    play.type = "button"; play.setAttribute("aria-label", `Watch ${job.name}`);
    const disc = element("span", "play-disc"); disc.setAttribute("aria-hidden", "true");
    const playIcon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    playIcon.setAttribute("viewBox", "0 0 24 24");
    const triangle = document.createElementNS(playIcon.namespaceURI, "path");
    triangle.setAttribute("d", "M8 5v14l11-7z");
    playIcon.append(triangle); disc.append(playIcon); play.append(disc);
    play.addEventListener("click", () => watch(job));
    preview.append(play, element("span", "preview-time", duration(job.frames / job.fps)));
  } else if (job.frames > 0) {
    const image = element("img");
    image.src = `./api/jobs/${job.id}/snapshot?v=${job.frames}`;
    image.alt = `Latest snapshot for ${job.name}`; image.loading = "lazy";
    image.addEventListener("load", () => { image.classList.add("loaded"); fallback.hidden = true; });
    image.addEventListener("error", () => { image.remove(); fallback.querySelector("span").textContent = "Snapshot unavailable"; });
    preview.append(image);
  }
  const body = element("div", "job-body");
  const heading = element("div", "job-heading");
  const statuses = { capturing: "Recording", scheduled: "Scheduled", rendering: "Rendering", completed: "Ready", failed: "Failed" };
  heading.append(element("h3", "", job.name), element("span", `status status-${job.status}`, statuses[job.status] || job.status));
  body.append(heading, element("p", "camera", cameraNames.get(job.camera) || job.camera));
  const active = ["scheduled", "capturing", "rendering"].includes(job.status);
  if (job.status === "capturing" || job.status === "rendering") {
    const caption = element("div", "progress-label");
    caption.append(element("span", "", job.status === "capturing" ? "Recording" : "Creating MP4"), element("span", "progress-value"));
    const progress = element("progress"); progress.max = 100;
    progress.setAttribute("aria-label", job.status === "capturing" ? "Recording progress" : "Creating video");
    body.append(caption, progress);
  }
  body.append(element("p", "meta", `${job.frames.toLocaleString()} frames · ${duration(job.frames / job.fps)} video · every ${job.interval_seconds}s`));
  body.append(element("p", "job-timing", `${job.status === "scheduled" ? "Starts" : job.frames ? "Started" : "Start time"} ${date(job.start_at)}`));
  const details = element("details", "job-details");
  details.append(element("summary", "", "Recording details"));
  const list = element("dl");
  for (const [label, value] of [["Camera entity", job.camera], ["Start", date(job.start_at)], ["End", date(job.end_at)], ["Video frame rate", `${job.fps} FPS`], ["Failed captures", String(job.errors)]]) {
    list.append(element("dt", "", label), element("dd", "", value));
  }
  details.append(list); body.append(details);
  if (job.last_error) body.append(element("p", "error", job.last_error));
  else if (job.errors) body.append(element("p", "error", `${job.errors} failed captures`));
  const actions = element("div", "actions");
  if (["scheduled", "capturing"].includes(job.status)) {
    actions.append(action(job.frames ? "Finish video now" : "Stop recording", "secondary", async () => {
      if (window.confirm(job.frames ? "Finish this recording and create its video now?" : "Stop this recording? No video will be created without snapshots."))
        await api(`jobs/${job.id}/finish`, { method: "POST" });
    }));
  }
  if (job.status === "completed") {
    actions.append(action("Watch", "", () => watch(job)));
    const download = element("a", "button secondary", "Download MP4");
    download.href = `./api/jobs/${job.id}/video?download=true`; actions.append(download);
  }
  if (job.status === "failed" && job.frames) actions.append(action("Retry video", "secondary", () => api(`jobs/${job.id}/retry`, { method: "POST" })));
  if (!active) actions.append(action("Delete", "text-button danger", async () => {
    if (window.confirm(`Delete “${job.name}” and all its saved files?`)) await api(`jobs/${job.id}`, { method: "DELETE" });
  }));
  body.append(actions); card.append(preview, body); updateProgress(card, job);
  return card;
}
function matchesFilter(job) {
  return jobFilter === "all" || (jobFilter === "active" ? ["scheduled", "capturing", "rendering"].includes(job.status) : job.status === "completed");
}
function updateLibrary() {
  const counts = { all: latestJobs.length, active: latestJobs.filter(job => ["scheduled", "capturing", "rendering"].includes(job.status)).length, completed: latestJobs.filter(job => job.status === "completed").length };
  for (const [key, count] of Object.entries(counts)) document.getElementById(`count-${key}`).textContent = count;
  const failed = latestJobs.filter(job => job.status === "failed").length;
  const summary = [];
  if (counts.active) summary.push(`${counts.active} in progress`);
  if (counts.completed) summary.push(`${counts.completed} finished ${counts.completed === 1 ? "video" : "videos"}`);
  if (failed) summary.push(`${failed} failed`);
  document.getElementById("library-summary").textContent = summary.join(" · ") || "Recordings and finished videos";
  for (const job of latestJobs) if (cards.has(job.id)) cards.get(job.id).node.hidden = !matchesFilter(job);
  document.getElementById("empty").hidden = latestJobs.some(matchesFilter);
  const emptyText = jobFilter === "active" ? ["No recordings in progress", "Start a recording or schedule one for later."] : jobFilter === "completed" ? ["No finished videos", "Your videos will appear here when rendering is complete."] : ["No timelapses yet", "Create a recording from a Home Assistant camera."];
  document.getElementById("empty-title").textContent = emptyText[0];
  document.getElementById("empty-description").textContent = emptyText[1];
}
function setFilter(value) {
  jobFilter = value;
  for (const button of document.querySelectorAll("[data-filter]")) button.setAttribute("aria-pressed", String(button.dataset.filter === value));
  updateLibrary();
}
for (const button of document.querySelectorAll("[data-filter]")) button.addEventListener("click", () => setFilter(button.dataset.filter));
async function refreshJobs() {
  if (refreshing) return;
  refreshing = true;
  try {
    const jobs = await api("jobs");
    latestJobs = jobs;
    const ids = new Set(jobs.map(job => job.id));
    for (const [id, entry] of cards) if (!ids.has(id)) {
      const preview = entry.node.querySelector("video"); if (preview) previewObserver.unobserve(preview);
      entry.node.remove(); cards.delete(id);
    }
    for (const job of jobs) {
      // Preserve pending actions; restore focus when changed content needs replacing.
      const signature = JSON.stringify([job, cameraNames.get(job.camera)]);
      const existing = cards.get(job.id);
      if (!existing || (existing.signature !== signature && !existing.node.querySelector("button:disabled"))) {
        const node = buildCard(job);
        if (existing) {
          const focused = existing.node.contains(document.activeElement) ? document.activeElement : null;
          const preview = existing.node.querySelector("video"); if (preview) previewObserver.unobserve(preview);
          const expanded = existing.node.querySelector("details").open;
          node.querySelector("details").open = expanded;
          existing.node.replaceWith(node);
          if (focused) {
            const replacement = [...node.querySelectorAll("button, a, summary")].find(item => item.tagName === focused.tagName && item.textContent === focused.textContent);
            const target = replacement || node.querySelector("h3");
            if (!replacement) target.tabIndex = -1;
            target.focus({ preventScroll: true });
          }
        } else jobsContainer.append(node);
        cards.set(job.id, { node, signature });
      }
      updateProgress(cards.get(job.id).node, job);
    }
    // Leave correctly ordered nodes in place so polling preserves focus and previews.
    let next = jobsContainer.firstElementChild;
    for (const job of jobs) {
      const node = cards.get(job.id).node;
      if (node !== next) jobsContainer.insertBefore(node, next);
      next = node.nextElementSibling;
    }
    updateLibrary();
  } catch (error) { showError(error.message); }
  finally { refreshing = false; jobsContainer.setAttribute("aria-busy", "false"); }
}
async function refreshStorage() {
  try {
    const status = await api("status");
    document.getElementById("storage").textContent = `${bytes(status.used_bytes)} / ${bytes(status.limit_bytes)}`;
    document.getElementById("storage-meter").value = Math.min(1, status.used_bytes / status.limit_bytes);
  } catch (error) { showError(error.message); }
}
function closePlayer() { player.close(); }
document.getElementById("close-player").addEventListener("click", closePlayer);
player.addEventListener("close", () => { const video = player.querySelector("video"); video.pause(); video.removeAttribute("src"); video.load(); });
loadCameras(); refreshJobs(); refreshStorage();
setInterval(refreshJobs, 5000);
setInterval(refreshStorage, 20000);
