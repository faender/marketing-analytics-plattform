const API = "/api";

const el = (id) => document.getElementById(id);

function formatCompact(value, { currency = false, percent = false } = {}) {
  if (value === null || value === undefined) return "—";
  if (percent) return (value * 100).toFixed(2) + "%";

  const abs = Math.abs(value);
  let str;
  if (abs >= 1_000_000) str = (value / 1_000_000).toFixed(1) + "M";
  else if (abs >= 1_000) str = (value / 1_000).toFixed(1) + "K";
  else str = Number.isInteger(value) ? value.toLocaleString() : value.toFixed(2);

  return currency ? "$" + str : str;
}

async function fetchJSON(url) {
  const response = await fetch(url);
  const data = await response.json();
  if (!response.ok) {
    const message = data.detail || JSON.stringify(data);
    throw new Error(message);
  }
  return data;
}

function currentFilters() {
  const params = new URLSearchParams();
  const dateFrom = el("filter-date-from").value;
  const dateTo = el("filter-date-to").value;
  const channel = el("filter-channel").value;
  if (dateFrom) params.set("date_from", dateFrom);
  if (dateTo) params.set("date_to", dateTo);
  if (channel) params.set("channel", channel);
  return params;
}

function setText(id, text) {
  el(id).textContent = text;
}

function renderKPIs(summary) {
  const t = summary.totals;
  const a = summary.averages;
  setText("kpi-impressions", formatCompact(t.impressions));
  setText("kpi-clicks", formatCompact(t.clicks));
  setText("kpi-cost", formatCompact(t.cost, { currency: true }));
  setText("kpi-conversions", formatCompact(t.conversions));
  setText("kpi-revenue", formatCompact(t.revenue, { currency: true }));
  setText("kpi-ctr", a.ctr === null ? "—" : formatCompact(a.ctr, { percent: true }));
  setText("kpi-cpc", a.cpc === null ? "—" : formatCompact(a.cpc, { currency: true }));
  setText("kpi-cpa", a.cpa === null ? "—" : formatCompact(a.cpa, { currency: true }));
  setText("kpi-roas", a.roas === null ? "—" : formatCompact(a.roas) + "x");

  el("empty-state").hidden = summary.row_count > 0;
  el("kpi-grid").hidden = summary.row_count === 0;
}

let trendChart = null;
let latestTrends = [];

function seriesColor() {
  return getComputedStyle(document.documentElement).getPropertyValue("--series-1").trim();
}

function fillColor() {
  return getComputedStyle(document.documentElement).getPropertyValue("--series-1-fill").trim();
}

function gridColor() {
  return getComputedStyle(document.documentElement).getPropertyValue("--gridline").trim();
}

function textMuted() {
  return getComputedStyle(document.documentElement).getPropertyValue("--text-muted").trim();
}

function renderTrendChart(trends, metric) {
  latestTrends = trends;
  const ctx = el("trend-canvas").getContext("2d");
  const labels = trends.map((p) => p.period);
  const values = trends.map((p) => p.value);

  if (trendChart) {
    trendChart.destroy();
  }
  trendChart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: metric,
          data: values,
          borderColor: seriesColor(),
          backgroundColor: fillColor(),
          borderWidth: 2,
          pointRadius: 4,
          pointBackgroundColor: seriesColor(),
          pointBorderColor: getComputedStyle(document.documentElement)
            .getPropertyValue("--surface-1")
            .trim(),
          pointBorderWidth: 2,
          fill: true,
          tension: 0.15,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          mode: "index",
          intersect: false,
          callbacks: {
            label: (item) => {
              const isCurrency = ["cost", "revenue"].includes(metric);
              return formatCompact(item.parsed.y, { currency: isCurrency });
            },
          },
        },
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: textMuted(), maxRotation: 0 },
        },
        y: {
          beginAtZero: true,
          grid: { color: gridColor() },
          ticks: { color: textMuted() },
        },
      },
    },
  });
}

function renderTrendTable(trends) {
  const tbody = el("trend-table-body");
  tbody.innerHTML = "";
  for (const point of trends) {
    const row = document.createElement("tr");
    const periodCell = document.createElement("td");
    periodCell.textContent = point.period;
    const valueCell = document.createElement("td");
    valueCell.textContent = point.value;
    row.append(periodCell, valueCell);
    tbody.append(row);
  }
}

function renderTopCampaigns(campaigns) {
  const tbody = el("campaigns-table-body");
  tbody.innerHTML = "";
  for (const c of campaigns) {
    const row = document.createElement("tr");
    for (const value of [
      c.campaign_name,
      c.channel,
      formatCompact(c.impressions),
      formatCompact(c.clicks),
      formatCompact(c.cost, { currency: true }),
      formatCompact(c.conversions),
      formatCompact(c.revenue, { currency: true }),
    ]) {
      const cell = document.createElement("td");
      cell.textContent = value;
      row.append(cell);
    }
    tbody.append(row);
  }
  el("campaigns-empty").hidden = campaigns.length > 0;
}

