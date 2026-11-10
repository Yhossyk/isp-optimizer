/* ISP OPTIMIZER · frontend. Una única fuente de datos activos: el objeto S. */
"use strict";
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const NUM = (x) => (x === null || x === undefined ? NaN : Number(String(x).replace(",", ".")));
function fmt(x, d = 6) {
  if (x === null || x === undefined || Number.isNaN(x)) return "—";
  if (x === 0) return "0";
  const a = Math.abs(x);
  if (a < 1e-4 || a >= 1e7) return x.toExponential(3);
  return x.toFixed(d);
}
const sci = (x) => (x === null || x === undefined ? "—" : Number(x).toExponential(2));
const AREAS = ["Fibra óptica", "Routers y switches", "Servidores", "Mantenimiento"];
const C = { cyan: "#22d3ee", blue: "#2f6bff", violet: "#8b5cf6", amber: "#f59e0b", ok: "#34d399" };

const S = {
  scenarios: [], byId: {}, props: null, defaults: { tol: 1e-6, max_iter: 1000, precond: "jacobi" },
  mode: "scenario", sid: "ideal", A: [], b: [], x0: [], tol: "1e-6", maxIter: "1000", pre: "jacobi", mirror: true,
  result: null, seq: 0, stale: false, timer: null, compare: null, compareKey: "", charts: {},
};

async function api(url, opts) {
  const r = await fetch(url, opts && { headers: { "Content-Type": "application/json" }, ...opts });
  return r.json();
}
const post = (url, body) => api(url, { method: "POST", body: JSON.stringify(body) });

/* ------------------------------------------------------------------ */
/* Estado → payload                                                    */
/* ------------------------------------------------------------------ */
function payload(save = false) {
  const numOrNull = (v) => { const n = NUM(v); return Number.isFinite(n) && String(v).trim() !== "" ? n : null; };
  return {
    A: S.A.map((r) => r.map(numOrNull)), b: S.b.map(numOrNull), x0: S.x0.map(numOrNull),
    tol: numOrNull(S.tol), max_iter: numOrNull(S.maxIter), precond: S.pre,
    scenario_id: S.mode === "scenario" ? S.sid : null, save,
  };
}
function isOriginal() {
  if (S.mode !== "scenario" || !S.sid) return false;
  const sc = S.byId[S.sid];
  const eq = (a, b) => Math.abs(NUM(a) - b) < 1e-12;
  return S.A.every((r, i) => r.every((v, j) => eq(v, sc.A[i][j]))) && S.b.every((v, i) => eq(v, sc.b[i]));
}
function stateLabel() {
  if (S.mode === "manual" || !S.sid) return "Modo manual";
  const sc = S.byId[S.sid];
  return isOriginal() ? `${sc.name} (original)` : `Escenario personalizado (basado en ${sc.short})`;
}
function loadScenario(id) {
  const sc = S.byId[id];
  S.mode = "scenario"; S.sid = id;
  S.A = sc.A.map((r) => r.map(String)); S.b = sc.b.map(String); S.x0 = ["0", "0", "0", "0"];
  syncInputs(); renderStatusTags(); renderPicker();
}

