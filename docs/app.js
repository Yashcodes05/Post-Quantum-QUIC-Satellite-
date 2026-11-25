let DATA = null;
const CHARTS = {};

const COLORS = {
  unmodified: "#f87171",
  handover_aware: "#34d399",
  leo: "#38bdf8",
  terrestrial: "#818cf8",
  warn: "#fbbf24",
  muted: "#93a4c4",
};

function destroyChart(id) {
  if (CHARTS[id]) {
    CHARTS[id].destroy();
    delete CHARTS[id];
  }
}

function setupTabs() {
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");
    });
  });
}

function renderKPIs() {
  const leoRows = DATA.rq2_algorithm_matrix.filter((r) => r.environment === "LEO_Starlink");
  const classical = leoRows.find((r) => r.profile === "X25519+RSA2048");
  const pq = leoRows.find((r) => r.profile === "Kyber768+Dilithium3");
  const blockedCount = leoRows.filter((r) => r.amplification_blocked_pct > 0).length;

  const unmod = DATA.rq3_rq4_mitigations.find(
    (r) => r.profile === "Kyber768+Dilithium3" && r.mitigation_id === "unmodified"
  );
  const aware = DATA.rq3_rq4_mitigations.find(
    (r) => r.profile === "Kyber768+Dilithium3" && r.mitigation_id === "handover_aware"
  );

  document.getElementById("kpiClassical").textContent = classical ? `${classical.mean_ms} ms` : "--";
  document.getElementById("kpiPQ").textContent = pq ? `${pq.mean_ms} ms` : "--";
  document.getElementById("kpiAmp").textContent = `${blockedCount} / ${leoRows.length}`;
  if (unmod && aware && unmod.mean_pto_fires > 0) {
    const pct = Math.round(((unmod.mean_pto_fires - aware.mean_pto_fires) / unmod.mean_pto_fires) * 100);
    document.getElementById("kpiPto").textContent = `-${pct}%`;
  }
}

function renderTraceChart() {
  destroyChart("traceChart");
  const labels = DATA.trace_preview.map((p) => `${p.time_s.toFixed(1)}s`);
  const rtts = DATA.trace_preview.map((p) => p.rtt_ms);
  const losses = DATA.trace_preview.map((p) => p.loss_pct);

  CHARTS.traceChart = new Chart(document.getElementById("traceChart"), {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "RTT (ms)",
          data: rtts,
          borderColor: COLORS.leo,
          backgroundColor: "rgba(56, 189, 248, 0.12)",
          yAxisID: "y",
          tension: 0.25,
          pointRadius: 0,
          fill: true,
        },
        {
          label: "Packet Loss (%)",
          data: losses,
          borderColor: COLORS.unmodified,
          yAxisID: "y1",
          tension: 0.25,
          pointRadius: 0,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: { legend: { labels: { color: "#e6edf7" } } },
      scales: {
        x: { ticks: { color: COLORS.muted, maxTicksLimit: 15 }, grid: { color: "#1c2847" } },
        y: {
          type: "linear",
          position: "left",
          title: { display: true, text: "RTT (ms)", color: COLORS.leo },
          ticks: { color: COLORS.muted },
          grid: { color: "#1c2847" },
        },
        y1: {
          type: "linear",
          position: "right",
          title: { display: true, text: "Loss (%)", color: COLORS.unmodified },
          ticks: { color: COLORS.muted },
          grid: { drawOnChartArea: false },
        },
      },
    },
  });
}

function populateSelectors() {
  const rq1Profiles = [...new Set(DATA.rq1_handover_sweep.map((s) => s.profile))];
  const rq1Sel = document.getElementById("rq1Profile");
  rq1Sel.innerHTML = rq1Profiles.map((p) => `<option value="${p}">${p}</option>`).join("");
  rq1Sel.value = rq1Profiles.includes("Kyber768+Dilithium3") ? "Kyber768+Dilithium3" : rq1Profiles[0];

  const rq34Profiles = [...new Set(DATA.rq3_rq4_mitigations.map((s) => s.profile))];
  const rq34Sel = document.getElementById("rq34Profile");
  rq34Sel.innerHTML = rq34Profiles.map((p) => `<option value="${p}">${p}</option>`).join("");
  rq34Sel.value = rq34Profiles.includes("Kyber768+Dilithium3") ? "Kyber768+Dilithium3" : rq34Profiles[0];

  const sbSel = document.getElementById("sbProfile");
  sbSel.innerHTML = Object.keys(DATA.profiles)
    .map((p) => `<option value="${p}">${p} (${DATA.profiles[p].category})</option>`)
    .join("");
  sbSel.value = "Kyber768+Dilithium3";

  const qSel = document.getElementById("sampleQlogSelect");
  qSel.innerHTML = DATA.sample_qlogs
    .map((q, idx) => `<option value="${idx}">${q.label}</option>`)
    .join("");
}

