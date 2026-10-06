"use strict";
const $ = id => document.getElementById(id);
const coreStages = ["create", "insert", "delete"];
const legacyPage = location.pathname === "/legacy";
const stageNames = {create:"Create",insert:"Insert",update:"Update",delete:"Delete",evolve:"Evolve"};
const names = {iceberg:"Apache Iceberg",delta:"Delta Lake",hudi:"Apache Hudi"};
let statusData = null, snapshot = null, view = "rows", requestId = 0;
const escape = value => String(value).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));
const pretty = value => `<pre>${escape(JSON.stringify(value,null,2))}</pre>`;
const empty = text => `<div class="empty">${escape(text)}</div>`;
const formatTime = time => new Date(time).toLocaleString(undefined,{dateStyle:"medium",timeStyle:"medium"});
const runLabel = run => run.preset_label.replace(/^Article ·/, "Olist ·");
const selectedRun = () => statusData?.runs.find(run => run.run_id === $("run").value);
const selectedFormats = () => snapshot?.formats.filter(item => $("format").value === "all" || item.format === $("format").value) || [];

function cell(value, column) {
  if (value === null || value === undefined) return '<span class="null">null</span>';
  if (column === "order_id" || column === "customer_id") return `<span class="key" title="${escape(value)}">${escape(value.slice(0,10))}…</span>`;
  return escape(typeof value === "object" ? JSON.stringify(value) : value);
}
function table(rows, columns) {
  if (!rows.length) return '<p class="muted">No rows in this selection.</p>';
  const headings = columns.map(c => `<th>${escape(c)}</th>`).join("");
  const body = rows.map(row => `<tr>${columns.map(c => `<td>${cell(row[c],c)}</td>`).join("")}</tr>`).join("");
  return `<div class="table-scroll"><table><thead><tr>${headings}</tr></thead><tbody>${body}</tbody></table></div>`;
}
function panel(item, body) {return `<article class="panel" data-format="${item.format}"><h2>${names[item.format]}</h2>${body}</article>`;}
function details(title, data) {return `<details><summary>${escape(title)}</summary>${pretty(data)}</details>`;}
function filtered(rows) {
  const query = $("search").value.trim().toLowerCase();
  return query ? rows.filter(row => JSON.stringify(row).toLowerCase().includes(query)) : rows;
}
function render() {
  $("search-label").hidden = view !== "rows";
  $("download").disabled = !snapshot;
  if (!snapshot) {$("cards").innerHTML="";$("question").hidden=true;return;}
  $("question").hidden=false;
  $("question").innerHTML=`<strong>${escape(snapshot.question)}</strong><span>Expected ${snapshot.expected_rows} rows · ${escape(snapshot.write_action||snapshot.stage)} · captured ${escape(formatTime(snapshot.captured_at))}</span>`;
  $("cards").innerHTML=snapshot.formats.map(item => `<article class="card"><h3>${names[item.format]}</h3><div class="number">${item.validation.row_count} <span class="muted">rows</span></div><span class="badge ${item.validation.status !== "PASS" ? "fail" : ""}">${escape(item.validation.status)} · business values</span><small>${item.file_changes.added.length} files added · ${item.file_changes.removed.length} removed · ${item.file_changes.changed.length} changed</small></article>`).join("");
  $("content").innerHTML=selectedFormats().map(item => {
    if (view === "rows") {
      const rows=filtered(item.rows);
      return panel(item,`<p>${rows.length} of ${item.rows.length} saved rows shown. Identifiers are shortened visually; full values remain in downloaded evidence.</p>`+table(rows,item.validation.business_columns));
    }
    if (view === "changes") {
      const changes=item.row_changes;
      const updates=changes.updated.flatMap(change => change.changed_columns.map(column => ({order_id:change.order_id,column,before:column in change.before ? change.before[column] : "column absent",after:change.after[column]})));
      return panel(item,`<h3 class="change-heading">${snapshot.stage === "create" ? "Initial rows" : "Inserted"} · ${changes.inserted.length}</h3>`+table(changes.inserted,item.validation.business_columns)+`<h3 class="change-heading">Updated · ${changes.updated.length} rows</h3>`+table(updates,["order_id","column","before","after"])+`<h3 class="change-heading">Deleted · ${changes.deleted.length}</h3>`+table(changes.deleted,Object.keys(changes.deleted[0]||{})));
    }
    if (view === "schema") return panel(item,table(item.schema.fields,["name","type","nullable"])+details("Actual Spark schema JSON",item.schema));
    if (view === "metadata") {
      const files=item.raw_metadata.files;
      return panel(item,`<p>${escape(item.metadata.what_to_notice)}</p>`+table(Object.entries(item.metadata_summary||{}).map(([property,value])=>({property,value})),["property","value"])+`<p class="path">Read: ${escape(item.reader_command)}</p>`+details("Table metadata interfaces",item.metadata)+`<p>${files.length} of ${item.raw_metadata.candidate_count} metadata files included. ${escape(item.raw_metadata.note)}</p><p class="muted">Large integer metadata values appear as decimal strings to preserve every digit in the browser and download.</p>`+files.map(file => `<details><summary>${escape(file.path.replace(item.root+"/",""))} · ${escape(file.encoding)}</summary>${file.inspection_error ? `<p>Decode unavailable: ${escape(file.inspection_error)}</p>` : ""}${file.note ? `<p>${escape(file.note)}</p>` : ""}${file.truncated ? "<p>Record preview is truncated at its documented limit.</p>" : ""}${file.text !== undefined ? `<pre>${escape(file.text)}</pre>` : file.records ? pretty(file.records) : pretty(file)}</details>`).join(""));
    }
    const files=item.file_changes;
    const paths = rows => rows.map(row => ({path:row.path.replace(item.root+"/",""),bytes:row.size_bytes,modified:new Date(row.modified_ms).toISOString()}));
    return panel(item,`<p>${escape(files.change_basis)}</p><h3 class="change-heading">Added · ${files.added.length}</h3>`+table(paths(files.added),["path","bytes","modified"])+`<h3 class="change-heading">Removed · ${files.removed.length}</h3>`+table(paths(files.removed),["path","bytes","modified"])+`<h3 class="change-heading">Changed · ${files.changed.length}</h3>`+pretty(files.changed)+details("Complete captured inventory",item.inventory));
  }).join("");
}
function showRunNotice(run) {
  const notices=[];
  if (run.is_legacy) notices.push("Earlier run: read-only saved results.");
  if (!run.is_current) notices.push("Viewing saved snapshots from an earlier run.");
  if (!run.evidence_schema_version) notices.push("These saved Hudi totals include auxiliary metadata-table objects; the summary lists them separately.");
  if (run.status === "running") notices.push(`Stage ${run.active_stage} is running. The producer publishes evidence only after successful validation.`);
  if (run.stale) notices.push("No producer update for over five minutes. This run may be stalled; refresh after checking the notebook.");
  if (run.status === "failed") notices.push(`Run failed at ${run.failed_stage}: ${run.error}. Showing only completed snapshots.`);
  if (run.status === "reset") notices.push("This run's table resources were reset. Its saved snapshots remain available.");
  $("notice").textContent=notices.join(" ");
  $("provenance").textContent=`${runLabel(run)} · ${run.run_id} · ${run.status} · source SHA-256 ${run.source.sha256.slice(0,12)}… · saved evidence only`;
  if (!legacyPage && run.configuration) {
    document.querySelector(".intro h1").textContent=run.configuration.counts.join(" → ")+" orders";
    document.querySelector(".intro > p:last-child").textContent=`Create ${run.configuration.initial_rows}, insert ${run.configuration.insert_rows}, delete ${run.configuration.delete_rows}. Sample seed: ${run.configuration.sample_seed}`;
  }
}
async function loadStage() {
  const id=++requestId;
  snapshot=null;render();
  const run=selectedRun();
  if (!run) return;
  showRunNotice(run);
  const stage=$("stage").value;
  if (!run.completed_stages.includes(stage)) {
    $("content").innerHTML=empty("No saved evidence for this stage yet. Run this step in the notebook, then refresh.");
    return;
  }
  $("content").innerHTML=empty("Loading saved snapshot…");
  try {
    const response=await fetch(`/api/runs/${encodeURIComponent(run.run_id)}/stages/${stage}`);
    const data=await response.json();
    if (id !== requestId) return;
    if (!response.ok) throw new Error(data.message);
    if (data.run_id !== run.run_id || data.stage !== stage) throw new Error("Snapshot identity does not match the selection");
    snapshot=data;render();
    $("provenance").textContent+=` · captured ${formatTime(data.captured_at)}`;
  } catch(error) {if(id===requestId)$("content").innerHTML=empty(error.message);}
}
function populateStages(jumpToLatest=true) {
  const run=selectedRun();
  const previous=$("stage").value;
  const definitions=run?.stages || coreStages.map(id=>({id}));
  $("stage").innerHTML=definitions.map((definition,index)=>`<option value="${definition.id}">${index+1} · ${stageNames[definition.id]}${definition.expected_rows !== undefined ? ` · ${definition.expected_rows} rows` : ""}${run?.completed_stages.includes(definition.id)?" · recorded":" · pending"}</option>`).join("");
  $("stage").value=jumpToLatest ? run?.completed_stages.at(-1)||"create" : previous||"create";
}
async function refresh() {
  $("refresh").disabled=true;
  try {
    const response=await fetch("/api/status");
    const data=await response.json();
    if(!response.ok)throw new Error(data.message);
    data.runs=data.runs.filter(run=>legacyPage ? run.is_legacy : !run.is_legacy);
    const oldRun=$("run").value, oldCurrent=statusData?.current_run_id;
    statusData=data;
    if (!data.runs.length) {
      snapshot=null;render();$("run").innerHTML="";populateStages();
      $("provenance").textContent="No generated Olist evidence found.";
      $("content").innerHTML=empty(legacyPage ? "No earlier runs are available." : "Set the notebook configuration and execute Create. Defaults are 3 → 5 → 4. Refresh will then load its evidence.");
      return;
    }
    $("run").innerHTML=data.runs.map(run=>`<option value="${escape(run.run_id)}">${escape(runLabel(run))} · ${escape(run.run_id)}${run.is_current?" · current":""}</option>`).join("");
    const current=data.runs.some(run=>run.run_id===data.current_run_id) ? data.current_run_id : data.runs[0].run_id;
    $("run").value=(oldRun&&oldRun!==oldCurrent&&data.runs.some(run=>run.run_id===oldRun))?oldRun:current;
    populateStages();await loadStage();
  } catch(error) {
    snapshot=null;render();$("notice").textContent="Evidence unavailable";$("content").innerHTML=empty(error.message);
  } finally {$("refresh").disabled=false;}
}
$("refresh").addEventListener("click",refresh);
$("run").addEventListener("change",()=>{populateStages();loadStage();});
$("stage").addEventListener("change",loadStage);
$("format").addEventListener("change",render);
$("search").addEventListener("input",render);
document.querySelectorAll("[data-view]").forEach(button=>button.addEventListener("click",()=>{
  view=button.dataset.view;
  document.querySelectorAll("[data-view]").forEach(tab=>{tab.classList.toggle("selected",tab===button);tab.setAttribute("aria-pressed",String(tab===button));});
  render();
}));
$("download").addEventListener("click",()=>{
  if(!snapshot)return;
  const data={...snapshot,formats:selectedFormats()};
  const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:"application/json"}));
  const anchor=document.createElement("a");anchor.href=url;anchor.download=`${snapshot.run_id}-${snapshot.stage}-${$("format").value}.json`;anchor.click();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
});
if (legacyPage) {
  document.querySelector(".intro h1").textContent="Earlier runs";
  document.querySelector(".intro > p:last-child").textContent="Saved results from earlier workflows. The Olist walkthrough defaults to 3 → 5 → 4.";
  $("history-link").href="/";$("history-link").textContent="Open Olist walkthrough";
}
refresh();