/* ------------------------------------------------------------------ */
/* Editor                                                              */
/* ------------------------------------------------------------------ */
function buildEditor() {
  const gA = $("#gridA"), gB = $("#gridB"), gX = $("#gridX0");
  gA.innerHTML = ""; gB.innerHTML = ""; gX.innerHTML = "";
  for (let i = 0; i < 4; i++) for (let j = 0; j < 4; j++) {
    const inp = document.createElement("input");
    inp.dataset.i = i; inp.dataset.j = j; inp.id = `a_${i}_${j}`; inp.inputMode = "decimal"; inp.ariaLabel = `a${i + 1}${j + 1}`;
    inp.addEventListener("input", () => {
      S.A[i][j] = inp.value;
      if (S.mirror && i !== j) { S.A[j][i] = inp.value; $(`#a_${j}_${i}`).value = inp.value; }
      onEdit();
    });
    gA.appendChild(inp);
  }
  for (let i = 0; i < 4; i++) {
    const b = document.createElement("input"); b.id = `b_${i}`; b.inputMode = "decimal"; b.ariaLabel = `b${i + 1}`;
    b.addEventListener("input", () => { S.b[i] = b.value; onEdit(); }); gB.appendChild(b);
    const x = document.createElement("input"); x.id = `x0_${i}`; x.inputMode = "decimal"; x.ariaLabel = `x0_${i + 1}`;
    x.addEventListener("input", () => { S.x0[i] = x.value; onEdit(); }); gX.appendChild(x);
  }
  $("#inTol").addEventListener("input", (e) => { S.tol = e.target.value; onEdit(); });
  $("#inMax").addEventListener("input", (e) => { S.maxIter = e.target.value; onEdit(); });
  $("#inPre").addEventListener("change", (e) => { S.pre = e.target.value; onEdit(); });
  $("#mirror").addEventListener("change", (e) => { S.mirror = e.target.checked; });
  $("#btnModeScn").onclick = () => { loadScenario(S.sid || "ideal"); runAnalysis(); };
  $("#btnModeMan").onclick = () => { S.mode = "manual"; renderStatusTags(); renderPicker(); onEdit(); };
  $("#btnRestore").onclick = () => {
    if (S.mode !== "scenario") { $("#edErrors").innerHTML = '<div class="note">No hay escenario base en modo manual. Elija un escenario para restaurarlo.</div>'; return; }
    loadScenario(S.sid); runAnalysis();
  };
  $("#btnZeroX0").onclick = () => { S.x0 = ["0", "0", "0", "0"]; syncInputs(); onEdit(); };
  $("#btnRunSave").onclick = () => runAnalysis(true);
  $("#btnSaveScn").onclick = saveOwnScenario;
  $("#btnClearHist").onclick = async () => { if (confirm("¿Vaciar el historial de simulaciones?")) { await api("/api/history", { method: "DELETE" }); loadHistory(); } };
}
function syncInputs() {
  for (let i = 0; i < 4; i++) for (let j = 0; j < 4; j++) $(`#a_${i}_${j}`).value = S.A[i][j];
  for (let i = 0; i < 4; i++) { $(`#b_${i}`).value = S.b[i]; $(`#x0_${i}`).value = S.x0[i]; }
  $("#inTol").value = S.tol; $("#inMax").value = S.maxIter; $("#inPre").value = S.pre; $("#mirror").checked = S.mirror;
}
function markBadInputs() {
  const bad = (el, v) => el.classList.toggle("bad", !(String(v).trim() !== "" && Number.isFinite(NUM(v))));
  for (let i = 0; i < 4; i++) for (let j = 0; j < 4; j++) bad($(`#a_${i}_${j}`), S.A[i][j]);
  for (let i = 0; i < 4; i++) { bad($(`#b_${i}`), S.b[i]); bad($(`#x0_${i}`), S.x0[i]); }
  bad($("#inTol"), S.tol); bad($("#inMax"), S.maxIter);
}
function onEdit() {
  setStale(true); markBadInputs(); renderStatusTags(); renderPicker();
  clearTimeout(S.timer); S.timer = setTimeout(() => runAnalysis(), 350);
}
function setStale(v) {
  S.stale = v;
  document.body.classList.toggle("stale", v);
  $("#staleBanner").classList.toggle("show", v);
  if (v) { $("#okBanner").classList.remove("show"); $("#badBanner").classList.remove("show"); }
}
function renderStatusTags() {
  const l = stateLabel();
  $("#modeTag").textContent = l; $("#edModeTag").textContent = l;
  const orig = isOriginal();
  [$("#modeTag"), $("#edModeTag")].forEach((t) => { t.className = "tag " + (S.mode === "manual" ? "warn" : orig ? "ok" : "info"); });
}
function renderPicker() {
  const box = $("#scnPicker");
  $("#btnModeScn").classList.toggle("active", S.mode === "scenario");
  $("#btnModeMan").classList.toggle("active", S.mode === "manual");
  box.style.display = S.mode === "scenario" ? "flex" : "none";
  box.innerHTML = S.scenarios.map((sc) =>
    `<button class="btn sm ${S.mode === "scenario" && S.sid === sc.id ? "active" : ""}" data-id="${sc.id}"><span class="dot" style="display:inline-block;width:9px;height:9px;border-radius:50%;background:${sc.color}"></span>${esc(sc.name)}</button>`).join("");
  box.querySelectorAll("button").forEach((b) => (b.onclick = () => { loadScenario(b.dataset.id); runAnalysis(); }));
}

/* ------------------------------------------------------------------ */
/* Análisis                                                            */
/* ------------------------------------------------------------------ */
async function runAnalysis(save = false) {
  clearTimeout(S.timer);
  const my = ++S.seq;
  markBadInputs();
  setStale(true);
  let res;
  try { res = await post("/api/analyze", payload(save)); }
  catch (e) { $("#edErrors").innerHTML = `<div class="note bad">No se pudo contactar con el servidor: ${esc(e.message)}</div>`; return; }
  if (my !== S.seq) return; // llegó una respuesta de una versión anterior de los datos: se descarta
  S.result = res;
  renderAll(res);
  setStale(false);
  $("#okBanner").classList.toggle("show", !!res.valid);
  $("#badBanner").classList.toggle("show", !res.valid);
  if (save && res.saved_id) loadHistory();
  refreshCompare();
}
async function refreshCompare() {
  const tol = NUM(S.tol), mi = NUM(S.maxIter);
  if (!(tol > 0 && tol < 1) || !(mi >= 1)) return;
  const key = `${tol}|${mi}|${S.pre}`;
  if (key === S.compareKey && S.compare) return;
  const data = await post("/api/compare", { tol, max_iter: mi, precond: S.pre });
  S.compare = data; S.compareKey = key;
  renderScnCards(); renderCompare(); renderCondChart();
}