function renderRQ1Chart() {
  destroyChart("rq1Chart");
  const prof = document.getElementById("rq1Profile").value;
  const metric = document.getElementById("rq1Metric").value;
  const unmod = DATA.rq1_handover_sweep.find((s) => s.profile === prof && s.scheme === "unmodified");
  const aware = DATA.rq1_handover_sweep.find((s) => s.profile === prof && s.scheme === "handover_aware");
  if (!unmod || !aware) return;

  const labels = unmod.points.map((pt) => `${pt.offset_s >= 0 ? "+" : ""}${pt.offset_s}s`);
  const globalMax = Math.max(
    ...DATA.rq1_handover_sweep.flatMap((s) => s.points.map((pt) => pt[metric] || 0))
  );
  const yMax = metric === "mean_pto_fires" ? Math.ceil(globalMax * 10) / 10 + 0.2 : Math.ceil(globalMax / 100) * 100 + 100;

  CHARTS.rq1Chart = new Chart(document.getElementById("rq1Chart"), {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Unmodified QUIC",
          data: unmod.points.map((pt) => pt[metric]),
          borderColor: COLORS.unmodified,
          backgroundColor: "rgba(248, 113, 113, 0.15)",
          tension: 0.25,
          fill: true,
        },
        {
          label: "Handover-Aware Scheme",
          data: aware.points.map((pt) => pt[metric]),
          borderColor: COLORS.handover_aware,
          backgroundColor: "rgba(52, 211, 153, 0.15)",
          tension: 0.25,
          fill: true,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { labels: { color: "#e6edf7" } } },
      scales: {
        x: {
          title: { display: true, text: "Handshake Start Offset vs. 12.0s Handover", color: COLORS.muted },
          ticks: { color: COLORS.muted },
          grid: { color: "#1c2847" },
        },
        y: { min: 0, max: yMax, ticks: { color: COLORS.muted }, grid: { color: "#1c2847" } },
      },
    },
  });
}

function renderRQ2() {
  destroyChart("rq2Chart");
  const profiles = [...new Set(DATA.rq2_algorithm_matrix.map((r) => r.profile))];
  const leoData = profiles.map(
    (p) => DATA.rq2_algorithm_matrix.find((r) => r.profile === p && r.environment === "LEO_Starlink")?.mean_ms ?? 0
  );
  const terrData = profiles.map(
    (p) => DATA.rq2_algorithm_matrix.find((r) => r.profile === p && r.environment === "Terrestrial")?.mean_ms ?? 0
  );

  CHARTS.rq2Chart = new Chart(document.getElementById("rq2Chart"), {
    type: "bar",
    data: {
      labels: profiles,
      datasets: [
        { label: "LEO Starlink (ms)", data: leoData, backgroundColor: COLORS.leo },
        { label: "Terrestrial (ms)", data: terrData, backgroundColor: COLORS.terrestrial },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { labels: { color: "#e6edf7" } } },
      scales: {
        x: { ticks: { color: COLORS.muted }, grid: { color: "#1c2847" } },
        y: { title: { display: true, text: "Mean Handshake Time (ms)", color: COLORS.muted }, ticks: { color: COLORS.muted }, grid: { color: "#1c2847" } },
      },
    },
  });

  const tbody = document.querySelector("#rq2Table tbody");
  tbody.innerHTML = DATA.rq2_algorithm_matrix
    .map((r) => {
      const blocked = r.amplification_blocked_pct > 0;
      return `<tr>
        <td class="mono">${r.profile}</td>
        <td>${r.category}</td>
        <td>${r.environment}</td>
        <td class="mono">${r.client_packets} / ${r.server_packets}</td>
        <td class="mono">${r.server_total_bytes.toLocaleString()} B</td>
        <td><span class="pill ${blocked ? "bad" : "ok"}">${blocked ? "BLOCKED" : "OK"}</span></td>
        <td class="mono">${r.mean_ms}</td>
        <td class="mono">${r.p95_ms}</td>
        <td class="mono">${r.mean_pto_fires}</td>
      </tr>`;
    })
    .join("");
}

