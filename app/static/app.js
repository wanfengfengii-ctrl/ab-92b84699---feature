"use strict";

// ---- 状态 ----
let records = [
  { r1: 1, c1: 1, r2: 2, c2: 2, count: 1 },
  { r1: 2, c1: 2, r2: 3, c2: 3, count: 0 },
  { r1: 3, c1: 3, r2: 4, c2: 4, count: 1 },
];

// 最近一次成功提交、与页面结论一致的请求载荷；规划只能基于它重新发起。
let activePayload = null;

const $ = (id) => document.getElementById(id);
const rowsInput = $("rows");
const colsInput = $("cols");
const recordsEl = $("records");
const addBtn = $("add-btn");
const submitBtn = $("submit-btn");
const formError = $("form-error");

const placeholder = $("result-placeholder");
const staleBanner = $("result-stale");
const resultError = $("result-error");
const resultOk = $("result-ok");
const errorText = $("error-text");

const planBtn = $("plan-btn");
const planPlaceholder = $("plan-placeholder");
const planFail = $("plan-fail");
const planResult = $("plan-result");
const patchRows = $("patch-rows");
const patchOverlay = $("patch-overlay");

// 网格几何，须与 style.css / 内联网格样式保持一致。
const CELL_W = 64;
const CELL_H = 52;
const CELL_GAP = 5;
const PATCH_COLORS = ["#1f6f5c", "#2b5aa0", "#b05a00", "#7a2f8f", "#9a2f4e", "#0f7a7a", "#5a6b12", "#8a4a1f"];

// ---- 旧结论与旧规划清除 ----
function clearPlan(opts = {}) {
  planResult.hidden = true;
  planFail.hidden = true;
  planPlaceholder.hidden = true;
  planBtn.disabled = false;
  patchOverlay.innerHTML = "";
  if (opts.planFail) {
    planFail.textContent = opts.planFail;
    planFail.hidden = false;
  } else {
    planPlaceholder.hidden = false;
  }
}

function clearConclusion(opts = {}) {
  resultOk.hidden = true;
  resultError.hidden = true;
  formError.hidden = true;
  placeholder.hidden = true;
  staleBanner.hidden = true;
  activePayload = null;
  clearPlan();
  if (opts.stale) {
    staleBanner.hidden = false;
  } else if (opts.error) {
    resultError.hidden = false;
    errorText.textContent = opts.error;
  } else {
    placeholder.hidden = false;
  }
}

// 任何检测资料修改都使旧结论与既有规划立即失效。
function markStale() {
  clearConclusion({ stale: true });
}

// ---- 检测记录编辑 ----
function renderRecords() {
  recordsEl.innerHTML = "";
  records.forEach((rec, idx) => {
    const li = document.createElement("li");
    li.className = "record";

    const head = document.createElement("span");
    head.className = "idx";
    head.textContent = `#${idx + 1}`;
    li.appendChild(head);

    const fields = [
      ["r1", "上行"], ["c1", "左列"],
      ["r2", "下行"], ["c2", "右列"],
    ];
    fields.forEach(([key, label], fi) => {
      if (fi === 2) {
        const arrow = document.createElement("span");
        arrow.className = "sep";
        arrow.textContent = "→";
        li.appendChild(arrow);
      }
      const lab = document.createElement("label");
      const span = document.createElement("span");
      span.className = "sep";
      span.textContent = label;
      const inp = document.createElement("input");
      inp.type = "number";
      inp.min = "1";
      inp.max = "5";
      inp.step = "1";
      inp.value = rec[key];
      inp.addEventListener("input", () => {
        rec[key] = inp.value === "" ? "" : Number(inp.value);
        markStale();
      });
      lab.append(span, inp);
      li.appendChild(lab);
    });

    const countLab = document.createElement("label");
    const countSpan = document.createElement("span");
    countSpan.className = "sep";
    countSpan.textContent = "空鼓数";
    const countInp = document.createElement("input");
    countInp.type = "number";
    countInp.className = "count-input";
    countInp.min = "0";
    countInp.step = "1";
    countInp.value = rec.count;
    countInp.addEventListener("input", () => {
      rec.count = countInp.value === "" ? "" : Number(countInp.value);
      markStale();
    });
    countLab.append(countSpan, countInp);
    li.appendChild(countLab);

    const del = document.createElement("button");
    del.type = "button";
    del.className = "del";
    del.textContent = "删除";
    del.title = "删除该检测记录";
    del.addEventListener("click", () => {
      records.splice(idx, 1);
      renderRecords();
      markStale();
    });
    li.appendChild(del);

    recordsEl.appendChild(li);
  });
  addBtn.disabled = records.length >= 12;
}

addBtn.addEventListener("click", () => {
  if (records.length >= 12) return;
  const rows = Number(rowsInput.value);
  const cols = Number(colsInput.value);
  records.push({ r1: 1, c1: 1, r2: rows || 4, c2: cols || 4, count: 0 });
  renderRecords();
  markStale();
});

