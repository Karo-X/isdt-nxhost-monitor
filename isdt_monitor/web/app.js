"use strict";

const slotsNode = document.querySelector("#slots");
const recentNode = document.querySelector("#recent");
const rawNode = document.querySelector("#raw-output");
const channelSelect = document.querySelector("#history-channel");
const fieldSelect = document.querySelector("#history-field");
const hideInactiveToggle = document.querySelector("#hide-inactive");
const slotCountNode = document.querySelector("#slot-count");
const canvas = document.querySelector("#chart");
const chartEmpty = document.querySelector("#chart-empty");
let selectedChannel = null;
let latestHistory = [];
const fileMode = window.location.protocol === "file:";
let hideInactive = false;
try { hideInactive = localStorage.getItem("nxhost-hide-inactive") === "1"; } catch (_) {}
hideInactiveToggle.checked = hideInactive;

function node(tag, className, text) {
  const item = document.createElement(tag);
  if (className) item.className = className;
  if (text !== undefined) item.textContent = text;
  return item;
}

function number(value, digits = 0) {
  if (value === null || value === undefined) return "—";
  return Number(value).toLocaleString("de-DE", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function localTime(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString("de-DE", { hour12: false });
}

function duration(value) {
  if (value === null || value === undefined) return "—";
  const total = Math.max(0, Math.round(Number(value)));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const seconds = total % 60;
  return hours ? `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}` : `${minutes}:${String(seconds).padStart(2, "0")}`;
}

function addMetric(parent, label, value) {
  const metric = node("div", "metric");
  metric.append(node("small", "", label), node("b", "", value));
  parent.append(metric);
}

function renderCard(channel, sample, manualLabel) {
  const card = node("article", "slot-card");
  if (channel === selectedChannel) card.classList.add("active");
  if (sample?.error) card.classList.add("error");
  card.addEventListener("click", () => {
    selectedChannel = channel;
    channelSelect.value = String(channel);
    load();
  });

  const head = node("div", "slot-head");
  const title = node("div");
  title.append(
    node("div", "slot-title", `Slot ${channel + 1}`),
    node("div", "slot-channel", `${manualLabel ? `${manualLabel} · manuell · ` : ""}isdttool-Kanal ${channel}`),
  );
  const hasData = Boolean(sample?.has_nonzero_measurement);
  const measurement = hasData ? sample : null;
  head.append(title, node("span", `pill ${hasData ? "data" : ""}`, hasData ? "MESSWERTE" : "NULL / OFFEN"));
  card.append(head);

  const primary = node("div", "primary-reading");
  primary.append(node("strong", "", number(measurement?.voltage_mv)), node("span", "", "mV · exp."));
  card.append(primary);

  const grid = node("div", "metric-grid");
  addMetric(grid, "Momentanstrom", `${number(measurement?.current_ma_unverified)} mA`);
  addMetric(grid, "Widerstand", `${number(measurement?.resistance_mohm_unverified)} mΩ`);
  addMetric(grid, "Temperatur", `${number(measurement?.temperature_c_candidate)} °C`);
  addMetric(grid, "Kapazität", `${number(measurement?.capacity_mah_candidate)} mAh`);
  addMetric(grid, "Status / %", number(measurement?.state_or_soc_candidate));
  addMetric(grid, "Zeit-Kandidat", duration(measurement?.elapsed_seconds_candidate));
  card.append(grid);
  if (sample?.error) card.append(node("p", "card-error", sample.error));
  card.append(node("div", "card-time", sample ? `Letzte Abfrage ${localTime(sample.observed_at)}` : "Noch nicht abgefragt"));
  return card;
}

function renderRecent(samples) {
  recentNode.replaceChildren();
  for (const sample of samples) {
    const row = document.createElement("tr");
    const values = [
      localTime(sample.observed_at),
      `Slot ${sample.channel + 1} / ${sample.channel}`,
      `${number(sample.voltage_mv)} mV`,
      `${number(sample.current_ma_unverified)} mA`,
      `${number(sample.resistance_mohm_unverified)} mΩ`,
      `${number(sample.temperature_c_candidate)} °C`,
      `${number(sample.capacity_mah_candidate)} / ${number(sample.state_or_soc_candidate)} / ${duration(sample.elapsed_seconds_candidate)}`,
    ];
    for (const value of values) row.append(node("td", "", value));
    row.append(node("td", sample.error ? "bad" : "ok", sample.error ? "Fehler" : "OK"));
    row.addEventListener("click", () => {
      rawNode.textContent = [
        `Zeit: ${sample.observed_at}`,
        `Slot ${sample.channel + 1} / Kanal ${sample.channel}`,
        sample.error ? `Fehler: ${sample.error}` : "Fehler: keiner",
        `Reading: ${sample.raw_frame || "nicht vorhanden"}`,
        `Profil-/Moduscodes (Bytes 7/8/9/11): ${number(sample.code_7_candidate)} / ${number(sample.code_8_candidate)} / ${number(sample.code_9_candidate)} / ${number(sample.code_11_candidate)}`,
        `Temperatur (Byte 10): ${number(sample.temperature_c_candidate)} °C`,
        `Status/% (Byte 12): ${number(sample.state_or_soc_candidate)}`,
        `Spannung (Offset 13): ${number(sample.voltage_mv)} mV`,
        `Momentanstrom (Offset 15): ${number(sample.current_ma_unverified)} mA`,
        `Widerstand (Offset 17): ${number(sample.resistance_mohm_unverified)} mΩ`,
        `Rohwert Offset 19: ${number(sample.unknown_offset19_u16)}`,
        `Unbekannt A (Offset 21): ${number(sample.unknown_a)}`,
        `Kapazität (Offset 23): ${number(sample.capacity_mah_candidate)} mAh`,
        `Zeit-Kandidat (Offset 27): ${number(sample.elapsed_seconds_candidate)} s`,
        "",
        "Vollständige isdttool-Ausgabe:",
        sample.raw_output || "(leer)",
      ].join("\n");
    });
    recentNode.append(row);
  }
}

function setupChannels(channels) {
  const signature = channels.join(",");
  if (channelSelect.dataset.signature === signature) return;
  channelSelect.dataset.signature = signature;
  channelSelect.replaceChildren();
  for (const channel of channels) {
    const option = node("option", "", `${channel + 1} (Kanal ${channel})`);
    option.value = String(channel);
    channelSelect.append(option);
  }
  if (selectedChannel === null || !channels.includes(selectedChannel)) selectedChannel = channels[0];
  channelSelect.value = String(selectedChannel);
}

async function loadHistory() {
  if (selectedChannel === null) return;
  const response = await fetch(`/api/history?channel=${selectedChannel}&limit=500`, { cache: "no-store" });
  if (!response.ok) throw new Error(`Verlauf: HTTP ${response.status}`);
  latestHistory = (await response.json()).samples;
  drawChart();
}

function drawChart() {
  const field = fieldSelect.value;
  const points = latestHistory.filter(sample => sample[field] !== null && sample[field] !== undefined);
  chartEmpty.hidden = points.length > 1;
  const rect = canvas.getBoundingClientRect();
  const scale = window.devicePixelRatio || 1;
  canvas.width = Math.max(1, Math.round(rect.width * scale));
  canvas.height = Math.max(1, Math.round(rect.height * scale));
  const ctx = canvas.getContext("2d");
  ctx.scale(scale, scale);
  const width = rect.width;
  const height = rect.height;
  ctx.clearRect(0, 0, width, height);
  if (points.length < 2) return;

  const pad = { left: 54, right: 18, top: 18, bottom: 30 };
  const values = points.map(point => Number(point[field]));
  let min = Math.min(...values);
  let max = Math.max(...values);
  if (min === max) { min -= 1; max += 1; }
  const extra = (max - min) * 0.12;
  min -= extra; max += extra;
  const x = index => pad.left + index * (width - pad.left - pad.right) / (points.length - 1);
  const y = value => pad.top + (max - value) * (height - pad.top - pad.bottom) / (max - min);

  ctx.font = "11px -apple-system, system-ui, sans-serif";
  ctx.fillStyle = "#81909a";
  ctx.strokeStyle = "#25303b";
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i += 1) {
    const yy = pad.top + i * (height - pad.top - pad.bottom) / 4;
    const value = max - i * (max - min) / 4;
    ctx.beginPath(); ctx.moveTo(pad.left, yy); ctx.lineTo(width - pad.right, yy); ctx.stroke();
    ctx.fillText(number(value, Math.abs(max - min) < 10 ? 1 : 0), 4, yy + 4);
  }
  ctx.fillText(localTime(points[0].observed_at), pad.left, height - 7);
  const endLabel = localTime(points.at(-1).observed_at);
  ctx.fillText(endLabel, width - pad.right - ctx.measureText(endLabel).width, height - 7);

  const gradient = ctx.createLinearGradient(0, pad.top, 0, height - pad.bottom);
  gradient.addColorStop(0, "rgba(87,230,175,.3)");
  gradient.addColorStop(1, "rgba(87,230,175,0)");
  ctx.beginPath();
  points.forEach((point, index) => index ? ctx.lineTo(x(index), y(Number(point[field]))) : ctx.moveTo(x(index), y(Number(point[field]))));
  ctx.lineTo(x(points.length - 1), height - pad.bottom); ctx.lineTo(x(0), height - pad.bottom); ctx.closePath();
  ctx.fillStyle = gradient; ctx.fill();
  ctx.beginPath();
  points.forEach((point, index) => index ? ctx.lineTo(x(index), y(Number(point[field]))) : ctx.moveTo(x(index), y(Number(point[field]))));
  ctx.strokeStyle = "#57e6af"; ctx.lineWidth = 2; ctx.stroke();
}

async function load() {
  try {
    const response = await fetch("/api/state", { cache: "no-store" });
    if (!response.ok) throw new Error(`Status: HTTP ${response.status}`);
    const state = await response.json();
    setupChannels(state.config.channels);
    document.querySelector("#mode").textContent = state.config.demo ? "DEMO · KEINE HARDWARE" : "LIVE · USB";
    document.querySelector("#live-dot").classList.toggle("on", state.collector.running);
    const polling = state.collector.polling_channel;
    document.querySelector("#status").textContent = polling === null ? "Serielles Polling aktiv" : `Kanal ${polling} wird gelesen …`;
    document.querySelector("#cycle").textContent = `Zyklen: ${state.collector.cycles} · Intervall: ${number(state.config.poll_interval_seconds, 0)} s`;
    const latest = new Map(state.latest.map(item => [item.channel, item]));
    const activeCount = state.config.channels.filter(channel => latest.get(channel)?.has_nonzero_measurement).length;
    const visibleChannels = state.config.channels.filter(channel => !hideInactive || latest.get(channel)?.has_nonzero_measurement);
    const cards = visibleChannels.map(channel => renderCard(channel, latest.get(channel), state.config.slot_labels?.[String(channel)]));
    slotsNode.replaceChildren(...cards);
    if (!cards.length) slotsNode.append(node("p", "muted", "Noch keine aktiven Slots erkannt."));
    slotCountNode.textContent = `${activeCount} aktiv · ${state.config.channels.length} konfiguriert · Slot 1 = Kanal 0`;
    renderRecent(state.recent);
    await loadHistory();
  } catch (error) {
    document.querySelector("#live-dot").classList.remove("on");
    document.querySelector("#status").textContent = `Verbindungsfehler: ${error.message}`;
  }
}

function showFileMode() {
  const channels = Array.from({ length: 8 }, (_, index) => index);
  selectedChannel = 0;
  setupChannels(channels);
  slotsNode.replaceChildren(...channels.map(channel => renderCard(channel, null, null)));
  document.querySelector("#mode").textContent = "SERVER NICHT GESTARTET";
  document.querySelector("#status").textContent =
    "Diese HTML-Datei wurde direkt geöffnet. Bitte im Hauptordner isdt-nxhost-monitor die Datei start.command doppelklicken.";
  document.querySelector("#cycle").textContent = "Danach öffnet sich http://127.0.0.1:8765/ automatisch.";
  chartEmpty.hidden = false;
  chartEmpty.textContent = "Start erforderlich – noch keine Messwertabfragen.";
  rawNode.textContent = [
    "Der Monitor benötigt den lokalen Python-Server.",
    "",
    "So startest du ihn:",
    "1. Zum Hauptordner isdt-nxhost-monitor wechseln.",
    "2. start.command doppelklicken.",
    "3. Dieses file://-Fenster schließen; die richtige localhost-Seite öffnet sich automatisch.",
    "",
    "Alternativ im Terminal:",
    "~/isdt-env/bin/python main.py",
  ].join("\n");
  channelSelect.disabled = true;
  fieldSelect.disabled = true;
  hideInactiveToggle.disabled = true;
  const download = document.querySelector("#csv-download");
  download.textContent = "CSV nach dem Start verfügbar";
  download.href = "#";
  download.addEventListener("click", event => event.preventDefault());
}

if (fileMode) {
  showFileMode();
} else {
  hideInactiveToggle.addEventListener("change", () => {
    hideInactive = hideInactiveToggle.checked;
    try { localStorage.setItem("nxhost-hide-inactive", hideInactive ? "1" : "0"); } catch (_) {}
    load();
  });
  channelSelect.addEventListener("change", () => { selectedChannel = Number(channelSelect.value); loadHistory(); });
  fieldSelect.addEventListener("change", drawChart);
  window.addEventListener("resize", drawChart);
  load();
  setInterval(load, 2500);
}
