/* Virtual blind box: pick a series -> pick a box -> open -> weighted random figure, with a model-estimated value.
   Pure logic is exported for tests (module.exports); DOM wiring runs in the browser. */
(function (root) {
  "use strict";

  const hash = (s) => { let h = 2166136261; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; };

  /** Weighted draw. Pull rates are normalised, so they need not sum to exactly 1. */
  function drawFigure(series, rand = Math.random) {
    const total = series.figures.reduce((a, f) => a + f.pull_rate, 0);
    let x = rand() * total;
    for (const f of series.figures) { x -= f.pull_rate; if (x < 0) return f; }
    return series.figures[series.figures.length - 1];
  }

  const money = (v) => (v == null ? "n/a" : "$" + v.toFixed(2));
  const pct = (v) => (v == null ? "n/a" : (v >= 0 ? "+" : "") + Math.round(v) + "%");

  /** Original generic sprite (not official art). Pose varies deterministically per figure. */
  function figureSVG(fig, o = {}) {
    const s = hash(fig.id || fig.name), r = (i) => ((s >>> (i * 3)) & 7) / 7;
    const tier = fig.tier || "common";
    const fill = o.mystery ? "var(--bg-2)" : `var(--fig-${tier})`, edge = o.mystery ? "var(--ink-3)" : `var(--fig-${tier}-edge)`;
    const ink = "var(--fig-ink)";
    const arm = (sx, sy, deg) => { const a = (deg * Math.PI) / 180; return [sx + Math.cos(a) * 21, sy + Math.sin(a) * 21]; };
    const aL = 100 + r(0) * 110, aR = 80 - r(1) * 110;           // degrees, 90 = straight down
    const [lx, ly] = arm(34, 78, aL), [rx, ry] = arm(66, 78, aR);
    const tilt = ((r(3) - 0.5) * 14).toFixed(1), sit = r(4) > 0.5, spread = 3 + r(2) * 8;
    const limb = (x1, y1, x2, y2, w = 9) =>
      `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${edge}" stroke-width="${w + 3}" stroke-linecap="round"/>` +
      `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${fill}" stroke-width="${w}" stroke-linecap="round"/>`;
    const legs = sit
      ? limb(42, 103, 30 - spread / 2, 112) + limb(58, 103, 70 + spread / 2, 112)
      : limb(42, 102, 40 - spread / 3, 120) + limb(58, 102, 60 + spread / 3, 120);
    const face = o.mystery
      ? `<text x="50" y="56" text-anchor="middle" font-size="30" font-weight="800" fill="${edge}">?</text>`
      : `<circle cx="41" cy="46" r="2.6" fill="${ink}"/><circle cx="59" cy="46" r="2.6" fill="${ink}"/>` +
        (tier === "secret" ? `<path d="M44,54 Q50,60 56,54" stroke="${ink}" stroke-width="2" fill="none" stroke-linecap="round"/>`
                           : `<path d="M45,54 Q50,57.5 55,54" stroke="${ink}" stroke-width="2" fill="none" stroke-linecap="round"/>`);
    const spark = tier === "secret" && !o.mystery
      ? `<path d="M12,22 l2,5 5,2 -5,2 -2,5 -2,-5 -5,-2 5,-2z M88,30 l1.6,4 4,1.6 -4,1.6 -1.6,4 -1.6,-4 -4,-1.6 4,-1.6z" fill="var(--fig-secret-edge)"/>` : "";
    return `<svg viewBox="0 0 100 128" class="${tier === "secret" && !o.mystery ? "glowing " : ""}${o.cls || ""}" role="img" aria-label="${o.mystery ? "Unknown figure" : fig.name + " (" + tier + ")"}">` +
      spark + legs +
      `<ellipse cx="50" cy="86" rx="19" ry="21" fill="${fill}" stroke="${edge}" stroke-width="3"/>` +
      limb(34, 78, lx, ly, 8) + limb(66, 78, rx, ry, 8) +
      `<g transform="rotate(${tilt} 50 62)"><circle cx="50" cy="44" r="27" fill="${fill}" stroke="${edge}" stroke-width="3"/>${face}</g></svg>`;
  }

  /** Real product image when the file exists (local use), otherwise the original sprite.
   *  ``mystery`` renders an undiscovered figure as a silhouette (real image) or a "?" sprite (no image). */
  function figureArt(fig, o = {}) {
    if (fig.img) {
      const cls = ["figimg", o.mystery ? "silhouette" : fig.tier === "secret" ? "glowing" : "", o.cls || ""].join(" ").trim();
      return `<img src="${fig.img}" class="${cls}" alt="${o.mystery ? "Undiscovered figure" : fig.name}" loading="lazy" decoding="async" draggable="false">`;
    }
    return figureSVG(fig, o);
  }

  /* ---------------- UI ---------------- */
  function init(data) {
    const $ = (id) => document.getElementById(id);
    const series = data.catalog.series;
    const simulated = data.catalog.provenance.resale === "simulated";
    const BOXES = 6;
    const KEY = "smiski-lab-collection-v1";
    let store = {};
    try { store = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) { store = {}; }
    const save = () => { try { localStorage.setItem(KEY, JSON.stringify(store)); } catch (e) { /* private mode */ } };
    const S = { series: series[series.length - 1], boxes: [], sel: null, busy: false };
    const col = () => (store[S.series.id] = store[S.series.id] || { counts: {}, opened: 0, history: [] });

    function newBoxes() { S.boxes = Array.from({ length: BOXES }, () => ({ opened: false })); S.sel = null; }

    function renderSeries() {
      const host = $("sim-series"); host.innerHTML = "";
      series.forEach((s) => {
        const b = document.createElement("button");
        b.className = "chip"; b.type = "button"; b.setAttribute("aria-pressed", String(s.id === S.series.id));
        b.innerHTML = `${s.name.replace(" Series", "")}<small>${s.release.slice(0, 4)}${s.collab ? " · collab" : ""}</small>`;
        b.addEventListener("click", () => { S.series = s; newBoxes(); $("sim-reveal").innerHTML = idleHTML(); renderAll(); });
        host.appendChild(b);
      });
    }
    function renderBoxes() {
      const host = $("sim-boxes"); host.innerHTML = "";
      S.boxes.forEach((bx, i) => {
        const b = document.createElement("button");
        b.type = "button"; b.className = "boxbtn" + (bx.opened ? " opened" : ""); b.id = "box-" + i;
        b.setAttribute("aria-pressed", String(S.sel === i)); b.setAttribute("aria-label", `Box ${i + 1}${bx.opened ? " (opened)" : ""}`);
        b.innerHTML = `<span class="q">${bx.opened ? "✓" : "?"}</span>`;
        b.addEventListener("click", () => { if (S.busy || bx.opened) return; if (S.sel === i) return openBox(); S.sel = i; renderBoxes(); renderOpen(); });
        host.appendChild(b);
      });
    }
    function renderOpen() {
      const left = S.boxes.filter((b) => !b.opened).length;
      $("sim-open").disabled = S.sel == null || S.busy;
      $("sim-openall").disabled = S.busy || left === 0;
      $("sim-fresh").disabled = S.busy;
      $("sim-hint").textContent = left === 0 ? "All boxes opened — grab a fresh set to keep going."
        : S.sel == null ? `Pick one of the ${left} sealed boxes.` : `Box ${S.sel + 1} selected. Click it again or press Open.`;
    }
    const idleHTML = () => `<div class="muted">${figureArt({ id: "x", name: "?", tier: "common" }, { mystery: true, cls: "fig" })}<p>Your figure will appear here.</p></div>`;

    function revealHTML(f, fresh) {
      const s = S.series, odds = f.pull_rate;
      const val = f.pred_usd == null ? "" : `
        <div class="value">
          <div class="muted small">Predicted value${simulated ? " (simulated data)" : ""}</div>
          <div class="big">${money(f.pred_usd)}</div>
          <div class="rng">80% range ${money(f.lo_usd)} – ${money(f.hi_usd)} · ${pct(f.pred_pct)} vs ${money(s.retail_usd)} retail</div>
          <div class="why">Model estimate from a ${data.premium.best_model} fit that never saw this series. Resale prices are simulated, so this is a demo of the method, not a price quote.</div>
        </div>`;
      return `<div class="fig ${fresh ? "pop" : ""}">${figureArt(f, { cls: "fig" })}</div>
        <h3>${f.name}</h3>
        <div><span class="tier ${f.tier}">${f.tier}${f.glow ? " · glows" : ""}</span></div>
        ${f.description ? `<p class="muted small" style="max-width:330px;margin:4px 0">“${f.description}”<br><span style="opacity:.7">official description</span></p>` : ""}
        <div class="muted small">${s.name} · assumed pull chance ${(odds * 100).toFixed(1)}% (about 1 in ${Math.round(1 / odds)})</div>${val}`;
    }

    function pull() {
      const f = drawFigure(S.series), c = col();
      c.counts[f.id] = (c.counts[f.id] || 0) + 1; c.opened++;
      c.history = [f.id, ...c.history].slice(0, 10); save();
      return f;
    }
    function openBox(forceIdx) {
      const i = forceIdx != null ? forceIdx : S.sel;
      if (i == null || S.busy || S.boxes[i].opened) return Promise.resolve();
      S.busy = true; renderOpen();
      const btn = $("box-" + i); if (btn) btn.classList.add("shake");
      return new Promise((res) => setTimeout(() => {
        const f = pull(); S.boxes[i].opened = true; if (S.sel === i) S.sel = null; S.busy = false;
        $("sim-reveal").innerHTML = revealHTML(f, true);
        renderAll(); res();
      }, window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 560));
    }
    async function openAll() { for (let i = 0; i < S.boxes.length; i++) if (!S.boxes[i].opened) { await openBox(i); await new Promise((r) => setTimeout(r, 120)); } }

    function renderCollection() {
      const c = col(), s = S.series;
      $("sim-collection").innerHTML = s.figures.map((f) => {
        const n = c.counts[f.id] || 0;
        return `<div class="slot ${n ? "" : "missing"}" title="${f.name}">${n > 1 ? `<span class="count">×${n}</span>` : ""}${figureArt(f, { mystery: !n })}<div>${n ? f.name : "???"}</div></div>`;
      }).join("");
      const have = s.figures.filter((f) => c.counts[f.id]).length;
      const spent = c.opened * s.retail_usd;
      const value = s.figures.reduce((a, f) => a + (c.counts[f.id] || 0) * (f.pred_usd || 0), 0);
      $("sim-stats").innerHTML = [
        [c.opened, "boxes opened"], [`${have}/${s.figures.length}`, "figures found"], [money(spent), "spent at retail"],
        [c.opened ? money(value) : "—", "est. value" + (simulated ? " (sim.)" : "")],
      ].map(([b, l]) => `<div class="stat"><b>${b}</b><span>${l}</span></div>`).join("");
      $("sim-history").innerHTML = c.history.length
        ? c.history.map((id) => { const f = s.figures.find((x) => x.id === id); return f ? `<span title="${f.name}" style="display:inline-block;width:30px;margin-right:4px">${figureArt(f)}</span>` : ""; }).join("")
        : '<span class="muted small">No pulls yet.</span>';
    }
    function renderOdds() {
      $("sim-odds").innerHTML = "<table><thead><tr><th>Figure</th><th>Tier</th><th class='num'>Assumed chance</th><th class='num'>Predicted value</th></tr></thead><tbody>" +
        S.series.figures.map((f) => `<tr><td><div class="odds-row">${figureArt(f)}${f.name}</div></td><td>${f.tier}</td><td class="num">${(f.pull_rate * 100).toFixed(1)}%</td>` +
          `<td class="num">${money(f.pred_usd)} <span class="muted small">(${money(f.lo_usd)}–${money(f.hi_usd)})</span></td></tr>`).join("") + "</tbody></table>";
      $("sim-series-title").textContent = `${S.series.name} · ${S.series.collab ? "collab · " : ""}${money(S.series.retail_usd)} per box`;
    }
    function renderAll() { renderSeries(); renderBoxes(); renderOpen(); renderCollection(); renderOdds(); }

    $("sim-open").addEventListener("click", () => openBox());
    $("sim-openall").addEventListener("click", openAll);
    $("sim-fresh").addEventListener("click", () => { newBoxes(); renderBoxes(); renderOpen(); });
    $("sim-reset").addEventListener("click", () => { delete store[S.series.id]; save(); renderAll(); $("sim-reveal").innerHTML = idleHTML(); });
    newBoxes(); $("sim-reveal").innerHTML = idleHTML(); renderAll();
  }

  const api = { drawFigure, figureSVG, figureArt, hash, init };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.BlindBox = api;
})(typeof window !== "undefined" ? window : globalThis);