function renderRQ34() {
  destroyChart("rq34LatencyChart");
  destroyChart("rq34PtoChart");
  const prof = document.getElementById("rq34Profile").value;
  const sla = Number(document.getElementById("slaSlider").value);
  document.getElementById("slaVal").textContent = sla;

  const rows = DATA.rq3_rq4_mitigations.filter((r) => r.profile === prof);
  const labels = rows.map((r) => r.mitigation_label);

  CHARTS.rq34LatencyChart = new Chart(document.getElementById("rq34LatencyChart"), {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Active Handshake (ms)",
          data: rows.map((r) => Math.max(0, +(r.mean_ms - r.mean_defer_ms).toFixed(1))),
          backgroundColor: COLORS.leo,
        },
        {
          label: "Scheduled Defer Wait (ms)",
          data: rows.map((r) => r.mean_defer_ms),
          backgroundColor: COLORS.warn,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { labels: { color: "#e6edf7" } } },
      scales: {
        x: { stacked: true, ticks: { color: COLORS.muted }, grid: { color: "#1c2847" } },
        y: { stacked: true, title: { display: true, text: "Latency Breakdown (ms)", color: COLORS.muted }, ticks: { color: COLORS.muted }, grid: { color: "#1c2847" } },
      },
    },
  });

  CHARTS.rq34PtoChart = new Chart(document.getElementById("rq34PtoChart"), {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Mean PTO Fires",
          data: rows.map((r) => r.mean_pto_fires),
          backgroundColor: rows.map((r) => (r.mean_ms > sla ? COLORS.unmodified : COLORS.handover_aware)),
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: "#e6edf7" } },
        title: { display: true, text: `Red = Mean Total Time > ${sla}ms SLA`, color: COLORS.muted },
      },
      scales: {
        x: { ticks: { color: COLORS.muted }, grid: { color: "#1c2847" } },
        y: { title: { display: true, text: "Probe Timeouts (PTO)", color: COLORS.muted }, ticks: { color: COLORS.muted }, grid: { color: "#1c2847" } },
      },
    },
  });
}

function sampleTrace(tSec) {
  const arr = DATA.trace_preview;
  const mod = ((tSec % 60) + 60) % 60;
  let best = arr[0];
  let bestDiff = Infinity;
  for (const pt of arr) {
    const d = Math.abs(pt.time_s - mod);
    if (d < bestDiff) {
      bestDiff = d;
      best = pt;
    }
  }
  return best;
}

function runBrowserSandbox() {
  const profName = document.getElementById("sbProfile").value;
  const startS = parseFloat(document.getElementById("sbStart").value) || 0;
  const scheme = document.getElementById("sbScheme").value;
  const mitigation = document.getElementById("sbMitigation").value;
  const useRetry = document.getElementById("sbRetry").value === "true";

  const prof = DATA.profiles[profName];
  const certScale = mitigation === "compress" ? 0.65 : mitigation === "mtc" ? 0.35 : 1.0;
  const is0Rtt = mitigation === "0rtt";

  const marks = [12, 27, 42, 57];
  let deferMs = 0;
  const events = [];

  const link0 = sampleTrace(startS);
  let ptoMs = Math.max(250, link0.rtt_ms * 3.0);

  if (scheme === "handover_aware") {
    ptoMs = Math.max(120, Math.min(260, link0.rtt_ms * 2.2));
    const tMod = startS % 60;
    for (const m of marks) {
      const delta = m - tMod;
      if (delta >= -0.45 && delta <= 0.35) {
        deferMs = Math.round((delta + 0.5) * 1000);
        events.push({
          t: 0,
          name: "scheme:defer_initiation",
          data: `Deferred ${deferMs}ms to clear ${m}s Starlink handover window`,
        });
        break;
      }
    }
  }

  let curT = startS + deferMs / 1000;
  let elapsed = 0;
  let rtts = 0;
  let ptos = 0;

  const clientPkts = is0Rtt ? 2 : prof.client_packets;
  const serverBytes = is0Rtt ? 1800 : prof.server_flight_bytes + Math.round(prof.cert_chain_bytes * certScale);
  const serverPkts = Math.max(1, Math.ceil(serverBytes / 1200));
  const ampLimit = 3 * Math.max(1200, clientPkts * 1200);
  const ampBlocked = serverBytes > ampLimit;

  if (useRetry) {
    rtts += 1;
    const l = sampleTrace(curT);
    elapsed += l.rtt_ms;
    curT += l.rtt_ms / 1000;
    events.push({ t: elapsed, name: "transport:retry_completed", data: `+1 RTT address validation (${l.rtt_ms.toFixed(1)}ms)` });
  }

  const flights = 1 + (ampBlocked && !useRetry ? 1 : 0) + (is0Rtt ? 0 : 1);
  let totalPkts = 0;
  for (let f = 0; f < flights; f++) {
    rtts += 1;
    const l = sampleTrace(curT);
    const pkts = f === 0 ? clientPkts : Math.ceil(serverPkts / Math.max(1, flights - 1));
    totalPkts += pkts;
    const expectedLoss = (l.loss_pct / 100) * pkts;
    elapsed += l.rtt_ms + (f === 0 ? prof.crypto_compute_ms : 0);
    curT += l.rtt_ms / 1000;
    events.push({
      t: elapsed,
      name: "transport:flight_sent",
      data: `Flight ${f + 1}: ${pkts} pkts, link RTT=${l.rtt_ms.toFixed(1)}ms, loss=${l.loss_pct.toFixed(1)}%`,
    });
    // Trigger PTO if burst loss probability hits at least one packet in the flight
    const pAnyLost = 1 - Math.pow(1 - Math.min(0.95, l.loss_pct / 100), pkts);
    if (pAnyLost >= 0.35 || expectedLoss >= 0.35) {
      const rounds = pkts > 20 ? 2 : 1;
      for (let r = 0; r < rounds; r++) {
        ptos += 1;
        const stepPto = ptoMs * (scheme === "handover_aware" ? Math.pow(1.25, r) : Math.pow(2, r));
        elapsed += stepPto + l.rtt_ms;
        curT += (stepPto + l.rtt_ms) / 1000;
        events.push({
          t: elapsed,
          name: "recovery:pto_retransmit",
          data: `PTO #${ptos} fired (${stepPto.toFixed(0)}ms) - ${Math.round(pAnyLost * 100)}% flight loss risk`,
        });
      }
    }
  }

  const totalMs = elapsed + deferMs;
  document.getElementById("sbMetrics").innerHTML = `
    <div class="kpi-card"><div class="kpi-label">Total Time</div><div class="kpi-value">${totalMs.toFixed(1)} ms</div><div class="kpi-sub">Active: ${elapsed.toFixed(1)} ms</div></div>
    <div class="kpi-card"><div class="kpi-label">Total RTTs</div><div class="kpi-value">${rtts}</div><div class="kpi-sub">Packets: ${totalPkts}</div></div>
    <div class="kpi-card"><div class="kpi-label">PTO Fires</div><div class="kpi-value">${ptos}</div><div class="kpi-sub">PTO base: ${ptoMs.toFixed(0)} ms</div></div>
    <div class="kpi-card"><div class="kpi-label">3&times; Amp Limit</div><div class="kpi-value">${ampBlocked ? "HIT" : "OK"}</div><div class="kpi-sub">${serverBytes} / ${ampLimit} B</div></div>
  `;

  const pct = Math.min(100, Math.round((serverBytes / ampLimit) * 100));
  const bar = document.getElementById("sbAmpBar");
  bar.style.width = `${pct}%`;
  bar.classList.toggle("over", ampBlocked);
  document.getElementById("sbAmpText").textContent = `${serverBytes.toLocaleString()} B / ${ampLimit.toLocaleString()} B (${pct}%)`;

  document.getElementById("sbQlog").innerHTML = events
    .map((e) => `<div class="qlog-item"><span class="qlog-time">${e.t.toFixed(1)} ms</span><span class="qlog-name">${e.name}</span><span class="qlog-data">${e.data}</span></div>`)
    .join("");
}

