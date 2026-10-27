const $ = (id) => document.getElementById(id);

function showMsg(el, ok, text) {
  el.replaceChildren();
  const div = document.createElement("div");
  div.className = "msg " + (ok ? "ok" : "err");
  div.textContent = text;
  el.appendChild(div);
}

function renderTable(container, columns, rows) {
  const wrap = document.createElement("div");
  wrap.className = "tbl-wrap";
  const table = document.createElement("table");
  const thead = document.createElement("thead");
  const htr = document.createElement("tr");
  columns.forEach((c) => {
    const th = document.createElement("th");
    th.textContent = c;
    htr.appendChild(th);
  });
  thead.appendChild(htr);
  table.appendChild(thead);
  const tbody = document.createElement("tbody");
  rows.forEach((r) => {
    const tr = document.createElement("tr");
    r.forEach((cell) => {
      const td = document.createElement("td");
      td.textContent = cell === null ? "" : String(cell);
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  wrap.appendChild(table);
  container.appendChild(wrap);
}

// ---- Upload ----
const drop = $("drop");
const fileInput = $("file");
drop.addEventListener("click", () => fileInput.click());
drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("drag"); });
drop.addEventListener("dragleave", () => drop.classList.remove("drag"));
drop.addEventListener("drop", (e) => {
  e.preventDefault();
  drop.classList.remove("drag");
  if (e.dataTransfer.files.length) uploadFile(e.dataTransfer.files[0]);
});
fileInput.addEventListener("change", () => {
  if (fileInput.files.length) uploadFile(fileInput.files[0]);
});

async function uploadFile(file) {
  const fd = new FormData();
  fd.append("file", file);
  const tn = $("tableName").value.trim();
  if (tn) fd.append("table_name", tn);
  showMsg($("uploadMsg"), true, "Uploading " + file.name + "…");
  try {
    const res = await fetch("/api/upload", { method: "POST", body: fd });
    const data = await res.json();
    if (data.success) {
      const cols = (data.columns || []).map((c) => c.name + " (" + c.type + ")").join(", ");
      showMsg($("uploadMsg"), true, "Loaded table '" + data.table_name + "'\nColumns: " + cols);
      fileInput.value = "";
      loadDatasets();
    } else {
      showMsg($("uploadMsg"), false, data.error || "Upload failed.");
    }
  } catch (err) {
    showMsg($("uploadMsg"), false, String(err));
  }
}

// ---- Datasets ----
let activeTable = null;
async function loadDatasets() {
  try {
    const res = await fetch("/api/datasets");
    const data = await res.json();
    const ul = $("datasets");
    ul.replaceChildren();
    if (!data.success) { showMsg($("uploadMsg"), false, data.error); return; }
    if (!data.datasets.length) {
      const empty = document.createElement("li");
      empty.className = "meta empty";
      empty.textContent = "No datasets loaded yet.";
      ul.appendChild(empty);
      return;
    }
    data.datasets.forEach((d) => {
      const li = document.createElement("li");
      if (d.table_name === activeTable) li.classList.add("active");
      const name = document.createElement("div");
      const strong = document.createElement("strong");
      strong.textContent = d.table_name;
      name.appendChild(strong);
      const meta = document.createElement("div");
      meta.className = "meta";
      meta.textContent = d.row_count + " rows · " + (d.source_path || "");
      li.append(name, meta);
      li.addEventListener("click", () => describe(d.table_name));
      ul.appendChild(li);
    });
  } catch (err) {
    showMsg($("uploadMsg"), false, String(err));
  }
}

async function describe(name) {
  activeTable = name;
  loadDatasets();
  const container = $("schema");
  container.replaceChildren();
  try {
    const res = await fetch("/api/datasets/" + encodeURIComponent(name));
    const data = await res.json();
    if (!data.success) { showMsg(container, false, data.error); return; }
    const title = document.createElement("div");
    const heading = document.createElement("strong");
    heading.textContent = data.table_name + " ";
    title.appendChild(heading);
    (data.columns || []).forEach((c) => {
      const s = document.createElement("span");
      s.className = "pill";
      s.textContent = c.name + " : " + c.type;
      s.classList.add("pill-gap");
      title.appendChild(s);
    });
    container.appendChild(title);
    const cols = (data.columns || []).map((c) => c.name);
    renderTable(container, cols, (data.sample_rows || []).map((row) => cols.map((c) => row[c])));
    $("sql").value = "SELECT * FROM " + name + " LIMIT 20";
  } catch (err) {
    showMsg(container, false, String(err));
  }
}

// ---- Query ----
async function runQuery() {
  const sql = $("sql").value;
  const container = $("queryResult");
  container.replaceChildren();
  try {
    const res = await fetch("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sql }),
    });
    const data = await res.json();
    if (!data.success) { showMsg(container, false, data.error); return; }
    if (data.truncated) showMsg(container, true, "Results truncated to 1000 rows.");
    renderTable(container, data.columns, data.rows);
  } catch (err) {
    showMsg(container, false, String(err));
  }
}

$("refresh").addEventListener("click", loadDatasets);
$("run").addEventListener("click", runQuery);
loadDatasets();