function renderDataSources(items) {
  const tbody = el("datasources-table-body");
  tbody.innerHTML = "";
  for (const d of items) {
    const row = document.createElement("tr");

    const nameCell = document.createElement("td");
    nameCell.textContent = d.file_name;

    const statusCell = document.createElement("td");
    const badge = document.createElement("span");
    badge.className = `badge ${d.status}`;
    badge.textContent = d.status;
    statusCell.append(badge);

    const rowsCell = document.createElement("td");
    rowsCell.textContent = d.row_count;

    const uploadedCell = document.createElement("td");
    uploadedCell.textContent = new Date(d.uploaded_at).toLocaleString();

    row.append(nameCell, statusCell, rowsCell, uploadedCell);
    tbody.append(row);
  }
}

async function populateChannelFilter() {
  try {
    const data = await fetchJSON(`${API}/metrics/top-campaigns/?metric=impressions&limit=50`);
    const channels = [...new Set(data.top_campaigns.map((c) => c.channel))].sort();
    const select = el("filter-channel");
    const current = select.value;
    select.innerHTML = '<option value="">All channels</option>';
    for (const channel of channels) {
      const option = document.createElement("option");
      option.value = channel;
      option.textContent = channel;
      select.append(option);
    }
    select.value = current;
  } catch (err) {
    // Non-fatal: the filter just stays empty if this fails.
    console.error("Could not load channel list", err);
  }
}

async function loadDashboard() {
  const params = currentFilters();
  const metric = el("filter-metric").value;

  const trendParams = new URLSearchParams(params);
  trendParams.set("metric", metric);
  trendParams.set("granularity", el("filter-granularity").value);

  const topParams = new URLSearchParams(params);
  topParams.set("metric", metric);
  topParams.set("limit", "5");

  try {
    const [summary, trends, topCampaigns, dataSources] = await Promise.all([
      fetchJSON(`${API}/metrics/summary/?${params.toString()}`),
      fetchJSON(`${API}/metrics/trends/?${trendParams.toString()}`),
      fetchJSON(`${API}/metrics/top-campaigns/?${topParams.toString()}`),
      fetchJSON(`${API}/datasources/`),
    ]);
    renderKPIs(summary);
    renderTrendChart(trends.trends, metric);
    renderTrendTable(trends.trends);
    renderTopCampaigns(topCampaigns.top_campaigns);
    renderDataSources(dataSources.results ?? dataSources);
  } catch (err) {
    console.error(err);
  }
}

function initFilters() {
  el("filters-form").addEventListener("submit", (event) => {
    event.preventDefault();
    loadDashboard();
  });
  el("filters-reset").addEventListener("click", () => {
    el("filter-date-from").value = "";
    el("filter-date-to").value = "";
    el("filter-channel").value = "";
    el("filter-metric").value = "revenue";
    el("filter-granularity").value = "week";
    loadDashboard();
  });
}

function initTableToggle() {
  const button = el("trend-table-toggle");
  button.addEventListener("click", () => {
    const showingTable = !el("trend-table-wrap").hidden;
    el("trend-table-wrap").hidden = showingTable;
    el("trend-canvas").hidden = !showingTable;
    button.textContent = showingTable ? "View as table" : "View as chart";
  });
}

function initUploadForm() {
  const form = el("upload-form");
  const statusLine = el("upload-status");

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fileInput = el("upload-file");
    if (!fileInput.files.length) return;

    const formData = new FormData();
    formData.append("file", fileInput.files[0]);

    const submitButton = form.querySelector("button[type=submit]");
    submitButton.disabled = true;
    statusLine.textContent = "Uploading…";
    statusLine.className = "status-line";

    try {
      const response = await fetch(`${API}/upload/`, { method: "POST", body: formData });
      const data = await response.json();

      if (response.ok && data.status === "processed") {
        statusLine.textContent = `Uploaded ${data.file_name}: ${data.row_count} rows processed.`;
        statusLine.className = "status-line success";
        form.reset();
        await populateChannelFilter();
        await loadDashboard();
      } else {
        statusLine.textContent = `Upload failed: ${data.error_message || "unknown error"}`;
        statusLine.className = "status-line error";
      }
    } catch (err) {
      statusLine.textContent = `Upload failed: ${err.message}`;
      statusLine.className = "status-line error";
    } finally {
      submitButton.disabled = false;
    }
  });
}

function initAskForm() {
  const form = el("ask-form");
  const answerBox = el("ask-answer");

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const input = el("ask-question");
    const question = input.value.trim();
    if (!question) return;

    const submitButton = form.querySelector("button[type=submit]");
    submitButton.disabled = true;
    answerBox.hidden = false;
    answerBox.querySelector(".answer-text").textContent = "Thinking…";
    answerBox.querySelector(".tool-calls").textContent = "";

    try {
      const response = await fetch(`${API}/ask/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      const data = await response.json();

      if (response.ok) {
        answerBox.querySelector(".answer-text").textContent = data.answer;
        if (data.tool_calls && data.tool_calls.length) {
          const toolNames = data.tool_calls.map((t) => t.tool).join(", ");
          answerBox.querySelector(".tool-calls").textContent = `Used: ${toolNames}`;
        }
      } else {
        answerBox.querySelector(".answer-text").textContent =
          data.detail || "Something went wrong answering that.";
      }
    } catch (err) {
      answerBox.querySelector(".answer-text").textContent = `Error: ${err.message}`;
    } finally {
      submitButton.disabled = false;
    }
  });
}

document.addEventListener("DOMContentLoaded", async () => {
  initFilters();
  initTableToggle();
  initUploadForm();
  initAskForm();
  await populateChannelFilter();
  await loadDashboard();
});
