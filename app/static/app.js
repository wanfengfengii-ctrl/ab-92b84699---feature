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

// ---- 旧结论清除 ----
function clearConclusion(opts = {}) {
  resultOk.hidden = true;
  resultError.hidden = true;
  formError.hidden = true;
  placeholder.hidden = true;
  staleBanner.hidden = true;
  if (opts.stale) {
    staleBanner.hidden = false;
  } else if (opts.error) {
    resultError.hidden = false;
    errorText.textContent = opts.error;
  } else {
    placeholder.hidden = false;
  }
}

// 任何输入修改都使旧结论立即失效。
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

// ---- 结果渲染 ----
function renderConclusion(data, submittedRects) {
  clearConclusion();
  resultOk.hidden = false;

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

// ---- 初始化 ----
renderRecords();
clearConclusion();
