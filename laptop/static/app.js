// Live dashboard: plots raw IMU data, tilts the board graphic, edits the mapping.

const WINDOW_S = 5;
const COLORS = { x: "#ff5c5c", y: "#4cd07d", z: "#4c9aff", lean: "#ffcc00" };
// Sample row layout from the server: t, ax, ay, az, gx, gy, gz, roll, pitch, yaw, lean, nose, stick_x
const COL = { t: 0, ax: 1, ay: 2, az: 3, gx: 4, gy: 5, gz: 6, roll: 7, pitch: 8, yaw: 9, lean: 10, nose: 11, stick: 12 };

const $ = (id) => document.getElementById(id);
let config = null;
let samples = [];
let ws;

class Chart {
  constructor(canvas, series, minSpan) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.series = series; // [{col, color}]
    this.minSpan = minSpan;
  }
  draw(rows) {
    const { canvas, ctx } = this;
    const w = (canvas.width = canvas.clientWidth * devicePixelRatio);
    const h = (canvas.height = 140 * devicePixelRatio);
    ctx.clearRect(0, 0, w, h);
    if (rows.length < 2) return;
    const tEnd = rows[rows.length - 1][COL.t];
    const tStart = tEnd - WINDOW_S;
    let lo = Infinity, hi = -Infinity;
    for (const r of rows) for (const s of this.series) { lo = Math.min(lo, r[s.col]); hi = Math.max(hi, r[s.col]); }
    const mid = (lo + hi) / 2;
    const span = Math.max(hi - lo, this.minSpan) * 1.15;
    lo = mid - span / 2; hi = mid + span / 2;
    const y = (v) => h - ((v - lo) / (hi - lo)) * h;
    const x = (t) => ((t - tStart) / WINDOW_S) * w;

    ctx.strokeStyle = "#262b35"; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(0, y(0)); ctx.lineTo(w, y(0)); ctx.stroke();
    ctx.fillStyle = "#8a93a6"; ctx.font = `${11 * devicePixelRatio}px system-ui`;
    ctx.fillText(hi.toFixed(1), 4, 12 * devicePixelRatio);
    ctx.fillText(lo.toFixed(1), 4, h - 4);

    ctx.lineWidth = 1.5 * devicePixelRatio;
    for (const s of this.series) {
      ctx.strokeStyle = s.color; ctx.beginPath();
      rows.forEach((r, i) => (i ? ctx.lineTo(x(r[COL.t]), y(r[s.col])) : ctx.moveTo(x(r[COL.t]), y(r[s.col]))));
      ctx.stroke();
    }
  }
}

const charts = [
  new Chart($("chart-accel"), [{ col: COL.ax, color: COLORS.x }, { col: COL.ay, color: COLORS.y }, { col: COL.az, color: COLORS.z }], 2),
  new Chart($("chart-gyro"), [{ col: COL.gx, color: COLORS.x }, { col: COL.gy, color: COLORS.y }, { col: COL.gz, color: COLORS.z }], 60),
  new Chart($("chart-orient"), [{ col: COL.roll, color: COLORS.x }, { col: COL.pitch, color: COLORS.y }, { col: COL.lean, color: COLORS.lean }], 20),
];

function connect() {
  ws = new WebSocket(`ws://${location.host}/ws`);
  ws.onmessage = (e) => handle(JSON.parse(e.data));
  ws.onclose = () => setTimeout(connect, 1000);
}

function send(cmd) {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(cmd));
}

function handle(msg) {
  if (msg.type === "config") {
    config = msg.config;
    renderConfig();
    if (msg.recordings) renderRecordings(msg.recordings);
  } else if (msg.type === "recordings") {
    renderRecordings(msg.recordings);
  } else if (msg.type === "frame") {
    if (msg.samples.length) {
      samples.push(...msg.samples);
      const tEnd = samples[samples.length - 1][COL.t];
      const firstKeep = samples.findIndex((r) => r[COL.t] >= tEnd - WINDOW_S);
      if (firstKeep > 0) samples = samples.slice(firstKeep);
    }
    renderStatus(msg.status);
    if (msg.latest && msg.latest.state) renderLatest(msg.latest);
  }
}