/* ------------------------------------------------------------------ */
/* Render general                                                      */
/* ------------------------------------------------------------------ */
function matHTML(M, opts = {}) {
  const rows = M.length, cols = Array.isArray(M[0]) ? M[0].length : 1;
  const flat = Array.isArray(M[0]) ? M.flat() : M;
  const f = opts.f || ((v) => fmt(v, opts.d ?? 4));
  return `<div class="mat ${opts.hl ? "hl" : ""}" style="grid-template-columns:repeat(${cols},auto)">${flat.map((v) => `<span>${f(v)}</span>`).join("")}</div>`;
}
function lab(m, l) { return `<div>${m}<div class="vlabel">${l}</div></div>`; }
function placeholder(msg) { return `<div class="note bad">${esc(msg)}</div>`; }

function renderAll(res) {
  renderStatusTags();
  $("#sigTag").textContent = "firma: " + (res.signature || "—");
  renderErrors(res);
  renderSystem(res);
  renderPropsActive(res);
  renderCholesky(res);
  renderMethods(res);
  renderErrorsModule(res);
  renderConclusions(res);
}
function renderErrors(res) {
  let h = "";
  if (!res.valid) h += res.errors.map((e) => `<div class="note bad"><b>No se ejecutó GC/GCP.</b> ${esc(e.message)}</div>`).join("");
  else if (res.warnings && res.warnings.length) h += res.warnings.map((w) => `<div class="note">${esc(w)}</div>`).join("");
  $("#edErrors").innerHTML = h;
}
function renderSystem(res) {
  const inp = res.inputs || { A: S.A.map((r) => r.map(NUM)), b: S.b.map(NUM) };
  const x = res.valid ? res.cholesky.x : ["x₁", "x₂", "x₃", "x₄"];
  $("#sysVisual").innerHTML =
    lab(matHTML(inp.A, { d: 4 }), "A (4×4)") + '<span class="op">×</span>' +
    lab(matHTML(x, { f: (v) => (typeof v === "string" ? v : fmt(v, 4)) }), res.valid ? "x (solución directa)" : "x (incógnitas)") +
    '<span class="op">=</span>' + lab(matHTML(inp.b, { d: 4 }), "b");
  $("#sysExplain").innerHTML = res.valid
    ? `Cada fila de A multiplica las inversiones x y debe reproducir el requerimiento b. Por ejemplo, la fila 1: ${inp.A[0].map((a, j) => `${fmt(a, 4)}·${fmt(x[j], 3)}`).join(" + ")} = ${fmt(inp.b[0], 4)}.`
    : "Con los datos actuales el sistema no tiene solución calculable (ver validaciones en el Módulo 4).";
}
function spdRow(sp, name) {
  const t = (b) => `<span class="tag ${b ? "ok" : "bad"}">${b ? "Sí" : "No"}</span>`;
  const eig = sp.eigenvalues ? sp.eigenvalues.map((v) => fmt(v, 4)).join(" · ") : "— (no simétrica)";
  const min = sp.minors ? sp.minors.map((m) => `Δ${m.k}=${fmt(m.det, 4)}`).join(" · ") : "—";
  return `<tr>${name ? `<td>${esc(name)}</td>` : ""}<td>${t(sp.square)}</td><td>${t(sp.symmetric)}</td><td class="mono">${eig}</td><td class="mono">${min}</td>${name ? `<td>${t(sp.cholesky_ok)}</td>` : ""}<td>${t(sp.spd)}</td></tr>`;
}
function renderProps() {
  $("#propsTable tbody").innerHTML = S.props.map((p) => spdRow(p.spd, p.name)).join("");
}
function renderPropsActive(res) {
  $("#propsActive tbody").innerHTML = res.spd ? spdRow(res.spd) : `<tr><td colspan="5" class="txt">No se pudo evaluar: ${esc(res.errors.map((e) => e.message).join(" "))}</td></tr>`;
}
function renderCholesky(res) {
  if (!res.valid) {
    $("#cholMats").innerHTML = placeholder("Sin factorización: los datos actuales no son válidos (A debe ser simétrica y definida positiva).");
    $("#fwdSteps").textContent = ""; $("#bwdSteps").textContent = ""; $("#cholSummary").innerHTML = ""; return;
  }
  const c = res.cholesky;
  $("#cholMats").innerHTML = lab(matHTML(res.inputs.A, { d: 4 }), "A") + '<span class="op">=</span>' + lab(matHTML(c.L, { d: 5 }), "L") + '<span class="op">·</span>' + lab(matHTML(c.Lt, { d: 5 }), "Lᵀ");
  $("#fwdSteps").textContent = c.forward_steps.join("\n");
  $("#bwdSteps").textContent = c.backward_steps.join("\n");
  $("#cholSummary").innerHTML =
    `<div class="card"><h4>Vector solución x</h4><div class="eq">${matHTML(c.x, { d: 8 })}</div><p>miles de Bs</p></div>` +
    `<div class="card"><h4>Comprobación</h4><p>‖b − A·x‖/‖b‖ = <code>${sci(c.check_rel)}</code></p><p>máx|L·Lᵀ − A| = <code>${sci(c.factor_check)}</code></p></div>` +
    `<div class="card"><h4>Vector intermedio y</h4><div class="eq">${matHTML(c.y, { d: 6 })}</div></div>`;
}
function tag(ok, y = "Sí", n = "No") { return `<span class="tag ${ok ? "ok" : "bad"}">${ok ? y : n}</span>`; }
function iterTable(m) {
  const head = `<thead><tr><th>k</th><th>x₁</th><th>x₂</th><th>x₃</th><th>x₄</th><th>‖r‖₂</th><th>‖r‖/‖b‖</th><th>α</th><th>β</th><th>Estado</th></tr></thead>`;
  const rows = m.rows.map((r) => `<tr class="${r.status === "convergió" ? "good" : ""}"><td>${r.k}</td>${r.x.map((v) => `<td class="num">${fmt(v, 6)}</td>`).join("")}<td class="num">${sci(r.residual)}</td><td class="num">${sci(r.rel_residual)}</td><td class="num">${r.alpha == null ? "—" : fmt(r.alpha, 5)}</td><td class="num">${r.beta == null ? "—" : fmt(r.beta, 5)}</td><td>${r.status}</td></tr>`).join("");
  return head + `<tbody>${rows}</tbody>`;
}
function renderMethods(res) {
  if (!res.valid) {
    $("#methodCards").innerHTML = placeholder("GC y GCP no se ejecutaron: " + res.errors.map((e) => e.message).join(" "));
    $("#tblGC").innerHTML = ""; $("#tblGCP").innerHTML = ""; destroyChart("chResid"); return;
  }
  const pn = res.inputs.precond === "jacobi" ? "GCP-Jacobi" : "GCP (sin precond.)";
  const card = (t, v, sub) => `<div class="card kpi"><div class="l">${t}</div><div class="v">${v}</div><div class="l">${sub}</div></div>`;
  $("#methodCards").innerHTML =
    card("GC · iteraciones", res.gc.iterations, tag(res.gc.converged, "convergió", "no convergió")) +
    card(`${pn} · iteraciones`, res.gcp.iterations, tag(res.gcp.converged, "convergió", "no convergió")) +
    card("GC · residuo relativo real", sci(res.gc.final_rel_residual), esc(res.gc.reason)) +
    card(`${pn} · residuo relativo real`, sci(res.gcp.final_rel_residual), esc(res.gcp.reason));
  $("#tblGC").innerHTML = iterTable(res.gc); $("#tblGCP").innerHTML = iterTable(res.gcp);
  const clamp = (v) => Math.max(v, 1e-17);
  lineChart("chResid", "Iteración k", "‖r‖₂ (residuo real)", [
    { label: "GC", data: res.gc.rows.map((r) => ({ x: r.k, y: clamp(r.residual) })), borderColor: C.cyan, backgroundColor: C.cyan },
    { label: pn, data: res.gcp.rows.map((r) => ({ x: r.k, y: clamp(r.residual) })), borderColor: C.violet, backgroundColor: C.violet },
  ]);
}
function renderErrorsModule(res) {
  if (!res.valid) {
    $("#metricCards").innerHTML = ""; $("#tblErr").innerHTML = ""; $("#expectedBox").innerHTML = placeholder("Sin comparación: datos no válidos.");
    ["chConv", "chErr", "chInv"].forEach(destroyChart); return;
  }
  const c = res.cond;
  const card = (t, v, s) => `<div class="card kpi"><div class="l">${t}</div><div class="v" style="font-size:1.4rem">${v}</div><div class="l">${s}</div></div>`;
  $("#metricCards").innerHTML =
    card("κ₂(A)", fmt(c.kappa_A, 4), "número de condición") +
    card("κ precondicionado", fmt(c.kappa_M, 4), res.inputs.precond === "jacobi" ? "M^(−1/2)·A·M^(−1/2)" : "sin precondicionador (=κ(A))") +
    card("Iteraciones GC / GCP", `${res.gc.iterations} / ${res.gcp.iterations}`, "tolerancia " + Number(res.inputs.tol).toExponential(0)) +
    card("Residuo relativo final", `${sci(res.gc.final_rel_residual)} · ${sci(res.gcp.final_rel_residual)}`, "GC · GCP") +
    card("Convergencia", `${res.gc.converged ? "GC ✔" : "GC ✖"} · ${res.gcp.converged ? "GCP ✔" : "GCP ✖"}`, "según residuo real");
  const na = '<span title="x_ref = 0: error relativo no definido">no definido</span>';
  const rows = res.errors_gc.map((g, i) => {
    const p = res.errors_gcp[i];
    return `<tr><td>${esc(AREAS[i])} (x${i + 1})</td><td class="num">${fmt(g.x_ref, 8)}</td><td class="num">${fmt(g.x_calc, 8)}</td><td class="num">${fmt(p.x_calc, 8)}</td>` +
      `<td class="num">${sci(g.ea)}</td><td class="num">${g.er == null ? na : sci(g.er)}</td><td class="num">${g.ep == null ? na : sci(g.ep) + " %"}</td>` +
      `<td class="num">${sci(p.ea)}</td><td class="num">${p.er == null ? na : sci(p.er)}</td><td class="num">${p.ep == null ? na : sci(p.ep) + " %"}</td></tr>`;
  }).join("");
  $("#tblErr").innerHTML = `<thead><tr><th>Variable</th><th>x_ref (Cholesky)</th><th>x GC</th><th>x GCP</th><th>Ea GC</th><th>Er GC</th><th>Ep GC</th><th>Ea GCP</th><th>Er GCP</th><th>Ep GCP</th></tr></thead><tbody>${rows}</tbody>`;
  if (res.expected) {
    $("#expectedBox").innerHTML = `<div class="note info" style="margin-top:12px">Solución esperada del escenario (calculada de forma independiente): <code>[${res.expected.x.join(", ")}]</code>. Diferencia máxima con la solución de Cholesky: <code>${sci(res.expected.max_diff_direct)}</code>.</div>`;
  } else {
    $("#expectedBox").innerHTML = `<div class="note" style="margin-top:12px">Datos personalizados o manuales: no hay solución esperada predefinida; la referencia es la solución directa de Cholesky.</div>`;
  }
  const clamp = (v) => Math.max(v, 1e-17);
  lineChart("chConv", "Iteración k", "‖r‖/‖b‖", [
    { label: "GC", data: res.gc.rows.map((r) => ({ x: r.k, y: clamp(r.rel_residual) })), borderColor: C.cyan, backgroundColor: C.cyan },
    { label: res.inputs.precond === "jacobi" ? "GCP-Jacobi" : "GCP", data: res.gcp.rows.map((r) => ({ x: r.k, y: clamp(r.rel_residual) })), borderColor: C.violet, backgroundColor: C.violet },
    { label: "Tolerancia", data: [{ x: 0, y: res.inputs.tol }, { x: Math.max(res.gc.iterations, res.gcp.iterations, 1), y: res.inputs.tol }], borderColor: C.amber, borderDash: [6, 4], pointRadius: 0 },
  ]);
  barChart("chErr", AREAS, [
    { label: "Ea GC", data: res.errors_gc.map((e) => clamp(e.ea)), backgroundColor: C.cyan },
    { label: "Ea GCP", data: res.errors_gcp.map((e) => clamp(e.ea)), backgroundColor: C.violet },
  ], true, "Error absoluto (escala log; piso 1e-17 si es 0)");
  barChart("chInv", AREAS, [
    { label: "Referencia (Cholesky)", data: res.cholesky.x, backgroundColor: C.blue },
    { label: "GCP", data: res.gcp.x, backgroundColor: C.violet },
  ], false, "Miles de Bs");
}
function renderConclusions(res) {
  const c = res.conclusions;
  $("#conclTag").className = "tag " + (c.status === "ok" ? "ok" : "bad");
  $("#conclTag").textContent = (c.status === "ok" ? "Generadas con resultados vigentes · " : "Sin ejecución válida · ") + c.label;
  const blk = (t, arr, ic) => `<div class="card"><h4>${t}</h4>${arr.map((p) => `<p>${esc(p)}</p>`).join("")}</div>`;
  $("#conclGrid").innerHTML = blk("A. Conclusión matemática", c.math) + blk("B. Conclusión financiera", c.financial) + blk("C. Comparación de métodos", c.comparison) + blk("D. Conclusión general", c.general);
  const lst = (t, arr) => `<div class="card"><h4>${t}</h4><ul class="clean">${arr.map((p) => `<li>${esc(p)}</li>`).join("")}</ul></div>`;
  $("#recGrid").innerHTML = lst("Recomendaciones matemáticas", c.rec_math) + lst("Recomendaciones financieras", c.rec_fin);
}