function renderSampleQlog() {
  const idx = Number(document.getElementById("sampleQlogSelect").value) || 0;
  const item = DATA.sample_qlogs[idx];
  if (!item) return;
  const evs = item.result.qlog_events || [];
  document.getElementById("sampleQlogBox").innerHTML = evs
    .map(
      (e) => `<div class="qlog-item"><span class="qlog-time">${e.time_ms} ms</span><span class="qlog-name">${e.name}</span><span class="qlog-data">${JSON.stringify(e.data)}</span></div>`
    )
    .join("");
}

function initDashboard(data) {
  DATA = data;
  populateSelectors();
  renderKPIs();
  renderTraceChart();
  renderRQ1Chart();
  renderRQ2();
  renderRQ34();
  runBrowserSandbox();
  renderSampleQlog();
}

document.addEventListener("DOMContentLoaded", async () => {
  setupTabs();
  document.getElementById("rq1Profile").addEventListener("change", renderRQ1Chart);
  document.getElementById("rq1Metric").addEventListener("change", renderRQ1Chart);
  document.getElementById("rq34Profile").addEventListener("change", renderRQ34);
  document.getElementById("slaSlider").addEventListener("input", renderRQ34);
  document.getElementById("sbRunBtn").addEventListener("click", runBrowserSandbox);
  ["sbProfile", "sbStart", "sbScheme", "sbMitigation", "sbRetry"].forEach((id) => {
    document.getElementById(id).addEventListener("change", runBrowserSandbox);
    document.getElementById(id).addEventListener("input", runBrowserSandbox);
  });
  document.getElementById("sampleQlogSelect").addEventListener("change", renderSampleQlog);

  document.getElementById("jsonUpload").addEventListener("change", async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const text = await file.text();
    initDashboard(JSON.parse(text));
  });

  const resp = await fetch("data/benchmark_results.json");
  const json = await resp.json();
  initDashboard(json);
});
