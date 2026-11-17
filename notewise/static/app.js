// Notewise UI: notes viewer with cited-line highlights, Ask / Tutor / Explain-it-back chat.
const $ = (s) => document.querySelector(s);
let notes = { files: [], chunks: 0 }, current = null, mode = "answer";
const HELP = {
  answer: "Ask anything. Every answer links to the lines of your notes it came from, or says it is not in your notes.",
  tutor: "Tutor mode does not hand you the answer: it asks a guiding question and points you to where to look.",
  check: "Explain a topic in your own words. Notewise checks it against your notes: what you got, what you missed, what contradicts them.",
};

async function api(path, body, method) {
  const r = await fetch(path, { method: method || (body ? "POST" : "GET"), headers: { "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : undefined });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.detail ? (typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail)) : r.statusText);
  return j;
}
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

function setNotes(n) { notes = n; if (!notes.files.find((f) => f.name === current)) current = notes.files[0]?.name || null; renderTabs(); renderViewer(); }
function renderTabs() {
  $("#tabs").innerHTML = notes.files.map((f) => `<span class="tab ${f.name === current ? "on" : ""}" data-n="${esc(f.name)}">${esc(f.name)} <span class="x" data-del="${esc(f.name)}" title="remove">x</span></span>`).join("");
}
function renderViewer(hl = [], focus = null) {
  const f = notes.files.find((x) => x.name === current);
  if (!f) { $("#viewer").innerHTML = `<p class="empty">No notes yet. Upload a file, paste text, or load the sample notes.</p>`; return; }
  const on = new Set(); const foc = new Set();
  for (const s of hl) if (s.file === f.name) for (let i = s.lines[0]; i <= s.lines[1]; i++) { on.add(i); if (s.id === focus) foc.add(i); }
  $("#viewer").innerHTML = f.text.split("\n").map((t, i) => {
    const n = i + 1; const cls = ["ln", on.has(n) ? "h" : "", foc.has(n) ? "focus" : "", t.trim().startsWith("#") ? "head" : ""].join(" ");
    return `<div class="${cls}" id="L${n}"><span class="n">${n}</span><span class="t">${esc(t) || " "}</span></div>`;
  }).join("");
  const first = [...(foc.size ? foc : on)][0];
  if (first) document.getElementById("L" + first)?.scrollIntoView({ block: "center", behavior: "smooth" });
}
let lastSources = [];
function showSource(id) {
  const s = lastSources.find((x) => x.id === id); if (!s) return;
  current = s.file; renderTabs(); renderViewer(lastSources, id);
}
const fileOf = (id) => id.split("#")[0];
function cites(sources) {
  return sources.map((s) => `<span class="cite" data-cite="${esc(s.id)}">${esc(s.id.split("#")[0])}, lines ${s.lines[0]}-${s.lines[1]}${s.heading ? " (" + esc(s.heading) + ")" : ""}</span>`).join("");
}
function add(cls, html) { const d = document.createElement("div"); d.className = "msg " + cls; d.innerHTML = html; $("#log").appendChild(d); $("#log").scrollTop = 1e9; return d; }

function renderAnswer(r) {
  const srcs = (r.sources || []).map((s) => ({ ...s, file: fileOf(s.id) }));
  lastSources = srcs;
  if (!r.in_notes) {
    const why = r.guard === "retrieval" ? "No part of your notes talks about this, so the model was not asked to guess."
      : r.guard === "citation" ? "The model's answer could not be matched to any passage in your notes, so it is not shown." : "";
    add("bot no", `<div class="k">Not in your notes</div>${esc(r.answer || r.question || "That is not in your notes.")}${why ? `<div class="help">${why}</div>` : ""}`);
    return;
  }
  if (mode === "tutor") add("bot", `<div class="k">Think about this</div>${esc(r.question)}${r.hint ? `<div class="help">Hint: ${esc(r.hint)}</div>` : ""}${cites(srcs)}`);
  else add("bot", `<div class="k">From your notes</div>${esc(r.answer)}<div>${cites(srcs)}</div>`);
  if (srcs[0]) showSource(srcs[0].id);
}
function renderCheck(r) {
  const srcs = Object.entries(r.sources || {}).map(([id, s]) => ({ id, ...s, file: fileOf(id) }));
  lastSources = srcs;
  const pill = (id) => { const s = srcs.find((x) => x.id === id); return s ? cites([s]) : ""; };
  const sc = r.score ?? 0;
  add("bot", `<div class="k">Explain-it-back check</div><div class="score ${sc >= 70 ? "ok" : sc < 40 ? "bad" : ""}">${sc}/100</div>
    ${r.covered?.length ? `<b class="ok">You got</b><ul>${r.covered.map((c) => `<li>${esc(c)}</li>`).join("")}</ul>` : ""}
    ${r.missed?.length ? `<b>You missed</b><ul>${r.missed.map((m) => `<li>${esc(m.point)} ${pill(m.citation)}</li>`).join("")}</ul>` : ""}
    ${r.wrong?.length ? `<b class="bad">Contradicts your notes</b><ul>${r.wrong.map((m) => `<li>${esc(m.claim)} ${pill(m.citation)}</li>`).join("")}</ul>` : ""}`);
  const firstCite = r.wrong?.[0]?.citation || r.missed?.[0]?.citation;
  if (firstCite) showSource(firstCite); else { renderViewer(srcs); }
}

$("#form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const q = $("#q").value.trim(); const topic = $("#topic").value.trim();
  if (!q || (mode === "check" && !topic)) return;
  add("you", mode === "check" ? `<div class="k">${esc(topic)}</div>${esc(q)}` : esc(q));
  $("#q").value = ""; $("#send").disabled = true;
  const wait = add("bot typing", "Reading your notes...");
  try {
    const r = mode === "check" ? await api("/api/check", { topic, explanation: q }) : await api("/api/ask", { question: q, mode });
    wait.remove(); mode === "check" ? renderCheck(r) : renderAnswer(r);
  } catch (err) { wait.remove(); add("bot no", `<div class="k">Error</div>${esc(err.message)}`); }
  $("#send").disabled = false; $("#q").focus();
});
$("#q").addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("#form").requestSubmit(); } });
document.querySelectorAll(".mode").forEach((b) => b.addEventListener("click", () => {
  mode = b.dataset.mode; document.querySelectorAll(".mode").forEach((x) => x.classList.toggle("on", x === b));
  $("#modehelp").textContent = HELP[mode]; $("#topic").hidden = mode !== "check";
  $("#q").placeholder = mode === "check" ? "Explain the topic in your own words" : mode === "tutor" ? "What are you stuck on?" : "Ask a question about your notes";
}));
$("#modehelp").textContent = HELP.answer;
$("#tabs").addEventListener("click", async (e) => {
  const del = e.target.dataset.del;
  if (del) { setNotes(await api("/api/notes/" + encodeURIComponent(del), null, "DELETE")); return; }
  const t = e.target.closest(".tab"); if (t) { current = t.dataset.n; renderTabs(); renderViewer(lastSources); }
});
$("#log").addEventListener("click", (e) => { const c = e.target.closest(".cite"); if (c) showSource(c.dataset.cite); });
$("#samples").addEventListener("click", async () => setNotes(await api("/api/samples", {})));
$("#paste").addEventListener("click", () => { $("#pastebox").hidden = !$("#pastebox").hidden; });
$("#padd").addEventListener("click", async () => {
  const name = $("#pname").value.trim() || "pasted-notes.md", text = $("#ptext").value;
  if (!text.trim()) return;
  setNotes(await api("/api/notes", { name, text })); current = name; renderTabs(); renderViewer();
  $("#ptext").value = ""; $("#pastebox").hidden = true;
});
$("#file").addEventListener("change", async (e) => {
  for (const f of e.target.files) { const n = await api("/api/notes", { name: f.name, text: await f.text() }); setNotes(n); current = f.name.replace(/#/g, "_"); }
  renderTabs(); renderViewer(); e.target.value = "";
});
api("/api/notes").then(setNotes);