/* ------------------------------------------------------------------ */
/* Escenarios y comparación                                            */
/* ------------------------------------------------------------------ */
function renderScnCards() {
  const cmp = S.compare ? Object.fromEntries(S.compare.map((e) => [e.id, e])) : {};
  $("#scnCards").innerHTML = S.scenarios.map((sc) => {
    const e = cmp[sc.id];
    const res = e && e.valid
      ? `<p><b>Resultados (datos originales):</b><br>x_ref = <code>[${e.x_ref.map((v) => fmt(v, 4)).join("; ")}]</code><br>GC ${e.it_gc} it · GCP ${e.it_gcp} it ${tag(e.conv_gc && e.conv_gcp, "convergen", "no convergen")}<br>κ(A) = <code>${fmt(e.kappa_A, 4)}</code> → κ precond. = <code>${fmt(e.kappa_M, 4)}</code></p>`
      : `<p class="lead">${e ? "Datos no válidos." : "Calculando…"}</p>`;
    return `<div class="card scn-card"><h3><span class="dot" style="background:${sc.color}"></span>${esc(sc.name)}</h3><p>${esc(sc.description)}</p>
      <h4>Matriz A</h4><div class="eq">${matHTML(sc.A, { d: 4 })}</div><h4>Vector b</h4><div class="eq">${matHTML(sc.b, { d: 4 })}</div>
      <p><b>Solución esperada:</b> <code>[${sc.expected.join(", ")}]</code></p><p><b>Justificación:</b> ${esc(sc.justification)}</p>${res}
      <button class="btn primary" data-load="${sc.id}">Cargar y ejecutar</button></div>`;
  }).join("");
  $$("#scnCards [data-load]").forEach((b) => (b.onclick = () => { loadScenario(b.dataset.load); runAnalysis(); document.getElementById("m7").scrollIntoView(); }));
}
function renderCompare() {
  const d = S.compare; if (!d) return;
  const col = (fn) => d.map((e) => `<td class="txt">${e.valid ? fn(e) : '<span class="tag bad">datos no válidos</span>'}</td>`).join("");
  const vec = (v, dg = 4) => `<code>[${v.map((x) => fmt(x, dg)).join("; ")}]</code>`;
  const row = (t, fn) => `<tr><td>${t}</td>${col(fn)}</tr>`;
  $("#tblCompare").innerHTML = `<thead><tr><th>Indicador</th>${d.map((e) => `<th style="text-align:left"><span class="dot" style="display:inline-block;width:9px;height:9px;border-radius:50%;background:${e.color}"></span> ${esc(e.short)}</th>`).join("")}</tr></thead><tbody>` +
    row("Solución numérica de referencia", (e) => vec(e.x_ref)) +
    row("Solución GCP", (e) => vec(e.x_gcp)) +
    row("Solución GC", (e) => vec(e.x_gc)) +
    row("Error absoluto (Ea) GCP", (e) => `<code>[${e.errors_gcp.map((x) => sci(x.ea)).join("; ")}]</code>`) +
    row("Error porcentual (Ep) GCP", (e) => `<code>[${e.errors_gcp.map((x) => (x.ep == null ? "n/d" : sci(x.ep) + "%")).join("; ")}]</code>`) +
    row("Iteraciones GC (sin precondicionar)", (e) => e.it_gc) +
    row("Iteraciones GCP (precondicionado)", (e) => e.it_gcp) +
    row("Número de condición κ(A)", (e) => fmt(e.kappa_A, 4)) +
    row("Número de condición κ(M⁻¹A)", (e) => fmt(e.kappa_M, 4)) +
    row("Residuo relativo final GCP", (e) => sci(e.rel_gcp)) +
    row("¿Convergió el algoritmo?", (e) => `GC: ${e.conv_gc ? "Sí" : "No"} · GCP: ${e.conv_gcp ? "Sí" : "No"}`) +
    row("Interpretación financiera", (e) => esc(e.brief)) + "</tbody>";
}
function renderCondChart() {
  const d = S.compare; if (!d) return;
  const ok = d.filter((e) => e.valid);
  barChart("chCond", ok.map((e) => e.short), [
    { label: "κ(A)", data: ok.map((e) => e.kappa_A), backgroundColor: C.blue },
    { label: "κ precondicionado", data: ok.map((e) => e.kappa_M), backgroundColor: C.cyan },
  ], true, "Número de condición (log)");
}

