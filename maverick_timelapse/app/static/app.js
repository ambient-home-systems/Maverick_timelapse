"use strict";
import { defaultSchedule, scheduledStart } from "./schedule.mjs";
import { capturePresets, defaultPreset } from "./presets.mjs";
const form = document.getElementById("job-form");
const notice = document.getElementById("notice");
const player = document.getElementById("player");
const jobsContainer = document.getElementById("jobs");
const cards = new Map();
let refreshing = false;

function showError(message) { notice.textContent = message; notice.hidden = false; }
function clearError() { notice.hidden = true; notice.textContent = ""; }
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
function bytes(value) { return `${(value / 1024 ** 3).toFixed(2)} GB`; }
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
    ? `About ${Math.ceil(duration * 60 / interval).toLocaleString()} snapshots → ${(Math.ceil(duration * 60 / interval) / fps).toFixed(1)} seconds of finished video at ${fps} FPS. Missed captures shorten the video.` : "";
}
form.addEventListener("input", estimate);
estimate();

function updateStartMode() {
  const scheduled = form.elements.start_mode.value === "scheduled";
  document.getElementById("scheduled-start").hidden = !scheduled;
  document.getElementById("start-help").textContent = scheduled
    ? "Recording begins at the date and time you choose below."
    : "Start now begins recording as soon as you create the timelapse.";
  for (const input of [form.elements.start_date, form.elements.start_time]) {
    input.disabled = !scheduled;
    input.setCustomValidity("");
  }
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
    document.getElementById("create-button").disabled = !cameras.some(c => !["unavailable", "unknown"].includes(c.state));
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
    await refreshJobs();
  } catch (error) { showError(error.message); }
  finally { button.disabled = false; }
});

function action(label, className, callback) {
  const button = element("button", className, label);
  button.type = "button";
  button.addEventListener("click", async () => {
    clearError(); button.disabled = true;
    try { await callback(); await refreshJobs(); }
    catch (error) { showError(error.message); }
    finally { button.disabled = false; }
  });
  return button;
}
function buildCard(job) {
  const card = element("article", "job");
  card.append(element("h3", "", job.name), element("p", "camera", job.camera), element("span", "status", job.status));
  const active = ["scheduled", "capturing", "rendering"].includes(job.status);
  if (["scheduled", "capturing"].includes(job.status)) {
    const progress = element("progress");
    progress.max = 100;
    progress.value = Math.max(0, Math.min(100, (Date.now() / 1000 - job.start_at) / (job.end_at - job.start_at) * 100));
    progress.setAttribute("aria-label", "Recording progress"); card.append(progress);
  }
  card.append(element("p", "meta", `${job.frames.toLocaleString()} frames · ${(job.frames / job.fps).toFixed(1)}s video · ${job.errors} failed captures`));
  card.append(element("p", "hint", `One snapshot every ${job.interval_seconds} seconds · Finished video: ${job.fps} FPS`));
  card.append(element("p", "hint", `Start: ${date(job.start_at)} · End: ${date(job.end_at)}`));
  if (job.last_error) card.append(element("p", "error", job.last_error));
  if (job.frames > 0 && job.status !== "completed") {
    const image = element("img", "snapshot");
    image.src = `./api/jobs/${job.id}/snapshot?v=${job.frames}`;
    image.alt = `Latest snapshot for ${job.name}`; image.loading = "lazy";
    image.addEventListener("error", () => image.remove()); card.append(image);
  }
  const actions = element("div", "actions");
  if (["scheduled", "capturing"].includes(job.status)) {
    actions.append(action(job.frames ? "Finish video now" : "Stop recording", "secondary", async () => {
      if (window.confirm(job.frames ? "Finish this recording and create its video now?" : "Stop this recording? No video will be created without snapshots."))
        await api(`jobs/${job.id}/finish`, { method: "POST" });
    }));
  }
  if (job.status === "completed") {
    actions.append(action("Watch", "", () => {
      document.getElementById("player-title").textContent = job.name;
      player.querySelector("video").src = `./api/jobs/${job.id}/video`; player.showModal();
    }));
    const download = element("a", "button secondary", "Download MP4");
    download.href = `./api/jobs/${job.id}/video?download=true`; actions.append(download);
  }
  if (job.status === "failed" && job.frames) actions.append(action("Retry video", "secondary", () => api(`jobs/${job.id}/retry`, { method: "POST" })));
  if (!active) actions.append(action("Delete", "secondary danger", async () => {
    if (window.confirm(`Delete “${job.name}” and all its saved files?`)) await api(`jobs/${job.id}`, { method: "DELETE" });
  }));
  card.append(actions); return card;
}
async function refreshJobs() {
  if (refreshing) return;
  refreshing = true;
  try {
    const jobs = await api("jobs");
    document.getElementById("empty").hidden = jobs.length > 0;
    const ids = new Set(jobs.map(job => job.id));
    for (const [id, entry] of cards) if (!ids.has(id)) { entry.node.remove(); cards.delete(id); }
    for (const job of jobs) {
      // Preserve unchanged cards, keyboard focus, and pending button actions during polling.
      const signature = JSON.stringify(job);
      const existing = cards.get(job.id);
      if (!existing || (existing.signature !== signature && !existing.node.contains(document.activeElement) && !existing.node.querySelector("button:disabled"))) {
        const node = buildCard(job);
        if (existing) existing.node.replaceWith(node); else jobsContainer.append(node);
        cards.set(job.id, { node, signature });
      }
    }
    // New jobs arrive at the top without rebuilding the other cards.
    for (const job of [...jobs].reverse()) jobsContainer.prepend(cards.get(job.id).node);
  } catch (error) { showError(error.message); }
  finally { refreshing = false; }
}
async function refreshStorage() {
  try {
    const status = await api("status");
    document.getElementById("storage").textContent = `${bytes(status.used_bytes)} / ${bytes(status.limit_bytes)} used`;
  } catch (error) { showError(error.message); }
}
function closePlayer() { player.close(); }
document.getElementById("close-player").addEventListener("click", closePlayer);
player.addEventListener("close", () => { const video = player.querySelector("video"); video.pause(); video.removeAttribute("src"); video.load(); });
loadCameras(); refreshJobs(); refreshStorage();
setInterval(refreshJobs, 5000);
setInterval(refreshStorage, 20000);
