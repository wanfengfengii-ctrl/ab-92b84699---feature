"use strict";

// ---- 状态 ----
let records = [
  { r1: 1, c1: 1, r2: 2, c2: 2, count: 1 },
  { r1: 2, c1: 2, r2: 3, c2: 3, count: 0 },
  { r1: 3, c1: 3, r2: 4, c2: 4, count: 1 },
];

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
const planError = $("plan-error");
const planResult = $("plan-result");
const planSummary = $("plan-summary");
const patchList = $("patch-list");

// 每次输入修改都递增；在途响应返回时若已过期则直接丢弃，
// 保证“任一检测资料修改后既有结论与规划不得继续显示”。
let inputEpoch = 0;

// 修补片配色（按片号循环）。
const PATCH_COLORS = [
  "#b3402f", "#1f6f8b", "#6a7f1f", "#7a4fa3",
  "#b3762a", "#2f7d5b", "#a33d6e", "#4d5fb3",
];

// ---- 旧结论清除 ----
function resetPlan() {
  planResult.hidden = true;
  planError.hidden = true;
  planError.textContent = "";
  patchList.innerHTML = "";
}

function clearConclusion(opts = {}) {
  resultOk.hidden = true;
  resultError.hidden = true;
  formError.hidden = true;
  placeholder.hidden = true;
  staleBanner.hidden = true;
  resetPlan();
  if (opts.stale) {
    staleBanner.hidden = false;
  } else if (opts.error) {
    resultError.hidden = false;
    errorText.textContent = opts.error;
  } else {
    placeholder.hidden = false;
  }
}

// 任何输入修改都使旧结论与旧规划立即失效。
function markStale() {
  inputEpoch += 1;
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

// ---- 结果渲染 ----
// 在原网格上绘制空鼓分布；patches（1 基含端点）存在时叠加每片边界与片号角标。
function renderBrickGrid(grid, cols, patches) {
  const rows = grid.length;
  const owner = grid.map((row) => row.map(() => -1));
  if (patches) {
    patches.forEach((p, idx) => {
      for (let r = p.r1 - 1; r <= p.r2 - 1; r += 1) {
        for (let c = p.c1 - 1; c <= p.c2 - 1; c += 1) {
          owner[r][c] = idx;
        }
      }
    });
  }

  const gridEl = $("brick-grid");
  gridEl.innerHTML = "";
  gridEl.style.gridTemplateColumns = `repeat(${cols}, 64px)`;
  grid.forEach((row, r) => {
    row.forEach((v, c) => {
      const cell = document.createElement("div");
      cell.className = "brick" + (v === 1 ? " hollow" : "");
      cell.textContent = `${r + 1},${c + 1}`;
      cell.title = v === 1 ? `第 ${r + 1} 行第 ${c + 1} 列：空鼓` : `第 ${r + 1} 行第 ${c + 1} 列：完好`;
      const idx = owner[r][c];
      if (idx >= 0) {
        const color = PATCH_COLORS[idx % PATCH_COLORS.length];
        // 四邻不属于同一片（或超出墙面）的边即该片切缝边界。
        const edges = [];
        if (r === 0 || owner[r - 1][c] !== idx) edges.push(`inset 0 4px 0 0 ${color}`);
        if (r === rows - 1 || owner[r + 1][c] !== idx) edges.push(`inset 0 -4px 0 0 ${color}`);
        if (c === 0 || owner[r][c - 1] !== idx) edges.push(`inset 4px 0 0 0 ${color}`);
        if (c === cols - 1 || owner[r][c + 1] !== idx) edges.push(`inset -4px 0 0 0 ${color}`);
        cell.style.boxShadow = edges.join(", ");
        const badge = document.createElement("span");
        badge.className = "patch-badge";
        badge.style.background = color;
        badge.textContent = String(idx + 1);
        cell.appendChild(badge);
        cell.title += `；第 ${idx + 1} 修补片`;
      }
      gridEl.appendChild(cell);
    });
  });
}

function renderConclusion(data, submittedRects) {
  clearConclusion();
  resultOk.hidden = false;

  $("total-hollow").textContent = String(data.total);

  renderBrickGrid(data.grid, data.cols, null);

  const list = $("count-list");
  list.innerHTML = "";
  data.actual_counts.forEach((actual, i) => {
    const rec = submittedRects[i];
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

// ---- 修补规划渲染 ----
function showPlanError(message) {
  resetPlan();
  planError.hidden = false;
  planError.textContent = message;
}

function renderPlan(data) {
  resetPlan();
  const plan = data.plan;
  // 在原网格上标出每片边界（使用服务端随规划一并返回的反演网格）。
  renderBrickGrid(data.grid, data.cols, plan.pieces);

  planSummary.textContent = plan.piece_count === 0
    ? "修补规划：无空鼓砖，无需修补（0 片，切缝长度合计 0）。"
    : `修补规划：共 ${plan.piece_count} 片，各片四周切缝长度合计 ` +
      `${plan.total_perimeter}（砖边长）。网格中同色描边与角标为同一片。`;

  plan.pieces.forEach((p, idx) => {
    const li = document.createElement("li");
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.style.background = PATCH_COLORS[idx % PATCH_COLORS.length];
    const text = document.createElement("span");
    text.className = "coords";
    text.textContent =
      `第 ${idx + 1} 片：行 ${p.r1}–${p.r2}、列 ${p.c1}–${p.c2}，` +
      `覆盖 ${p.cells} 砖，单片切缝长度 ${p.perimeter}`;
    li.append(chip, text);
    patchList.appendChild(li);
  });
  planResult.hidden = false;
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
  const epoch = inputEpoch;
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
    if (epoch !== inputEpoch) return; // 等待期间输入已修改，丢弃旧响应

    if (resp.ok && data && data.status === "ok") {
      renderConclusion(data, payloadRects);
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

// ---- 发起最小切缝修补规划 ----
planBtn.addEventListener("click", async () => {
  // 只发送检测记录（行列数 + 矩形记录），由服务端重新反演后再规划。
  const { errs, rows, cols, payloadRects } = clientValidate();
  if (errs.length > 0) {
    showPlanError(
      "无法生成修补规划：当前检测资料不合法，服务端将拒绝该请求，旧规划已清除：\n" +
        errs.map((e) => "· " + e).join("\n"),
    );
    return;
  }

  planBtn.disabled = true;
  const epoch = inputEpoch;
  try {
    const resp = await fetch("/api/plan", {
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
    if (epoch !== inputEpoch) return; // 等待期间输入已修改，丢弃旧响应

    if (resp.ok && data && data.status === "ok" && data.plan) {
      renderPlan(data);
      return;
    }
    if (resp.ok && data && data.status === "unsat") {
      showPlanError(
        "无法生成修补规划：当前全部检测记录无解（无法满足全部记录），旧规划已清除。" +
          "请核对敲击记录后重新提交联合判定。",
      );
      return;
    }
    const detail =
      data && Array.isArray(data.errors) && data.errors.length > 0
        ? data.errors.map((e) => "· " + e).join("\n")
        : "服务端未能处理该请求。";
    showPlanError("无法生成修补规划：服务端拒绝了本次请求，旧规划已清除：\n" + detail);
  } catch (e) {
    if (epoch !== inputEpoch) return;
    showPlanError("无法连接反演服务，未能生成修补规划，旧规划已清除。请确认服务可用后重试。");
  } finally {
    planBtn.disabled = false;
  }
});

// ---- 初始化 ----
renderRecords();
clearConclusion();
