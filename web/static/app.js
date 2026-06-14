const API = "/api";

let selectedFilterId = null;
let screenRows = [];
let selectedScreenSymbols = new Set();
let selectedPoolSymbols = new Set();
let currentPoolNode = "hs300";
let poolHierarchy = [];

async function api(path, opts = {}) {
  const res = await fetch(API + path, {
    headers: { "Content-Type": "application/json", ...opts.headers },
    ...opts,
  });
  const text = await res.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = text; }
  if (!res.ok) {
    const msg = data?.detail || (typeof data === "string" ? data : JSON.stringify(data));
    throw new Error(msg || res.statusText);
  }
  return data;
}

function toast(msg) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.classList.remove("hidden");
  setTimeout(() => el.classList.add("hidden"), 3200);
}

function fmtNum(n, digits = 2) {
  if (n == null || Number.isNaN(n)) return "—";
  if (Math.abs(n) >= 1e8) return (n / 1e8).toFixed(digits) + "亿";
  if (Math.abs(n) >= 1e4) return (n / 1e4).toFixed(digits) + "万";
  return Number(n).toFixed(digits);
}

// ── tabs ──
document.querySelectorAll(".step").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".step").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById("tab-" + btn.dataset.tab).classList.add("active");
  });
});

// ── health ──
async function refreshHealth() {
  const pill = document.getElementById("connStatus");
  try {
    const h = await api("/health");
    if (h.connected) {
      pill.className = "status-pill ok";
      pill.innerHTML = `<span class="dot"></span><span>MiniQMT 已连接 · 全市场 ${h.universe_size ?? "?"} 只</span>`;
    } else {
      pill.className = "status-pill err";
      pill.innerHTML = `<span class="dot"></span><span>未连接${h.error ? " · " + h.error : ""}</span>`;
    }
  } catch (e) {
    pill.className = "status-pill err";
    pill.innerHTML = `<span class="dot"></span><span>服务异常</span>`;
  }
}

// ── sync ──
async function pollSync() {
  try {
    const job = await api("/sync/status");
    const box = document.getElementById("syncProgress");
    if (!job || job.status === "idle") {
      box.innerHTML = '<p class="muted">暂无运行中的任务</p>';
      return;
    }
    const p = job.progress;
    const pct = p ? p.pct?.toFixed(1) : 0;
    box.innerHTML = `
      <p><strong>${job.mode}</strong> · ${job.status}</p>
      ${p ? `<p class="muted">${p.message} · ${p.done}/${p.total}</p>
      <div class="progress-bar"><div style="width:${pct}%"></div></div>` : ""}
      ${job.error ? `<p class="msg err">${job.error}</p>` : ""}
      ${job.report ? `<p class="msg ok">完成: ${job.report.success_count}/${job.report.stock_count}</p>` : ""}
    `;
    if (job.status === "running") setTimeout(pollSync, 1500);
  } catch { /* ignore */ }
}

document.getElementById("btnFullSync").onclick = async () => {
  try {
    await api("/sync/full", {
      method: "POST",
      body: JSON.stringify({ start: document.getElementById("syncStart").value }),
    });
    toast("全量同步已启动");
    pollSync();
  } catch (e) { toast(e.message); }
};

document.getElementById("btnIncrSync").onclick = async () => {
  try {
    await api("/sync/incremental", { method: "POST", body: "{}" });
    toast("增量同步已启动");
    pollSync();
  } catch (e) { toast(e.message); }
};

document.getElementById("btnUniverse").onclick = async () => {
  try {
    const u = await api("/sync/universe");
    document.getElementById("universeInfo").textContent =
      `全市场 ${u.count} 只 · 样例: ${u.sample.slice(0, 10).join(", ")}`;
    toast("已刷新");
  } catch (e) { toast(e.message); }
};