[rowsInput, colsInput].forEach((inp) =>
  inp.addEventListener("input", () => {
    markStale();
  })
);

// ---- 修补片边界叠加 ----
function drawPatchOverlay(rows, cols, pieces) {
  const width = cols * CELL_W + (cols - 1) * CELL_GAP;
  const height = rows * CELL_H + (rows - 1) * CELL_GAP;
  patchOverlay.innerHTML = "";
  patchOverlay.setAttribute("viewBox", `0 0 ${width} ${height}`);
  patchOverlay.style.width = `${width}px`;
  patchOverlay.style.height = `${height}px`;

  pieces.forEach((p, i) => {
    const x = (p.c1 - 1) * (CELL_W + CELL_GAP) + 2;
    const y = (p.r1 - 1) * (CELL_H + CELL_GAP) + 2;
    const w = (p.c2 - p.c1 + 1) * CELL_W + (p.c2 - p.c1) * CELL_GAP - 4;
    const h = (p.r2 - p.r1 + 1) * CELL_H + (p.r2 - p.r1) * CELL_GAP - 4;
    const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    rect.setAttribute("x", x);
    rect.setAttribute("y", y);
    rect.setAttribute("width", w);
    rect.setAttribute("height", h);
    rect.setAttribute("rx", "6");
    rect.setAttribute("fill", "none");
    rect.setAttribute("stroke", PATCH_COLORS[i % PATCH_COLORS.length]);
    rect.setAttribute("stroke-width", "3");
    const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
    title.textContent =
      `第 ${i + 1} 片：行${p.r1}–${p.r2}、列${p.c1}–${p.c2}，` +
      `${p.cells} 块空鼓砖，切缝长度 ${p.cut_length}`;
    rect.appendChild(title);
    patchOverlay.appendChild(rect);
  });
}

// ---- 规划渲染 ----
function renderPlan(rows, cols, plan) {
  clearPlan();
  if (!plan || plan.piece_count === 0) {
    planResult.hidden = false;
    planPlaceholder.hidden = true;
    $("plan-piece-count").textContent = "0";
    $("plan-total-cut").textContent = "0";
    $("patch-total-cells").textContent = "0";
    $("patch-total-cut").textContent = "0";
    patchRows.innerHTML = "";
    // 无空鼓砖：以提示替代空表。
    const note = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = 5;
    td.className = "plan-empty";
    td.textContent = "当前结论下没有空鼓砖，无需揭除修补。";
    note.appendChild(td);
    patchRows.appendChild(note);
    return;
  }

  planResult.hidden = false;
  planPlaceholder.hidden = true;
  $("plan-piece-count").textContent = String(plan.piece_count);
  $("plan-total-cut").textContent = String(plan.total_cut_length);

  patchRows.innerHTML = "";
  let totalCells = 0;
  plan.pieces.forEach((p, i) => {
    totalCells += p.cells;
    const tr = document.createElement("tr");
    const vals = [
      String(i + 1),
      `(${p.r1}, ${p.c1})`,
      `(${p.r2}, ${p.c2})`,
      String(p.cells),
      String(p.cut_length),
    ];
    vals.forEach((v) => {
      const td = document.createElement("td");
      td.textContent = v;
      tr.appendChild(td);
    });
    patchRows.appendChild(tr);
  });
  $("patch-total-cells").textContent = String(totalCells);
  $("patch-total-cut").textContent = String(plan.total_cut_length);
  drawPatchOverlay(rows, cols, plan.pieces);
}

// ---- 结果渲染 ----
function renderConclusion(data, submittedPayload) {
  clearConclusion();
  resultOk.hidden = false;
  activePayload = submittedPayload;

  $("total-hollow").textContent = String(data.total);

  const grid = $("brick-grid");
  grid.innerHTML = "";
  grid.style.gridTemplateColumns = `repeat(${data.cols}, 64px)`;
  data.grid.forEach((row, r) => {
    row.forEach((v, c) => {
      const cell = document.createElement("div");
      cell.className = "brick" + (v === 1 ? " hollow" : "");
      cell.textContent = `${r + 1},${c + 1}`;
      cell.title = v === 1 ? `第 ${r + 1} 行第 ${c + 1} 列：空鼓` : `第 ${r + 1} 行第 ${c + 1} 列：完好`;
      grid.appendChild(cell);
    });
  });

  const list = $("count-list");
  list.innerHTML = "";
  data.actual_counts.forEach((actual, i) => {
    const rec = submittedPayload.rects[i];
    const li = document.createElement("li");
    const coords = document.createElement("span");
    coords.className = "coords";
    coords.textContent =
      `区域 行${rec.r1}–${rec.r2}、列${rec.c1}–${rec.c2}：记录 ${rec.count}，实际 ${actual}　`;
    const tag = document.createElement("span");
    tag.className = "match";
    tag.textContent = actual === rec.count ? "✓ 一致" : "✗ 不一致";
    li.append(coords, tag);
    list.appendChild(li);
  });
}