/* ------------------------------------------------------------------ */
/* Gráficos                                                            */
/* ------------------------------------------------------------------ */
Chart.defaults.color = "#9fb0d8"; Chart.defaults.borderColor = "rgba(120,160,255,.15)";
Chart.defaults.font.family = "system-ui,sans-serif";
const logTick = (v) => { const e = Math.log10(v); return Math.abs(e - Math.round(e)) < 1e-9 ? "1e" + Math.round(e) : ""; };
function destroyChart(id) { if (S.charts[id]) { S.charts[id].destroy(); delete S.charts[id]; } }
function lineChart(id, xt, yt, datasets) {
  destroyChart(id);
  S.charts[id] = new Chart($("#" + id), {
    type: "line",
    data: { datasets: datasets.map((d) => ({ tension: 0.15, pointRadius: 4, borderWidth: 2, ...d })) },
    options: { responsive: true, maintainAspectRatio: false, parsing: false,
      scales: { x: { type: "linear", title: { display: true, text: xt }, ticks: { precision: 0, stepSize: 1 } }, y: { type: "logarithmic", title: { display: true, text: yt }, ticks: { callback: logTick } } },
      plugins: { legend: { position: "bottom" }, tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${Number(c.parsed.y).toExponential(3)}` } } } },
  });
}
function barChart(id, labels, datasets, log, yt) {
  destroyChart(id);
  S.charts[id] = new Chart($("#" + id), {
    type: "bar", data: { labels, datasets },
    options: { responsive: true, maintainAspectRatio: false,
      scales: { y: { type: log ? "logarithmic" : "linear", title: { display: true, text: yt }, ticks: log ? { callback: logTick } : {} } },
      plugins: { legend: { position: "bottom" } } },
  });
}

/* ------------------------------------------------------------------ */
/* Historial y escenarios propios                                      */
/* ------------------------------------------------------------------ */
function loadRecord(r) {
  S.mode = r.scenario_id && S.byId[r.scenario_id] ? "scenario" : "manual"; S.sid = S.mode === "scenario" ? r.scenario_id : S.sid;
  S.A = r.a.map((row) => row.map(String)); S.b = r.b.map(String); S.x0 = r.x0.map(String);
  S.tol = String(r.tol); S.maxIter = String(r.max_iter); S.pre = r.precond;
  syncInputs(); renderStatusTags(); renderPicker(); runAnalysis();
  document.getElementById("m4").scrollIntoView();
}
async function loadHistory() {
  const h = await api("/api/history");
  S.hist = h;
  $("#histTable tbody").innerHTML = h.length ? h.map((r) => `<tr><td>${r.id}</td><td>${esc(r.created_at)}</td><td class="txt">${esc(r.label)}</td><td>${r.it_gc}/${r.it_gcp} ${r.conv_gc && r.conv_gcp ? "✔" : "✖"}</td><td class="num">${fmt(r.kappa_a, 3)}</td><td><button class="btn sm" data-h="${r.id}">Cargar</button> <button class="btn sm danger" data-d="${r.id}">✕</button></td></tr>`).join("") : `<tr><td colspan="6" class="txt">Sin registros. Use «Ejecutar y guardar en historial».</td></tr>`;
  $$("#histTable [data-h]").forEach((b) => (b.onclick = () => loadRecord(h.find((r) => r.id == b.dataset.h))));
  $$("#histTable [data-d]").forEach((b) => (b.onclick = async () => { await api("/api/history/" + b.dataset.d, { method: "DELETE" }); loadHistory(); }));
}
async function loadSaved() {
  const s = await api("/api/saved"); S.saved = s;
  $("#savedList").innerHTML = s.length ? s.map((r) => `<div class="status" style="margin:4px 0"><b>${esc(r.name)}</b><span class="tag">${esc(r.created_at)}</span><span class="spacer"></span><button class="btn sm" data-s="${r.id}">Cargar</button><button class="btn sm danger" data-x="${r.id}">✕</button></div>`).join("") : "Aún no hay escenarios propios. Edite datos y use «Guardar como escenario propio».";
  $$("#savedList [data-s]").forEach((b) => (b.onclick = () => { const r = s.find((q) => q.id == b.dataset.s); loadRecord({ ...r, scenario_id: r.base_scenario, label: r.name }); }));
  $$("#savedList [data-x]").forEach((b) => (b.onclick = async () => { await api("/api/saved/" + b.dataset.x, { method: "DELETE" }); loadSaved(); }));
}
async function saveOwnScenario() {
  const name = prompt("Nombre del escenario propio:"); if (!name) return;
  const r = await post("/api/saved", { name, ...payload(false) });
  if (!r.ok) $("#edErrors").innerHTML = r.errors.map((e) => `<div class="note bad">${esc(e.message)}</div>`).join("");
  else loadSaved();
}

/* ------------------------------------------------------------------ */
/* QA                                                                  */
/* ------------------------------------------------------------------ */
function clientTest10() {
  const res = S.result, base = { id: 10, name: "Actualización de gráficos, tablas e interpretaciones", data: "Resultado activo en pantalla", expected: "Gráficos, tablas, firma y conclusiones coinciden con el último cálculo" };
  if (!res || !res.valid || S.stale) return { ...base, obtained: "No hay un resultado vigente y válido en pantalla", status: "fallida", explanation: "Se requiere un cálculo válido y actualizado para verificar la interfaz." };
  const checks = [
    ["gráfico de residuos (GC)", S.charts.chResid && S.charts.chResid.data.datasets[0].data.length === res.gc.rows.length],
    ["gráfico de residuos (GCP)", S.charts.chResid && S.charts.chResid.data.datasets[1].data.length === res.gcp.rows.length],
    ["tabla GC", $("#tblGC tbody").children.length === res.gc.rows.length],
    ["tabla GCP", $("#tblGCP tbody").children.length === res.gcp.rows.length],
    ["tabla de errores", $("#tblErr tbody").children.length === 4 && $("#tblErr tbody").rows[0].cells[3].textContent === fmt(res.gcp.x[0], 8)],
    ["firma visible", $("#sigTag").textContent.includes(res.signature)],
    ["κ(A) visible", $("#metricCards").textContent.includes(fmt(res.cond.kappa_A, 4))],
    ["conclusión matemática", $("#conclGrid").textContent.includes(res.conclusions.math[0].slice(0, 60))],
    ["conclusión financiera", $("#conclGrid").textContent.includes(res.conclusions.financial[0].slice(0, 60))],
  ];
  const failed = checks.filter((c) => !c[1]).map((c) => c[0]);
  return { ...base, obtained: `${checks.length - failed.length}/${checks.length} comprobaciones en el DOM` + (failed.length ? ` · fallan: ${failed.join(", ")}` : ""), status: failed.length ? "fallida" : "aprobada", explanation: "Se compara el contenido real de gráficos, tablas y textos con el resultado del último cálculo." };
}
async function runQA() {
  $("#qaSummary").textContent = "Ejecutando…"; $("#qaSummary").className = "tag warn";
  const tests = await post("/api/qa/run", {});
  const out = tests.map((t) => (t.client ? { ...t, ...clientTest10() } : t));
  const cls = { aprobada: "qa-pass", fallida: "qa-fail", pendiente: "qa-pend" };
  $("#tblQA tbody").innerHTML = out.map((t) => `<tr><td>${t.id}</td><td class="txt"><b>${esc(t.name)}</b></td><td class="txt">${esc(t.data)}</td><td class="txt">${esc(t.expected)}</td><td class="txt mono" style="font-size:.76rem">${esc(t.obtained)}</td><td class="${cls[t.status]}">${t.status === "aprobada" ? "✔ APROBADA" : t.status === "fallida" ? "✖ FALLIDA" : "… PENDIENTE"}</td><td class="txt">${esc(t.explanation)}</td></tr>`).join("");
  const ok = out.filter((t) => t.status === "aprobada").length;
  $("#qaSummary").textContent = `${ok}/${out.length} aprobadas`; $("#qaSummary").className = "tag " + (ok === out.length ? "ok" : "bad");
}

/* ------------------------------------------------------------------ */
/* Navegación                                                          */
/* ------------------------------------------------------------------ */
function setupNav() {
  const links = $$("#nav a");
  const obs = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) links.forEach((l) => l.classList.toggle("active", l.getAttribute("href") === "#" + e.target.id)); }), { rootMargin: "-30% 0px -60% 0px" });
  $$("section.module").forEach((s) => obs.observe(s));
  $("#menuBtn").onclick = () => $("#sidebar").classList.toggle("open");
  links.forEach((l) => l.addEventListener("click", () => $("#sidebar").classList.remove("open")));
}

/* ------------------------------------------------------------------ */
async function init() {
  setupNav(); buildEditor();
  $("#btnQA").onclick = runQA;
  const d = await api("/api/scenarios");
  S.scenarios = d.scenarios; S.byId = Object.fromEntries(d.scenarios.map((s) => [s.id, s])); S.props = d.properties; S.defaults = d.defaults;
  renderProps(); renderScnCards();
  loadScenario("ideal");
  loadHistory(); loadSaved();
  await runAnalysis();
}
init();