// ── filters ──
async function loadFilters() {
  const filters = await api("/filters");
  const list = document.getElementById("filterList");
  list.innerHTML = filters.map((f) => `
    <div class="filter-item ${f.id === selectedFilterId ? "selected" : ""}" data-id="${f.id}">
      <input type="checkbox" ${f.enabled ? "checked" : ""} data-toggle="${f.id}" />
      <div class="filter-meta">
        <strong>${f.name}${f.builtin ? " (内置)" : ""}</strong>
        <code>${f.expr}</code>
      </div>
      ${!f.builtin ? `<div class="filter-actions"><button data-del="${f.id}">删除</button></div>` : ""}
    </div>
  `).join("");

  list.querySelectorAll("[data-toggle]").forEach((cb) => {
    cb.addEventListener("click", async (e) => {
      e.stopPropagation();
      await api(`/filters/${cb.dataset.toggle}/enabled`, {
        method: "PATCH",
        body: JSON.stringify({ enabled: cb.checked }),
      });
    });
  });

  list.querySelectorAll(".filter-item").forEach((el) => {
    el.addEventListener("click", () => {
      selectedFilterId = el.dataset.id;
      const f = filters.find((x) => x.id === selectedFilterId);
      if (f) {
        document.getElementById("filterName").value = f.name;
        document.getElementById("filterExpr").value = f.expr;
        document.getElementById("filterDesc").value = f.description || "";
      }
      loadFilters();
    });
  });

  list.querySelectorAll("[data-del]").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      if (!confirm("删除此规则?")) return;
      await api(`/filters/${btn.dataset.del}`, { method: "DELETE" });
      selectedFilterId = null;
      loadFilters();
      toast("已删除");
    });
  });
}

async function loadFieldDocs() {
  const fields = await api("/filters/fields");
  document.getElementById("fieldDocs").innerHTML = Object.entries(fields)
    .map(([k, v]) => `<li><code>${k}</code> — ${v}</li>`)
    .join("");
}

document.getElementById("btnNewFilter").onclick = () => {
  selectedFilterId = null;
  document.getElementById("filterName").value = "";
  document.getElementById("filterExpr").value = "";
  document.getElementById("filterDesc").value = "";
};

document.getElementById("btnValidateExpr").onclick = async () => {
  const expr = document.getElementById("filterExpr").value;
  const r = await api("/filters/validate", { method: "POST", body: JSON.stringify({ expr }) });
  const msg = document.getElementById("exprMsg");
  msg.textContent = r.ok ? "表达式合法" : r.message;
  msg.className = "msg " + (r.ok ? "ok" : "err");
};

document.getElementById("btnSaveFilter").onclick = async () => {
  const body = {
    name: document.getElementById("filterName").value.trim(),
    expr: document.getElementById("filterExpr").value.trim(),
    description: document.getElementById("filterDesc").value.trim(),
  };
  if (!body.name || !body.expr) return toast("请填写名称和表达式");
  try {
    if (selectedFilterId) {
      await api(`/filters/${selectedFilterId}`, { method: "PUT", body: JSON.stringify(body) });
    } else {
      const created = await api("/filters", { method: "POST", body: JSON.stringify(body) });
      selectedFilterId = created.id;
    }
    loadFilters();
    toast("已保存");
  } catch (e) { toast(e.message); }
};

// ── screen ──
function renderTable(tableId, rows, cols, onSelect) {
  const table = document.getElementById(tableId);
  const thead = table.querySelector("thead");
  const tbody = table.querySelector("tbody");
  thead.innerHTML = `<tr>${cols.map((c) => `<th>${c.label}</th>`).join("")}</tr>`;
  tbody.innerHTML = rows.map((row) => {
    const sym = String(row.symbol || "");
    const sel = onSelect?.has(sym) ? "selected" : "";
    return `<tr class="${sel}" data-sym="${sym}">${cols.map((c) =>
      `<td>${c.fmt ? c.fmt(row[c.key]) : (row[c.key] ?? "—")}</td>`
    ).join("")}</tr>`;
  }).join("");

  if (onSelect) {
    tbody.querySelectorAll("tr").forEach((tr) => {
      tr.addEventListener("click", () => {
        const s = tr.dataset.sym;
        if (onSelect.has(s)) onSelect.delete(s); else onSelect.add(s);
        renderTable(tableId, rows, cols, onSelect);
      });
    });
  }
}

const screenCols = [
  { key: "symbol", label: "代码" },
  { key: "name", label: "名称" },
  { key: "close", label: "收盘", fmt: (v) => fmtNum(v) },
  { key: "momentum_20d", label: "20日%", fmt: (v) => fmtNum(v) },
  { key: "amount", label: "成交额", fmt: (v) => fmtNum(v) },
];

document.getElementById("screenSource").onchange = (e) => {
  document.getElementById("screenNode").classList.toggle("hidden", e.target.value !== "node");
};

document.getElementById("btnRunScreen").onclick = async () => {
  const source = document.getElementById("screenSource").value;
  const body = {
    source,
    node_id: document.getElementById("screenNode").value || "hs300",
    max_stocks: source === "universe" ? 800 : 200,
  };
  try {
    toast("筛选中，请稍候…");
    const r = await api("/screen", { method: "POST", body: JSON.stringify(body) });
    screenRows = r.rows || [];
    selectedScreenSymbols.clear();
    document.getElementById("screenStat").textContent = `命中 ${r.count} 只`;
    renderTable("screenTable", screenRows, screenCols, selectedScreenSymbols);
    toast(`筛选完成: ${r.count} 只`);
  } catch (e) { toast(e.message); }
};

