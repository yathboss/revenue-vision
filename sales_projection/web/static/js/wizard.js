let chartInstance = null;

const PREV_KEY = "sales_projection_prev_forecast_v1";

function money(n){
  if(n === null || n === undefined || Number.isNaN(n)) return "-";
  return new Intl.NumberFormat("en-IN", {maximumFractionDigits: 0}).format(n);
}

function pct(n){
  if(n === null || n === undefined || Number.isNaN(n)) return "-";
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(1)}%`;
}

function cssVar(name, fallback){
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || fallback;
}

function getScenario(){
  const btn = document.querySelector(".scenario-btn.active");
  return btn ? btn.getAttribute("data-scenario") : "base";
}

function setScenario(s){
  document.querySelectorAll(".scenario-btn").forEach(b => {
    b.classList.toggle("active", b.getAttribute("data-scenario") === s);
  });
}

function setStep(step){
  document.querySelectorAll(".step-pill").forEach(p => {
    p.classList.toggle("active", p.getAttribute("data-step") === String(step));
  });

  const s1 = document.getElementById("step1");
  const s2 = document.getElementById("step2");
  const s3 = document.getElementById("step3");

  const map = {1:s1, 2:s2, 3:s3};
  [s1,s2,s3].forEach(el => {
    el.classList.add("hidden");
    el.style.opacity = "0";
    el.style.transform = "translateY(6px)";
  });

  const target = map[step];
  target.classList.remove("hidden");

  requestAnimationFrame(() => {
    target.style.transition = "opacity 220ms ease, transform 220ms ease";
    target.style.opacity = "1";
    target.style.transform = "translateY(0)";
    setTimeout(() => { target.style.transition = ""; }, 260);
  });
}

function buildParams(){
  const freq = document.querySelector("input[name='freq']:checked").value;
  const category = document.getElementById("category").value;
  const region = document.getElementById("region").value;
  const segment = document.getElementById("segment").value;
  const mode = document.getElementById("modeToggle").checked ? "advanced" : "fast";
  const scenario = getScenario();

  return {freq, category, region, segment, mode, scenario};
}

async function runForecast(){
  const loading = document.getElementById("loading");
  const errorBox = document.getElementById("errorBox");

  loading.classList.remove("hidden");
  const loadingTitle = loading.querySelector(".loading-title");
  const loadingSub = loading.querySelector(".muted");
  if(loadingTitle) loadingTitle.textContent = "Forecasting...";
  if(loadingSub) loadingSub.textContent = "Crunching trends, seasonality, and insights";

  errorBox.classList.add("hidden");
  errorBox.textContent = "";

  const paramsObj = buildParams();
  const params = new URLSearchParams(paramsObj);

  try{
    const res = await fetch(`/forecast?${params.toString()}`);
    const data = await res.json();
    if(!res.ok){
      throw new Error(data.message || "Something went wrong");
    }

    setStep(3);
    requestAnimationFrame(() => renderResults(data, params));
  }catch(err){
    errorBox.textContent = err.message;
    errorBox.classList.remove("hidden");
  }finally{
    loading.classList.add("hidden");
  }
}

function getPrevious(){
  try{
    const raw = localStorage.getItem(PREV_KEY);
    return raw ? JSON.parse(raw) : null;
  }catch{
    return null;
  }
}

function savePrevious(current){
  try{
    localStorage.setItem(PREV_KEY, JSON.stringify({
      at: new Date().toISOString(),
      freq: current.freq,
      filters: current.filters,
      scenario: current.scenario,
      chart: current.chart,
      kpis: current.kpis
    }));
  }catch{}
}

function computeNext3Total(payload){
  const rows = (payload.table || []).slice(0, 3);
  return rows.reduce((s, r) => s + (r.predicted_sales || 0), 0);
}

function renderResults(payload, params){
  const f = payload.filters;

  document.getElementById("subtitle").textContent =
    `Freq: ${payload.freq} / Category: ${f.category} / Region: ${f.region} / Segment: ${f.segment}`;

  const tags = [
    "Dataset: Superstore (Kaggle)",
    `Scenario: ${payload.scenario || "base"}`,
    `Mode: ${payload.mode || params.get("mode")}`,
  ];
  document.getElementById("snapshotTags").textContent = tags.join(" / ");

  const conf = payload.confidence || {label:"-", note:""};
  const badge = document.getElementById("confidenceBadge");
  badge.textContent = conf.label ? `Confidence: ${conf.label}` : "Confidence: -";
  badge.title = conf.note || "";

  document.getElementById("kpiLast").textContent = money(payload.kpis.last_periods_actual);
  document.getElementById("kpiNext").textContent = money(payload.kpis.next_periods_forecast);
  document.getElementById("kpiGrowth").textContent = pct(payload.kpis.growth_pct);

  const modeText = (payload.mode || params.get("mode")) === "advanced" ? "Advanced" : "Fast";
  const cacheText = payload.cache_hit ? "Cache: Hit" : "Cache: Miss";
  const sourceText = payload.source ? `Source: ${payload.source}` : "";
  const meta = `Mode: ${modeText} / Scenario: ${payload.scenario || params.get("scenario") || "base"} / ${cacheText}${sourceText ? " / " + sourceText : ""}`;
  document.getElementById("metaLine").textContent = meta;

  const best = payload.insights.best_predicted;
  document.getElementById("bestMonth").textContent =
    best.best_date ? `${best.best_date} (Rs ${money(best.best_value)})` : "-";

  const seas = payload.insights.seasonality;
  const topNames = (seas.top_month_names || []).join(", ");
  document.getElementById("seasonality").textContent =
    topNames ? `Top months historically: ${topNames}. ${seas.default_note}` : seas.default_note;

  const anom = payload.insights.anomaly;
  document.getElementById("anomaly").textContent =
    anom.is_anomaly ? anom.message : "No unusual spike/drop detected.";

  const recs = document.getElementById("recs");
  recs.innerHTML = "";
  (payload.insights.recommendations || []).forEach(t => {
    const li = document.createElement("li");
    li.textContent = t;
    recs.appendChild(li);
  });

  const actualMap = new Map(payload.chart.actual.map(p => [p.date, p.value]));
  const forecastMap = new Map(payload.chart.forecast.map(p => [p.date, p.value]));
  const allDates = Array.from(new Set([...actualMap.keys(), ...forecastMap.keys()])).sort();

  const actualSeries = allDates.map(d => actualMap.has(d) ? actualMap.get(d) : null);
  const forecastSeries = allDates.map(d => forecastMap.has(d) ? forecastMap.get(d) : null);

  const prev = getPrevious();
  const compareBtn = document.getElementById("compareBtn");
  const compareDelta = document.getElementById("compareDelta");

  let prevSeries = null;
  let showCompare = false;

  if(prev && prev.chart && prev.chart.forecast && Array.isArray(prev.chart.forecast)){
    const prevMap = new Map(prev.chart.forecast.map(p => [p.date, p.value]));
    prevSeries = allDates.map(d => prevMap.has(d) ? prevMap.get(d) : null);
    showCompare = true;
  }

  compareBtn.style.display = showCompare ? "inline-flex" : "none";
  compareDelta.textContent = "";

  const colorMuted = cssVar("--muted", "#8d958f");
  const colorActual = cssVar("--accent", "#d6e864");
  const colorForecast = cssVar("--primary", "#2fffa8");
  const colorPrev = cssVar("--primary-3", "#6ef7d3");
  const gridColor = "rgba(255,255,255,0.07)";

  const ctx = document.getElementById("chart").getContext("2d");
  if(chartInstance) chartInstance.destroy();

  const datasetsBase = [
    {
      label: "Actual",
      data: actualSeries,
      borderWidth: 2,
      tension: 0.22,
      borderColor: colorActual,
      pointRadius: 0,
    },
    {
      label: "Forecast",
      data: forecastSeries,
      borderWidth: 2,
      tension: 0.22,
      borderDash: [6, 4],
      borderColor: colorForecast,
      pointRadius: 0,
    },
  ];

  chartInstance = new Chart(ctx, {
    type: "line",
    data: { labels: allDates, datasets: datasetsBase },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {mode: "index", intersect: false},
      plugins: {
        legend: { display: true, labels: {color: colorMuted} },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const v = ctx.parsed.y;
              if(v === null || v === undefined) return `${ctx.dataset.label}: -`;
              return `${ctx.dataset.label}: Rs ${money(v)}`;
            }
          }
        }
      },
      scales: {
        x: { ticks: { color: colorMuted, maxTicksLimit: 10, autoSkip: true }, grid: {color: gridColor} },
        y: { ticks: { color: colorMuted, callback: (v) => money(v) }, grid: {color: gridColor} }
      }
    }
  });

  compareBtn.onclick = () => {
    if(!prevSeries) return;

    const already = chartInstance.data.datasets.some(ds => ds.label === "Previous Forecast");
    if(already){
      chartInstance.data.datasets = datasetsBase.slice();
      chartInstance.update();
      compareDelta.textContent = "";
      return;
    }

    chartInstance.data.datasets = [
      ...datasetsBase,
      {
        label: "Previous Forecast",
        data: prevSeries,
        borderWidth: 2,
        tension: 0.22,
        borderDash: [2, 6],
        borderColor: colorPrev,
        pointRadius: 0,
      }
    ];
    chartInstance.update();

    const prevPayload = {
      table: (prev.chart.forecast || []).slice(0, 3).map(p => ({predicted_sales: p.value}))
    };
    const prevTotal = prevPayload.table.reduce((s, r) => s + (r.predicted_sales || 0), 0);
    const curTotal = computeNext3Total(payload);
    const diff = curTotal - prevTotal;
    const diffPct = prevTotal ? (diff / prevTotal) * 100 : null;

    compareDelta.textContent = (diffPct === null)
      ? `Change in next 3 forecast total: Rs ${money(diff)}`
      : `Change in next 3 forecast total: Rs ${money(diff)} (${pct(diffPct)})`;
  };

  const tbody = document.querySelector("#forecastTable tbody");
  tbody.innerHTML = "";
  (payload.table || []).forEach(r => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${r.date}</td><td>${money(r.predicted_sales)}</td>`;
    tbody.appendChild(tr);
  });

  const ybody = document.querySelector("#yearTable tbody");
  ybody.innerHTML = "";
  (payload.year_table || []).forEach(r => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${r.year}</td><td>${money(r.actual_sales)}</td><td>${money(r.forecast_sales)}</td><td>${money(r.total)}</td>`;
    ybody.appendChild(tr);
  });

  document.getElementById("downloadBtn").setAttribute("href", `/download?${params.toString()}`);
  document.getElementById("pdfBtn").setAttribute("href", `/report.pdf?${params.toString()}`);

  savePrevious(payload);
}

document.addEventListener("DOMContentLoaded", () => {
  setStep(1);

  document.querySelectorAll(".scenario-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      setScenario(btn.getAttribute("data-scenario"));
    });
  });

  document.getElementById("toStep2").addEventListener("click", () => setStep(2));
  document.getElementById("backTo1").addEventListener("click", () => setStep(1));
  document.getElementById("backTo2").addEventListener("click", () => setStep(2));
  document.getElementById("runForecast").addEventListener("click", runForecast);
});
