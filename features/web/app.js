const fmtDate = (iso) =>
  new Date(iso + "T00:00:00").toLocaleDateString(undefined, {
    year: "numeric", month: "short", day: "numeric",
  });

async function boot() {
  const res = await fetch("data.json", { cache: "no-store" });
  if (!res.ok) {
    document.body.insertAdjacentHTML("beforeend",
      `<pre style="color:#b00;padding:24px">Could not load data.json. Run: python -m features.forecasting.demo</pre>`);
    return;
  }
  const data = await res.json();
  renderCycle(data);
  renderHormone(data);
}

function renderCycle(data) {
  const c = data.cycle;
  document.getElementById("as-of").textContent = data.as_of;
  document.getElementById("next-start").textContent = fmtDate(c.next_start);
  document.getElementById("window").textContent =
    `window ${fmtDate(c.low)} – ${fmtDate(c.high)}`;
  document.getElementById("conf-cycle").textContent =
    `confidence ${c.confidence}`;
  document.getElementById("n-cycles").textContent =
    `${c.based_on_cycles} cycles`;
}

function renderHormone(data) {
  const h = data.hormones[0];
  if (!h) return;

  document.getElementById("hormone-name").textContent =
    `${h.name} (${h.unit})`;
  document.getElementById("hormone-method").textContent = h.method;
  document.getElementById("hormone-conf").textContent =
    `confidence ${h.confidence}`;

  const projLabels = h.points.map(([d]) => fmtDate(d));
  const projValues = h.points.map(([, v]) => v);
  const bandLow   = h.band_low.map(([, v]) => v);
  const bandHigh  = h.band_high.map(([, v]) => v);

  new Chart(document.getElementById("hormone-chart"), {
    type: "line",
    data: {
      labels: projLabels,
      datasets: [
        {
          label: `${h.name} projection`,
          data: projValues,
          borderColor: "#7a6cff",
          backgroundColor: "rgba(122,108,255,.15)",
          borderWidth: 2,
          tension: 0.25,
          pointRadius: 2,
          fill: false,
        },
        {
          label: "upper band",
          data: bandHigh,
          borderColor: "transparent",
          backgroundColor: "rgba(122,108,255,.10)",
          pointRadius: 0,
          fill: "+1",
        },
        {
          label: "lower band",
          data: bandLow,
          borderColor: "transparent",
          backgroundColor: "rgba(122,108,255,.10)",
          pointRadius: 0,
          fill: false,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { intersect: false, mode: "index" },
      },
      scales: {
        x: {
          grid: { color: "rgba(0,0,0,.04)" },
          ticks: { color: "#6f6a61", maxRotation: 0, autoSkipPadding: 20 },
        },
        y: {
          grid: { color: "rgba(0,0,0,.04)" },
          ticks: { color: "#6f6a61" },
        },
      },
    },
  });
}

boot();