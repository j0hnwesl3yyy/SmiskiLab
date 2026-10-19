/* Renders the findings sections from window.SMISKI (precomputed by the notebooks; the site is fully static). */
(function () {
  "use strict";
  const D = window.SMISKI, C = window.Charts;
  const $ = (id) => document.getElementById(id);
  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
  const fresh = (id) => { const w = $(id); w.innerHTML = ""; const h = el("div"); w.appendChild(h); return h; };
  const pc = (v, d = 0) => (v * 100).toFixed(d) + "%";
  const sgn = (v, d = 0) => (v >= 0 ? "+" : "−") + Math.abs(v * 100).toFixed(d) + "%";
  const renderers = [];

  function list(id, items) { const ul = $(id); ul.innerHTML = ""; items.forEach((t) => ul.appendChild(el("li", "", t))); }

  /* ---------- provenance banner ---------- */
  function banner() {
    const prov = D.catalog.provenance, sim = Object.keys(prov).filter((k) => prov[k] === "simulated"), real = Object.keys(prov).filter((k) => prov[k] !== "simulated");
    const b = $("provenance");
    if (sim.length) {
      b.innerHTML = `<b>Real</b> (scraped): <b>${real.join(", ") || "none"}</b>. <b>Simulated</b>: <b>${sim.join(", ")}</b>. ` +
        `Series, figure names and search interest come from smiski.com and Google Trends. Resale prices and Reddit text have no accessible source yet, so charts that depend on them describe a simulation, not the market. See <a href="#method">Data &amp; method</a>.`;
    } else { b.innerHTML = "<b>Data:</b> built from scraped / user-supplied sources. See <a href='#method'>Data &amp; method</a>."; }
  }

  /* ---------- premium ---------- */
  function premium() {
    const P = D.premium, best = P.best_model, imp = P.improvement_vs_rarity_baseline[best], bm = P.models.find((m) => m.model === best);
    const k = $("premium-kpis"); k.innerHTML = "";
    [[pc(imp.median), `lower error than the rarity baseline (${best}); 90% interval ${sgn(imp.lo)} to ${sgn(imp.hi)}`],
     [`${P.leakage.random_cv_r2.toFixed(2)} vs ${P.leakage.group_cv_r2.toFixed(2)}`, "R² with a random split vs whole-series hold-out (the gap is leakage)"],
     [pc(P.interval.holdout_coverage), "of newest-series prices fell inside the 80% interval"],
     [`${P.n_series} series`, `${P.n_figures} figures, ${P.n_rows} price snapshots: small data`]].forEach(([b, s]) => {
      const d = el("div", "kpi"); d.appendChild(el("b", "", b)); d.appendChild(el("span", "", s)); k.appendChild(d);
    });
    let metric = "mae";
    const COLORS = { "Baseline: mean": "var(--base)", "Baseline: rarity mean": "var(--base)", "Linear (ridge)": "var(--s2)", "LightGBM": "var(--s1)", "XGBoost": "var(--s3)" };
    function bars() {
      const key = metric === "mae" ? "mae" : "holdout_mae";
      const items = P.models.slice().sort((a, b) => a[key] - b[key]).map((m) => ({
        label: m.model, value: m[key], color: COLORS[m.model],
        tip: [{ label: "MAE", value: m[key].toFixed(1) + " pts" }, { label: "R²", value: (metric === "mae" ? m.r2 : m.holdout_r2).toFixed(2) }],
      }));
      const wrap = $("premium-models"); wrap.innerHTML = "";
      const host = el("div"); wrap.appendChild(host);
      C.barChart(host, { items, valueFormat: (v) => v.toFixed(1), xLabel: "mean absolute error, premium percentage points (lower is better)", aria: "Model error comparison", labelWidth: 150 });
      C.tableToggle(host, { headers: ["Model", "MAE (pts)", "RMSE (pts)", "R²"], numeric: [1, 2, 3], caption: "Model comparison",
        rows: P.models.map((m) => [m.model, (metric === "mae" ? m.mae : m.holdout_mae).toFixed(1), m.rmse.toFixed(1), (metric === "mae" ? m.r2 : m.holdout_r2).toFixed(2)]) });
    }
    renderers.push(bars);
    const hb = document.querySelector('#premium-metric button[data-m="hold"]');
    if (hb && P.holdout) hb.textContent = `Newest ${P.holdout.n_series} series`;
    document.querySelectorAll("#premium-metric button").forEach((b) => b.addEventListener("click", () => {
      metric = b.dataset.m; document.querySelectorAll("#premium-metric button").forEach((x) => x.setAttribute("aria-pressed", String(x === b))); bars();
    }));
    function shap() {
      const wrap = $("premium-shap"); wrap.innerHTML = ""; const host = el("div"); wrap.appendChild(host);
      const pretty = { rarity_ord: "Rarity tier", launch_interest: "Search interest at launch", retail_usd: "Retail price", months_since_launch: "Months since launch", release_season: "Release season", theme: "Series theme", collab: "Collab flag" };
      C.barChart(host, { items: P.shap.map((s) => ({ label: pretty[s.feature] || s.feature, value: s.mean_abs, lo: s.lo, hi: s.hi, color: "var(--s1)",
        tip: [{ label: "mean |SHAP|", value: s.mean_abs.toFixed(1) + " pts" }, { label: "5–95% over refits", value: `${s.lo.toFixed(1)}–${s.hi.toFixed(1)}` }, { label: "direction", value: s.direction }] })),
        valueFormat: (v) => v.toFixed(1), xLabel: "mean |SHAP|, premium percentage points (whiskers: 5–95% across leave-one-series-out refits)", aria: "SHAP feature importance", labelWidth: 170 });
      C.tableToggle(host, { headers: ["Feature", "Mean |SHAP|", "5%", "95%", "Direction"], numeric: [1, 2, 3], caption: "SHAP importance",
        rows: P.shap.map((s) => [pretty[s.feature] || s.feature, s.mean_abs.toFixed(2), s.lo.toFixed(2), s.hi.toFixed(2), s.direction]) });
    }
    renderers.push(shap);
    list("premium-takeaways", P.takeaways);
  }

  /* ---------- forecast ---------- */
  function forecast() {
    const F = D.forecast, best = F.chosen_model, ms = C.toMs;
    const histPts = F.history.dates.map((d, i) => [ms(d), F.history.values[i]]);
    const hd = F.holdout.dates.map(ms), hm = F.holdout.models;
    const zip = (dates, arr) => dates.map((d, i) => [d, arr[i]]);
    const bandOf = (m) => hd.map((d, i) => [d, m.lo[i], m.hi[i]]);
    const fd = F.future.dates.map(ms);
    const lastActual = ms(F.history.dates[F.history.dates.length - 1]), holdStart = hd[0];
    let range = "all", showCp = true, showEv = true;
    function draw() {
      const host = fresh("forecast-chart");
      const end = fd[fd.length - 1], start = range === "all" ? histPts[0][0] : end - { "3y": 3.2, "18m": 1.5 }[range] * 3.156e10;
      const maxY = Math.max(100, ...F.future.hi) * 1.04;
      const cp = showCp ? F.changepoints.map((c) => ({ x: ms(c.date), color: "var(--s2)", dash: "", width: 1.6 })) : [];
      const evs = showEv ? F.events.filter((e) => e.type !== "series_launch").map((e) => ({ x: ms(e.date), y: 3, shape: "tri", color: "var(--ink)" })) : [];
      const launches = showEv ? F.events.filter((e) => e.type === "series_launch").map((e) => ({ x: ms(e.date), y: (histPts.find((p) => p[0] >= ms(e.date)) || [0, 0])[1], color: "var(--s4)" })) : [];
      C.lineChart(host, {
        height: 350, xDomain: [start, end], yDomain: [0, maxY], yLabel: "Search interest (0–100)", aria: "Search interest history, hold-out forecast and 26 week forecast",
        series: [
          { name: "Actual", color: "var(--ink)", pts: histPts, width: 1.8, label: "Actual" },
          { name: "Naive (last week)", color: "var(--base)", dash: "5 4", pts: zip(hd, hm["Naive (last week)"].mean), width: 1.5 },
          { name: "Seasonal naive", color: "var(--s3)", dash: "5 4", pts: zip(hd, hm["Seasonal naive (52w)"].mean), width: 1.5 },
          { name: `${best} (held-out)`, color: "var(--s1)", pts: zip(hd, hm[best].mean), width: 2.2 },
          { name: `${best} (next 26 wks)`, color: "var(--s1)", pts: zip(fd, F.future.mean), width: 2.2, label: "Forecast" },
        ],
        bands: [
          { name: "80% interval (held-out)", color: "var(--s1)", opacity: 0.16, pts: bandOf(hm[best]) },
          { name: "80% interval (next 26 wks)", color: "var(--s1)", opacity: 0.28, pts: fd.map((d, i) => [d, F.future.lo[i], F.future.hi[i]]) },
        ],
        vlines: [{ x: holdStart, color: "var(--axis)", dash: "2 4" }, { x: lastActual, color: "var(--axis)", dash: "2 4" }, ...cp],
        markers: [...launches, ...evs], directLabels: true, tipTitle: C.fmtDate, tipFormat: (v) => v.toFixed(0), tipTolerance: 6.5e8,
        legendExtra: [
          ...(showCp ? [{ label: "Detected changepoint", color: "var(--s2)", kind: "line" }] : []),
          ...(showEv ? [{ label: "Series launch", color: "var(--s4)" }, { label: "Store / market event", color: "var(--ink)" }] : []),
        ],
      });
      C.tableToggle(host, { headers: ["Week", "Actual", "Held-out forecast", "Low", "High"], numeric: [1, 2, 3, 4], caption: "Hold-out forecast",
        rows: hd.map((d, i) => [C.fmtDate(d), F.history.values[F.history.values.length - hd.length + i], hm[best].mean[i], hm[best].lo[i], hm[best].hi[i]].map(String)) });
    }
    renderers.push(draw);
    document.querySelectorAll("#forecast-range button").forEach((b) => b.addEventListener("click", () => {
      range = b.dataset.r; document.querySelectorAll("#forecast-range button").forEach((x) => x.setAttribute("aria-pressed", String(x === b))); draw();
    }));
    $("tgl-cp").addEventListener("change", (e) => { showCp = e.target.checked; draw(); });
    $("tgl-ev").addEventListener("change", (e) => { showEv = e.target.checked; draw(); });

    const naive = F.metrics.find((m) => m.model.startsWith("Naive")).mae;
    const t = $("forecast-metrics"); t.innerHTML = "<thead><tr><th>Model</th><th class='num'>MAE</th><th class='num'>MASE</th><th class='num'>sMAPE %</th><th class='num'>vs naive</th><th class='num'>80% coverage</th></tr></thead>";
    const tb = el("tbody");
    F.metrics.slice().sort((a, b) => a.mae - b.mae).forEach((m) => {
      const tr = el("tr"); const gain = 1 - m.mae / naive;
      [m.model + (m.model === best ? "  ← chosen on backtests" : ""), m.mae.toFixed(1), m.mase.toFixed(1), m.smape.toFixed(0), m.model.startsWith("Naive") ? "—" : sgn(gain), m.coverage == null ? "—" : pc(m.coverage)].forEach((c, i) => {
        const td = el("td", i ? "num" : "", c); if (m.model === best) td.style.fontWeight = 800; tr.appendChild(td);
      }); tb.appendChild(tr);
    }); t.appendChild(tb);

    const ct = $("cp-table"); ct.innerHTML = "<thead><tr><th>Changepoint</th><th class='num'>Level shift</th><th>Nearest product event</th><th class='num'>Gap</th></tr></thead>";
    const cb = el("tbody");
    F.changepoints.forEach((c) => {
      const tr = el("tr"); [C.fmtDate(ms(c.date)), (c.shift_pct >= 0 ? "+" : "") + c.shift_pct + "%", c.event, (c.gap_weeks > 0 ? "+" : "") + c.gap_weeks + " wk"].forEach((x, i) => tr.appendChild(el("td", i === 1 || i === 3 ? "num" : "", x)));
      cb.appendChild(tr);
    }); ct.appendChild(cb);
    list("forecast-takeaways", F.takeaways);
  }

  /* ---------- reddit ---------- */
  function reddit() {
    const R = D.reddit, ms = C.toMs, SC = ["var(--s1)", "var(--s2)", "var(--s3)", "var(--s4)", "var(--s5)", "var(--s6)", "var(--s7)", "var(--s8)"];
    const topics = R.topics.slice().sort((a, b) => b.share - a.share);
    const box = $("topic-list"); box.innerHTML = "";
    const maxShare = Math.max(...topics.map((t) => t.share));
    topics.forEach((t) => {
      const row = el("div"); row.style.cssText = "display:grid;grid-template-columns:minmax(120px,190px) 1fr 120px;gap:10px;align-items:center;padding:7px 0;border-bottom:1px solid var(--line)";
      const nm = el("div"); nm.appendChild(el("b", "", t.name)); nm.appendChild(el("div", "muted small", t.keywords.slice(0, 5).join(", ")));
      const bar = el("div"); const fill = el("div"); fill.style.cssText = `height:14px;border-radius:0 4px 4px 0;background:var(--s1);width:${(t.share / maxShare) * 88}%;min-width:3px`;
      const lab = el("span", "small muted", pc(t.share, 0)); lab.style.marginLeft = "6px";
      bar.style.cssText = "display:flex;align-items:center"; bar.appendChild(fill); bar.appendChild(lab);
      const s = t.mean_sentiment, tone = s > 0.15 ? "▲ positive" : s < -0.15 ? "▼ negative" : "● mixed";
      const sent = el("div", "small", `${tone} (${s >= 0 ? "+" : "−"}${Math.abs(s).toFixed(2)})`);
      row.appendChild(nm); row.appendChild(bar); row.appendChild(sent); box.appendChild(row);
    });

    function over() {
      const host = fresh("topic-time"); const T = R.topics_over_time, names = Object.keys(T.series);
      C.stackedBars(host, { categories: T.quarters, series: names.map((n, i) => ({ name: n, color: SC[i % 8], values: T.series[n] })), height: 270, aria: "Topic share by quarter" });
      C.tableToggle(host, { headers: ["Quarter", ...names], numeric: names.map((_, i) => i + 1), caption: "Topic share by quarter",
        rows: T.quarters.map((q, i) => [q, ...names.map((n) => pc(T.series[n][i]))]) });
    }
    function sent() {
      const host = fresh("sent-chart"), dts = R.weekly.dates.map(ms);
      C.lineChart(host, { height: 300, xDomain: [dts[0], dts[dts.length - 1]], yDomain: (() => { const a = R.weekly.demand_mom_z.concat(R.weekly.sentiment_mom_z); return [Math.floor(Math.min(...a)), Math.ceil(Math.max(...a))]; })(), yLabel: "z-score of momentum vs trailing 26 weeks", zeroLine: true, directLabels: true, aria: "Sentiment and demand momentum",
        series: [{ name: "Demand (search)", label: "Demand", color: "var(--s1)", pts: dts.map((d, i) => [d, R.weekly.demand_mom_z[i]]) },
                 { name: "Sentiment (Reddit)", label: "Sentiment", color: "var(--s2)", pts: dts.map((d, i) => [d, R.weekly.sentiment_mom_z[i]]) }],
        tipTitle: C.fmtDate, tipFormat: (v) => v.toFixed(2), tipTolerance: 5e8 });
      C.tableToggle(host, { headers: ["Week", "Demand z", "Sentiment z"], numeric: [1, 2], caption: "Weekly momentum",
        rows: dts.map((d, i) => [C.fmtDate(d), R.weekly.demand_mom_z[i].toFixed(2), R.weekly.sentiment_mom_z[i].toFixed(2)]).slice(-60) });
    }
    function xc() {
      const host = fresh("xcorr-chart"), X = R.xcorr;
      C.lineChart(host, { height: 280, xType: "num", xDomain: [-12, 12], yDomain: [Math.min(-0.2, ...X.map((p) => p.lo)) - 0.05, Math.max(...X.map((p) => p.hi)) + 0.05], yLabel: "correlation", zeroLine: true, aria: "Cross correlation",
        series: [{ name: "Correlation", color: "var(--s1)", pts: X.map((p) => [p.lag, p.r]), dots: true }],
        bands: [{ name: "90% block-bootstrap interval", color: "var(--s1)", opacity: 0.18, pts: X.map((p) => [p.lag, p.lo, p.hi]) }],
        vlines: [{ x: 0, color: "var(--axis)", dash: "2 4" }], tipTitle: (x) => `Lag ${x > 0 ? "+" : ""}${x} weeks`, tipFormat: (v) => v.toFixed(2), tipTolerance: 0.6,
        yFormat: (v) => v.toFixed(1), legendExtra: [] });
      C.tableToggle(host, { headers: ["Lag (weeks)", "r", "5%", "95%"], numeric: [0, 1, 2, 3], caption: "Cross-correlation", rows: X.map((p) => [p.lag, p.r.toFixed(2), p.lo.toFixed(2), p.hi.toFixed(2)].map(String)) });
    }
    renderers.push(over, sent, xc);
    list("reddit-takeaways", R.takeaways);
    $("reddit-embedder").textContent = R.embedder;
  }

  /* ---------- method ---------- */
  function method() {
    const prov = D.catalog.provenance, tb = $("prov-table"); tb.innerHTML = "";
    const what = { series: "Series catalog (names, dates, retail)", figures: "Figures, rarity tiers, pull rates", resale: "Resale premium snapshots", trends: "Search interest (Google Trends)", events: "Product events", reddit: "r/smiski posts" };
    Object.keys(what).forEach((k) => {
      const tr = el("tr"); tr.appendChild(el("td", "", what[k])); const st = el("td", "", (prov[k] === "simulated" ? "⚠ " : "✓ ") + prov[k]); st.style.fontWeight = 700; tr.appendChild(st); tb.appendChild(tr);
    });
  }

  function assumptions() {
    const ul = $("assumptions"); ul.innerHTML = "";
    (D.catalog.assumptions || []).forEach((t) => ul.appendChild(el("li", "", t)));
    if (D.catalog.trends_note) ul.appendChild(el("li", "", D.catalog.trends_note));
    if (!ul.children.length) $("assumptions-box").hidden = true;
  }

  /* ---------- theme + boot ---------- */
  function theme() {
    const root = document.documentElement, btn = $("theme-btn");
    const saved = (() => { try { return localStorage.getItem("smiski-theme"); } catch (e) { return null; } })();
    if (saved) root.dataset.theme = saved;
    const isDark = () => root.dataset.theme === "dark" || (!root.dataset.theme && matchMedia("(prefers-color-scheme: dark)").matches);
    const label = () => { btn.textContent = isDark() ? "☀ Lights on" : "☾ Lights off"; };
    label();
    btn.addEventListener("click", () => { root.dataset.theme = isDark() ? "light" : "dark"; try { localStorage.setItem("smiski-theme", root.dataset.theme); } catch (e) {} label(); });
  }

  function boot() {
    const errs = $("errors");
    window.addEventListener("error", (e) => { errs.style.display = "block"; errs.textContent += (e.message || e) + "\n"; });
    try {
      theme(); banner();
      const hero = $("hero-art"), s0 = D.catalog.series[7];
      s0.figures.slice(0, 5).concat(s0.figures.slice(-1)).forEach((f) => { const d = el("div"); d.innerHTML = window.BlindBox.figureArt(f); hero.appendChild(d); });
      window.BlindBox.init(D);
      premium(); forecast(); reddit(); method(); assumptions();
      renderers.forEach((r) => r());
      let t; window.addEventListener("resize", () => { clearTimeout(t); t = setTimeout(() => renderers.forEach((r) => r()), 150); });
    } catch (e) { errs.style.display = "block"; errs.textContent += (e && e.stack) || e; throw e; }
  }
  document.addEventListener("DOMContentLoaded", boot);
})();