// ---- 提交 ----
function clientValidate() {
  const errs = [];
  const rows = Number(rowsInput.value);
  const cols = Number(colsInput.value);
  if (!Number.isInteger(rows) || rows < 4 || rows > 5) errs.push("行数必须为 4 或 5");
  if (!Number.isInteger(cols) || cols < 4 || cols > 5) errs.push("列数必须为 4 或 5");
  if (records.length < 3 || records.length > 12) errs.push("检测记录必须为 3 至 12 条");
  if (errs.length > 0) return { errs, rows, cols, payloadRects: [] };

  const payloadRects = [];
  records.forEach((rec, i) => {
    const where = `第 ${i + 1} 条记录`;
    const vals = {};
    let allInts = true;
    for (const k of ["r1", "c1", "r2", "c2", "count"]) {
      const n = rec[k];
      if (!Number.isInteger(n)) {
        errs.push(`${where}：${k} 必须填整数`);
        allInts = false;
      }
      vals[k] = n;
    }
    if (!allInts) {
      payloadRects.push(vals);
      return;
    }
    const { r1, c1, r2, c2, count } = vals;
    if (!(r1 >= 1 && r2 <= rows && r1 <= r2)) errs.push(`${where}：行范围需在 1..${rows} 且上≤下`);
    if (!(c1 >= 1 && c2 <= cols && c1 <= c2)) errs.push(`${where}：列范围需在 1..${cols} 且左≤右`);
    const area = Math.max(r2 - r1 + 1, 0) * Math.max(c2 - c1 + 1, 0);
    if (!(count >= 0 && count <= area)) errs.push(`${where}：空鼓计数需在 0..${area}`);
    payloadRects.push(vals);
  });

  return { errs, rows, cols, payloadRects };
}

submitBtn.addEventListener("click", async () => {
  const { errs, rows, cols, payloadRects } = clientValidate();
  if (errs.length > 0) {
    clearConclusion({
      error: "服务端拒绝了本次提交（输入不合法），无法满足全部记录：\n" + errs.map((e) => "· " + e).join("\n"),
    });
    return;
  }

  submitBtn.disabled = true;
  try {
    const resp = await fetch("/api/solve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rows, cols, rects: payloadRects }),
    });
    let data = null;
    try {
      data = await resp.json();
    } catch (_e) {
      data = null;
    }

    if (resp.ok && data && data.status === "ok") {
      renderConclusion(data, { rows, cols, rects: payloadRects });
      return;
    }
    if (resp.ok && data && data.status === "unsat") {
      clearConclusion({
        error:
          "全部检测记录在逻辑上互不相容：不存在任何一种空鼓分布能使每个矩形区域的空鼓计数同时等于记录值。" +
          "请核对敲击记录后重新提交。",
      });
      return;
    }
    // 服务端拒绝（400 等）：旧结论已清除。
    const detail =
      data && Array.isArray(data.errors) && data.errors.length > 0
        ? data.errors.map((e) => "· " + e).join("\n")
        : "服务端未能处理该请求。";
    clearConclusion({
      error: "服务端拒绝了本次提交，无法满足全部记录：\n" + detail,
    });
  } catch (e) {
    clearConclusion({
      error: "无法连接反演服务，本次未获得判定结论，旧结论不再显示。请确认服务可用后重试。",
    });
  } finally {
    submitBtn.disabled = false;
  }
});

// ---- 最小切缝修补规划 ----
planBtn.addEventListener("click", async () => {
  if (!activePayload) return;  // 结论已失效，按钮所在区域本应不可见。
  planBtn.disabled = true;
  clearPlan();
  planPlaceholder.hidden = true;
  try {
    const resp = await fetch("/api/plan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(activePayload),  // 仅原始检测记录，网格由服务端反演。
    });
    let data = null;
    try {
      data = await resp.json();
    } catch (_e) {
      data = null;
    }

    if (resp.ok && data && data.status === "ok" && data.plan) {
      renderPlan(data.rows, data.cols, data.plan);
      return;
    }
    if (resp.ok && data && data.status === "unsat") {
      // 服务端重新反演失败：清除旧规划并明确说明。
      clearPlan({
        planFail:
          "服务端依据当前全部检测记录重新反演时判定无解（无法满足全部记录），" +
          "无法生成最小切缝修补规划，既有规划已清除。请核对检测记录后重新提交。",
      });
      return;
    }
    const detail =
      data && Array.isArray(data.errors) && data.errors.length > 0
        ? data.errors.map((e) => "· " + e).join("\n")
        : "服务端未能处理该请求。";
    clearPlan({ planFail: "服务端拒绝了规划请求，无法生成修补规划：\n" + detail });
  } catch (e) {
    clearPlan({
      planFail: "无法连接反演服务，本次未生成修补规划，既有规划不再显示。请确认服务可用后重试。",
    });
  } finally {
    planBtn.disabled = false;
  }
});

// ---- 初始化 ----
renderRecords();
clearConclusion();