function renderStatus(s) {
  const conn = $("conn");
  conn.textContent = s.calibrating ? "CALIBRATING…" : s.connected ? "BOARD LIVE" : "NO BOARD";
  conn.className = "pill " + (s.connected ? "on" : "off");
  $("rate").textContent = `${s.packet_rate} pkt/s`;
  $("lost").textContent = `${s.lost} lost`;
  const pad = $("pad");
  pad.textContent = `Virtual pad: ${s.pad_enabled ? "ON" : "OFF"}`;
  pad.classList.toggle("active", s.pad_enabled);
  $("pad-error").textContent = s.pad_error || "";
  $("calib").textContent = s.calibration_message;
  const rec = $("record");
  rec.textContent = s.recording ? "■ Stop" : "● Record";
  rec.classList.toggle("recording", !!s.recording);
  $("rec-status").textContent = s.recording ? `recording → ${s.recording}` : "";
}

function renderLatest(l) {
  $("lean").textContent = `${l.lean.toFixed(1)}°`;
  $("nose").textContent = `${l.nose.toFixed(1)}°`;
  $("state").textContent = l.state;
  $("stickval").textContent = l.stick_x.toFixed(2);
  $("needle").style.left = `${50 + l.stick_x * 50}%`;
  // Board graphic: viewed from above at an angle; lean rolls about its long axis, nose pitches it.
  $("board").style.transform = `rotateX(55deg) rotateY(${-l.nose}deg) rotateX(${l.lean}deg)`;
}

function renderConfig() {
  if (!config) return;
  $("lean-source").value = config.lean.source;
  $("lean-invert").checked = config.lean.invert;
  $("nose-source").value = config.nose.source;
  $("nose-invert").checked = config.nose.invert;
  $("deadzone").value = config.left_stick_x.deadzone_deg;
  $("maxdeg").value = config.left_stick_x.max_deg;
  $("deadzone-val").textContent = `${config.left_stick_x.deadzone_deg}°`;
  $("maxdeg-val").textContent = `${config.left_stick_x.max_deg}°`;
  const dzFrac = config.left_stick_x.deadzone_deg / config.left_stick_x.max_deg;
  $("dz").style.left = `${50 - dzFrac * 50}%`;
  $("dz").style.width = `${dzFrac * 100}%`;
}

function renderRecordings(list) {
  $("recordings").innerHTML = list.map((n) => `<li>${n}</li>`).join("");
}

$("calibrate").onclick = () => send({ cmd: "calibrate" });
$("pad").onclick = () => send({ cmd: "pad", on: !$("pad").classList.contains("active") });
$("record").onclick = () => {
  if ($("record").classList.contains("recording")) send({ cmd: "stop" });
  else send({ cmd: "record", label: $("label").value.trim() });
};
$("label").addEventListener("keydown", (e) => { if (e.key === "Enter") $("record").click(); });
$("lean-source").onchange = (e) => send({ cmd: "config", update: { lean: { source: e.target.value } } });
$("lean-invert").onchange = (e) => send({ cmd: "config", update: { lean: { invert: e.target.checked } } });
$("nose-source").onchange = (e) => send({ cmd: "config", update: { nose: { source: e.target.value } } });
$("nose-invert").onchange = (e) => send({ cmd: "config", update: { nose: { invert: e.target.checked } } });
$("deadzone").oninput = (e) => send({ cmd: "config", update: { left_stick_x: { deadzone_deg: +e.target.value } } });
$("maxdeg").oninput = (e) => send({ cmd: "config", update: { left_stick_x: { max_deg: +e.target.value } } });

function frame() {
  charts.forEach((c) => c.draw(samples));
  requestAnimationFrame(frame);
}

connect();
requestAnimationFrame(frame);