document.getElementById("btnAddWatch").onclick = async () => {
  const syms = selectedScreenSymbols.size
    ? [...selectedScreenSymbols]
    : screenRows.slice(0, 20).map((r) => r.symbol);
  if (!syms.length) return toast("请先运行筛选或选择标的");
  try {
    await api("/watchlist", { method: "POST", body: JSON.stringify({ symbols: syms }) });
    toast(`已加入观察池 ${syms.length} 只`);
    loadWatchlist();
  } catch (e) { toast(e.message); }
};

// ── watchlist ──
async function loadWatchlist() {
  const items = await api("/watchlist");
  const box = document.getElementById("watchList");
  if (!items.length) {
    box.innerHTML = '<p class="muted">观察池为空，从筛选结果加入</p>';
    return;
  }
  box.innerHTML = items.map((w) => `
    <div class="watch-card ${w.status === "triggered" ? "triggered" : ""}">
      <h3>${w.name}</h3>
      <div class="sym">${w.symbol} · ${w.status}</div>
      <div class="progress"><div style="width:${Math.min(100, w.trigger_progress || 0)}%"></div></div>
      <p class="muted">${w.trigger_label}</p>
      <p>收盘 ${fmtNum(w.close)} · 动量 ${fmtNum(w.momentum20d)}%</p>
      <button class="btn sm ghost" data-rm="${w.symbol}">移除</button>
    </div>
  `).join("");
  box.querySelectorAll("[data-rm]").forEach((btn) => {
    btn.onclick = async () => {
      await api(`/watchlist/${btn.dataset.rm}`, { method: "DELETE" });
      loadWatchlist();
    };
  });
}

document.getElementById("btnRefreshWatch").onclick = async () => {
  await api("/watchlist/refresh", { method: "POST", body: "{}" });
  loadWatchlist();
  toast("已刷新");
};

// ── pools ──
async function loadPoolTree() {
  poolHierarchy = await api("/pools/hierarchy");
  const sel = document.getElementById("screenNode");
  sel.innerHTML = poolHierarchy
    .filter((n) => n.level >= 3)
    .map((n) => `<option value="${n.id}">${n.label}</option>`)
    .join("");

  const tree = document.getElementById("poolTree");
  tree.innerHTML = poolHierarchy.map((n) => `
    <li class="indent-${n.level}">
      <button data-node="${n.id}" class="${n.id === currentPoolNode ? "active" : ""}">
        ${"　".repeat(Math.max(0, n.level - 1))}${n.label}
      </button>
    </li>
  `).join("");

  tree.querySelectorAll("[data-node]").forEach((btn) => {
    btn.onclick = () => {
      currentPoolNode = btn.dataset.node;
      loadPoolTree();
      loadPoolDetail(currentPoolNode);
    };
  });
}

const poolCols = [
  { key: "symbol", label: "代码" },
  { key: "name", label: "名称" },
  { key: "close", label: "收盘", fmt: (v) => fmtNum(v) },
  { key: "pool_path", label: "路径" },
];

async function loadPoolDetail(nodeId) {
  try {
    const r = await api(`/pools/${nodeId}?max_stocks=80`);
    document.getElementById("poolTitle").textContent = r.path || nodeId;
    document.getElementById("poolStat").textContent = `${r.count} 只`;
    selectedPoolSymbols.clear();
    renderTable("poolTable", r.rows || [], poolCols, selectedPoolSymbols);
  } catch (e) {
    document.getElementById("poolStat").textContent = e.message;
  }
}

document.getElementById("btnPromote").onclick = async () => {
  const syms = selectedPoolSymbols.size
    ? [...selectedPoolSymbols]
    : [];
  if (!syms.length) return toast("请选择要调入的标的");
  try {
    const r = await api("/pools/promote", {
      method: "POST",
      body: JSON.stringify({ symbols: syms, target_node: "trade_momentum" }),
    });
    toast(`已调入可交易池 ${r.promoted.length} 只`);
    loadPoolDetail("trade_momentum");
    currentPoolNode = "trade_momentum";
    loadPoolTree();
  } catch (e) { toast(e.message); }
};

// ── init ──
async function init() {
  await refreshHealth();
  await loadFieldDocs();
  await loadFilters();
  await loadWatchlist();
  await loadPoolTree();
  await loadPoolDetail(currentPoolNode);
  pollSync();
  setInterval(refreshHealth, 30000);
}

init().catch(console.error);
