/* Tiny dependency-free SVG chart kit: line (+bands, markers, vlines), horizontal bars (+whiskers), stacked bars.
   Every chart: legend for >=2 series, hover tooltip, recessive grid, and an optional table view. */
(function () {
  const NS = "http://www.w3.org/2000/svg";
  const svg = (tag, attrs = {}, parent) => {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  };
  const html = (tag, attrs = {}, text) => {
    const e = document.createElement(tag);
    for (const k in attrs) k === "class" ? (e.className = attrs[k]) : e.setAttribute(k, attrs[k]);
    if (text != null) e.textContent = text;
    return e;
  };
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const fmtDate = (ms) => { const d = new Date(ms); return `${MONTHS[d.getUTCMonth()]} ${d.getUTCDate()}, ${d.getUTCFullYear()}`; };
  const toMs = (s) => Date.parse(s + "T00:00:00Z");

  function niceTicks(lo, hi, n = 5) {
    if (hi === lo) return [lo];
    const raw = (hi - lo) / n, mag = Math.pow(10, Math.floor(Math.log10(raw)));
    const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw);
    const out = [];
    for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(10));
    return out;
  }
  function timeTicks(a, b) {
    const years = (b - a) / 3.15e10, out = [];
    const start = new Date(a), y0 = start.getUTCFullYear();
    if (years > 2.2) {
      const stepY = years > 7 ? 2 : 1;
      for (let y = y0 + 1; Date.UTC(y, 0, 1) <= b; y += stepY) out.push([Date.UTC(y, 0, 1), String(y)]);
    } else {
      const step = years > 1 ? 3 : 1;
      let y = y0, m = start.getUTCMonth() + 1;
      for (;;) {
        if (m > 11) { y++; m = m - 12; }
        const t = Date.UTC(y, m, 1);
        if (t > b) break;
        if (m % step === 0) out.push([t, m === 0 ? String(y) : MONTHS[m]]);
        m++;
      }
    }
    return out;
  }

  let clipSeq = 0;
  function mount(host, o) {
    host.innerHTML = "";
    host.classList.add("chart");
    host.style.position = "relative";
    const tip = html("div", { class: "tip", role: "status" });
    host.appendChild(tip);
    return { tip };
  }
  function showTip(host, tip, px, py, rows, title) {
    tip.innerHTML = "";
    if (title) tip.appendChild(html("b", {}, title));
    rows.forEach((r) => {
      const d = html("div", { class: "r" });
      const l = html("span");
      if (r.color) { const sw = html("i"); sw.style.background = r.color; l.appendChild(sw); }
      l.appendChild(document.createTextNode(r.label));
      d.appendChild(l); d.appendChild(html("span", {}, r.value));
      tip.appendChild(d);
    });
    const hw = host.clientWidth, tw = tip.offsetWidth || 150;
    let x = px + 14; if (x + tw > hw) x = px - tw - 14;
    tip.style.left = Math.max(0, x) + "px"; tip.style.top = Math.max(0, py - 10) + "px"; tip.style.opacity = 1;
  }
  const hideTip = (tip) => { tip.style.opacity = 0; };

  function legend(host, items) {
    const lg = html("div", { class: "legend" });
    items.forEach((it) => {
      const s = html("span");
      const sw = html("i", { class: it.kind === "line" ? "line" : it.kind === "dash" ? "dash" : "" });
      if (it.kind === "dash") sw.style.borderTopColor = it.color; else sw.style.background = it.color;
      if (it.opacity) sw.style.opacity = it.opacity;
      s.appendChild(sw); s.appendChild(document.createTextNode(it.label)); lg.appendChild(s);
    });
    host.parentNode.insertBefore(lg, host);
    return lg;
  }

  /* ---------------- line chart ---------------- */
  function lineChart(host, o) {
    const { tip } = mount(host, o);
    const W = Math.max(320, host.clientWidth || 800), H = o.height || 320;
    const m = Object.assign({ l: 44, r: o.directLabels ? 78 : 14, t: 12, b: 30 }, o.margin || {});
    const root = svg("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": o.aria || "line chart" }, host);
    const [x0, x1] = o.xDomain, [y0, y1] = o.yDomain;
    const sx = (v) => m.l + ((v - x0) / (x1 - x0)) * (W - m.l - m.r);
    const sy = (v) => H - m.b - ((v - y0) / (y1 - y0)) * (H - m.t - m.b);

    const grid = svg("g", { class: "grid" }, root);
    niceTicks(y0, y1, 5).forEach((t) => {
      svg("line", { x1: m.l, x2: W - m.r, y1: sy(t), y2: sy(t) }, grid);
      const tx = svg("text", { x: m.l - 8, y: sy(t) + 4, "text-anchor": "end" }, root); tx.textContent = (o.yFormat || String)(t);
    });
    // everything data-driven is clipped to the plot area so wide bands cannot spill over the axes
    const clipId = "clip" + (++clipSeq);
    const cp_ = svg("clipPath", { id: clipId }, root);
    svg("rect", { x: m.l, y: m.t, width: W - m.l - m.r, height: H - m.t - m.b }, cp_);
    const plot = svg("g", { "clip-path": `url(#${clipId})` }, root);
    const ticks = o.xType === "num" ? niceTicks(x0, x1, 8).map((v) => [v, String(v)]) : timeTicks(x0, x1);
    ticks.forEach(([v, lab]) => {
      const tx = svg("text", { x: sx(v), y: H - m.b + 17, "text-anchor": "middle" }, root); tx.textContent = lab;
      svg("line", { x1: sx(v), x2: sx(v), y1: H - m.b, y2: H - m.b + 4, stroke: "var(--axis)" }, root);
    });
    svg("line", { x1: m.l, x2: W - m.r, y1: H - m.b, y2: H - m.b, stroke: "var(--axis)" }, root);
    if (o.yLabel) { const t = svg("text", { x: m.l, y: m.t - 2, class: "title" }, root); t.textContent = o.yLabel; }
    if (o.zeroLine) svg("line", { x1: m.l, x2: W - m.r, y1: sy(0), y2: sy(0), stroke: "var(--axis)", "stroke-dasharray": "3 3" }, root);

    (o.bands || []).forEach((b) => {
      const pts = b.pts.filter((p) => p[0] >= x0 && p[0] <= x1);
      if (!pts.length) return;
      const top = pts.map((p) => `${sx(p[0])},${sy(p[2])}`), bot = pts.slice().reverse().map((p) => `${sx(p[0])},${sy(p[1])}`);
      svg("path", { d: "M" + top.concat(bot).join("L") + "Z", fill: b.color, opacity: b.opacity || 0.2 }, plot);
    });
    (o.vlines || []).forEach((v) => {
      if (v.x < x0 || v.x > x1) return;
      svg("line", { x1: sx(v.x), x2: sx(v.x), y1: m.t, y2: H - m.b, stroke: v.color || "var(--axis)", "stroke-width": v.width || 1, "stroke-dasharray": v.dash || "4 3" }, plot);
    });
    const ends = [];
    (o.series || []).forEach((s) => {
      const pts = s.pts.filter((p) => p[0] >= x0 && p[0] <= x1 && p[1] != null);
      if (!pts.length) return;
      const p = svg("path", { d: "M" + pts.map((q) => `${sx(q[0]).toFixed(1)},${sy(q[1]).toFixed(1)}`).join("L"), fill: "none", stroke: s.color,
        "stroke-width": s.width || 2, "stroke-linejoin": "round", "stroke-linecap": "round" }, plot);
      if (s.dash) p.setAttribute("stroke-dasharray", s.dash);
      if (s.dots) pts.forEach((q) => svg("circle", { cx: sx(q[0]), cy: sy(q[1]), r: 3.5, fill: s.color, stroke: "var(--surface-1)", "stroke-width": 1.5 }, plot));
      if (o.directLabels && s.label) ends.push({ y: sy(pts[pts.length - 1][1]), x: sx(pts[pts.length - 1][0]), text: s.label });
    });
    ends.sort((a, b) => a.y - b.y);
    for (let i = 1; i < ends.length; i++) if (ends[i].y - ends[i - 1].y < 13) ends[i].y = ends[i - 1].y + 13;
    ends.forEach((e) => { const t = svg("text", { x: e.x + 6, y: e.y + 4 }, root); t.textContent = e.text; });
    (o.markers || []).forEach((mk) => {
      if (mk.x < x0 || mk.x > x1) return;
      const cx = sx(mk.x), cy = sy(mk.y);
      if (mk.shape === "tri") svg("path", { d: `M${cx - 5},${cy + 4}L${cx + 5},${cy + 4}L${cx},${cy - 6}Z`, fill: mk.color, stroke: "var(--surface-1)", "stroke-width": 1.5 }, plot);
      else svg("circle", { cx, cy, r: 4.5, fill: mk.color, stroke: "var(--surface-1)", "stroke-width": 2 }, plot);
    });

    // hover layer
    const cross = svg("line", { y1: m.t, y2: H - m.b, stroke: "var(--axis)", "stroke-width": 1, opacity: 0 }, root);
    const dots = (o.series || []).map((s) => svg("circle", { r: 4.5, fill: s.color, stroke: "var(--surface-1)", "stroke-width": 2, opacity: 0 }, root));
    const nearest = (pts, x) => {
      let lo = 0, hi = pts.length - 1;
      while (hi - lo > 1) { const mid = (lo + hi) >> 1; pts[mid][0] < x ? (lo = mid) : (hi = mid); }
      return Math.abs(pts[lo][0] - x) <= Math.abs(pts[hi][0] - x) ? pts[lo] : pts[hi];
    };
    const overlay = svg("rect", { x: m.l, y: m.t, width: W - m.l - m.r, height: H - m.t - m.b, fill: "transparent", style: "cursor:crosshair" }, root);
    overlay.addEventListener("pointermove", (ev) => {
      const r = root.getBoundingClientRect(), px = ((ev.clientX - r.left) / r.width) * W;
      const xv = x0 + ((px - m.l) / (W - m.l - m.r)) * (x1 - x0);
      const rows = []; let ax = null, ay = m.t + 20;
      (o.series || []).forEach((s, i) => {
        const pts = s.pts.filter((p) => p[1] != null);
        if (!pts.length || s.noTip) { dots[i].setAttribute("opacity", 0); return; }
        const p = nearest(pts, xv);
        if (Math.abs(p[0] - xv) > (o.tipTolerance || (x1 - x0) / 40)) { dots[i].setAttribute("opacity", 0); return; }
        dots[i].setAttribute("cx", sx(p[0])); dots[i].setAttribute("cy", sy(p[1])); dots[i].setAttribute("opacity", 1);
        ax = p[0]; ay = sy(p[1]);
        rows.push({ color: s.color, label: s.name, value: (o.tipFormat || String)(p[1], s) });
      });
      (o.bands || []).forEach((b) => {
        if (!b.pts.length || b.noTip) return;
        const p = nearest(b.pts, xv);
        if (Math.abs(p[0] - xv) <= (o.tipTolerance || (x1 - x0) / 40)) rows.push({ color: b.color, label: b.name, value: `${(o.tipFormat || String)(p[1])} – ${(o.tipFormat || String)(p[2])}` });
      });
      if (!rows.length) { cross.setAttribute("opacity", 0); hideTip(tip); return; }
      cross.setAttribute("x1", sx(ax)); cross.setAttribute("x2", sx(ax)); cross.setAttribute("opacity", 1);
      const hostRect = host.getBoundingClientRect();
      showTip(host, tip, (sx(ax) / W) * r.width + (r.left - hostRect.left), ay * (r.height / H), rows, (o.tipTitle || String)(ax));
    });
    overlay.addEventListener("pointerleave", () => { cross.setAttribute("opacity", 0); dots.forEach((d) => d.setAttribute("opacity", 0)); hideTip(tip); });

    if (o.legend !== false) {
      const items = [];
      (o.series || []).forEach((s) => items.push({ label: s.name, color: s.color, kind: s.dash ? "dash" : "line" }));
      (o.bands || []).forEach((b) => items.push({ label: b.name, color: b.color, opacity: b.opacity || 0.2 }));
      (o.legendExtra || []).forEach((x) => items.push(x));
      if (items.length >= 2 || (o.legendExtra || []).length) legend(host, items);
    }
    return root;
  }

  /* ---------------- horizontal bars ---------------- */
  function barChart(host, o) {
    const { tip } = mount(host, o);
    const W = Math.max(320, host.clientWidth || 700), rowH = o.rowH || 32, n = o.items.length;
    const labW = Math.min(o.labelWidth || 170, W * 0.42), m = { l: labW + 8, r: 56, t: 8, b: 30 };
    const H = m.t + n * rowH + m.b;
    const root = svg("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": o.aria || "bar chart" }, host);
    const max = o.max || Math.max(...o.items.map((d) => Math.max(d.value, d.hi || 0))) * 1.08;
    const min = o.min || 0;
    const sx = (v) => m.l + ((v - min) / (max - min)) * (W - m.l - m.r);
    const grid = svg("g", { class: "grid" }, root);
    niceTicks(min, max, 5).forEach((t) => {
      svg("line", { x1: sx(t), x2: sx(t), y1: m.t, y2: H - m.b }, grid);
      const tx = svg("text", { x: sx(t), y: H - m.b + 16, "text-anchor": "middle" }, root); tx.textContent = (o.valueFormat || String)(t);
    });
    if (o.xLabel) { const t = svg("text", { x: W - m.r, y: H - 2, "text-anchor": "end" }, root); t.textContent = o.xLabel; }
    const x0 = sx(Math.max(0, min));
    svg("line", { x1: x0, x2: x0, y1: m.t, y2: H - m.b, stroke: "var(--axis)" }, root);
    o.items.forEach((d, i) => {
      const cy = m.t + i * rowH + rowH / 2, bh = Math.min(18, rowH * 0.6);
      const t = svg("text", { x: m.l - 8, y: cy + 4, "text-anchor": "end" }, root);
      t.textContent = d.label.length > 28 ? d.label.slice(0, 27) + "…" : d.label;
      const xe = sx(d.value), r = 4, top = cy - bh / 2, bot = cy + bh / 2;
      const w = Math.max(xe - x0, 0);
      const rr = Math.min(r, w);
      // flat on the baseline, rounded data end
      svg("path", { d: `M${x0},${top}H${x0 + w - rr}Q${x0 + w},${top} ${x0 + w},${top + rr}V${bot - rr}Q${x0 + w},${bot} ${x0 + w - rr},${bot}H${x0}Z`, fill: d.color || "var(--s1)" }, root);
      let labelX = xe + 6;
      if (d.lo != null) {
        svg("line", { x1: sx(d.lo), x2: sx(d.hi), y1: cy, y2: cy, stroke: "var(--ink-2)", "stroke-width": 1.5 }, root);
        [d.lo, d.hi].forEach((v) => svg("line", { x1: sx(v), x2: sx(v), y1: cy - 5, y2: cy + 5, stroke: "var(--ink-2)", "stroke-width": 1.5 }, root));
        labelX = sx(d.hi) + 6;
      }
      const vt = svg("text", { x: labelX, y: cy + 4 }, root); vt.textContent = (o.valueFormat || String)(d.value);
      const hit = svg("rect", { x: 0, y: cy - rowH / 2, width: W, height: rowH, fill: "transparent" }, root);
      hit.addEventListener("pointermove", (ev) => {
        const rect = host.getBoundingClientRect();
        showTip(host, tip, ev.clientX - rect.left, ev.clientY - rect.top, (d.tip || [{ label: "value", value: (o.valueFormat || String)(d.value) }]), d.label);
      });
      hit.addEventListener("pointerleave", () => hideTip(tip));
    });
    return root;
  }

  /* ---------------- stacked (100%) bars ---------------- */
  function stackedBars(host, o) {
    const { tip } = mount(host, o);
    const W = Math.max(320, host.clientWidth || 800), H = o.height || 280, m = { l: 40, r: 10, t: 10, b: 28 };
    const root = svg("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": o.aria || "stacked bar chart" }, host);
    const n = o.categories.length, bw = (W - m.l - m.r) / n, sy = (v) => H - m.b - v * (H - m.t - m.b);
    const grid = svg("g", { class: "grid" }, root);
    [0, 0.25, 0.5, 0.75, 1].forEach((t) => {
      svg("line", { x1: m.l, x2: W - m.r, y1: sy(t), y2: sy(t) }, grid);
      const tx = svg("text", { x: m.l - 6, y: sy(t) + 4, "text-anchor": "end" }, root); tx.textContent = Math.round(t * 100) + "%";
    });
    o.categories.forEach((c, i) => {
      const x = m.l + i * bw, tot = o.series.reduce((a, s) => a + s.values[i], 0) || 1;
      let acc = 0;
      o.series.forEach((s) => {
        const v = s.values[i] / tot; if (v <= 0) return;
        const y = sy(acc + v), h = sy(acc) - y;
        svg("rect", { x: x + 1, y, width: Math.max(bw - 2, 1), height: Math.max(h, 0), fill: s.color, stroke: "var(--surface-1)", "stroke-width": 1.5 }, root);
        acc += v;
      });
      if (c.endsWith("Q1")) { const t = svg("text", { x: x + bw / 2, y: H - m.b + 16, "text-anchor": "middle" }, root); t.textContent = c.slice(0, 4); }
      const hit = svg("rect", { x, y: m.t, width: bw, height: H - m.t - m.b, fill: "transparent" }, root);
      hit.addEventListener("pointermove", (ev) => {
        const rect = host.getBoundingClientRect();
        showTip(host, tip, ev.clientX - rect.left, ev.clientY - rect.top,
          o.series.map((s) => ({ color: s.color, label: s.name, value: Math.round((s.values[i] / tot) * 100) + "%" })).filter((r) => r.value !== "0%"), c);
      });
      hit.addEventListener("pointerleave", () => hideTip(tip));
    });
    if (o.legend !== false) legend(host, o.series.map((s) => ({ label: s.name, color: s.color })));
    return root;
  }

  /* ---------------- table view toggle ---------------- */
  function tableToggle(host, { headers, rows, caption, numeric = [] }) {
    const wrap = html("div", { class: "tbl" });
    wrap.hidden = true;
    const t = html("table"); if (caption) t.appendChild(html("caption", { class: "sr-only" }, caption));
    const thead = html("thead"), tr = html("tr");
    headers.forEach((hd, i) => { const th = html("th", { class: numeric.includes(i) ? "num" : "" }, hd); tr.appendChild(th); });
    thead.appendChild(tr); t.appendChild(thead);
    const tb = html("tbody");
    rows.forEach((r) => { const row = html("tr"); r.forEach((c, i) => row.appendChild(html("td", { class: numeric.includes(i) ? "num" : "" }, c))); tb.appendChild(row); });
    t.appendChild(tb); wrap.appendChild(t);
    const btn = html("button", { class: "btn small", type: "button", "aria-expanded": "false" }, "Show data table");
    btn.addEventListener("click", () => { wrap.hidden = !wrap.hidden; btn.textContent = wrap.hidden ? "Show data table" : "Hide data table"; btn.setAttribute("aria-expanded", String(!wrap.hidden)); });
    host.parentNode.insertBefore(btn, host.nextSibling);
    btn.parentNode.insertBefore(wrap, btn.nextSibling);
  }

  window.Charts = { lineChart, barChart, stackedBars, tableToggle, toMs, fmtDate, niceTicks };
})();
