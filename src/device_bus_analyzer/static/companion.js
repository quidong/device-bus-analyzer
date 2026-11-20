// Companion: mark what is done at the appliance. Every action is timed by the server; nothing is sent to the appliance.
(function () {
  var root = document.getElementById("cp");
  if (!root) { return; }
  var csrf = root.dataset.csrf, base = "/s/" + encodeURIComponent(root.dataset.src), ctl = JSON.parse(root.dataset.controls),
      T = JSON.parse(root.dataset.t), recent = JSON.parse(root.dataset.markers), $ = function (id) { return document.getElementById(id); };
  var events = {}; ctl.events.forEach(function (e) { events[e.id] = e; });

  function post(url, data) {
    var body = new URLSearchParams(); body.set("csrf", csrf);
    Object.keys(data || {}).forEach(function (k) { if (data[k] !== undefined && data[k] !== null) { body.set(k, data[k]); } });
    return fetch(url, { method: "POST", body: body, credentials: "same-origin" }).then(function (r) {
      if (!r.ok) { throw new Error(String(r.status)); }
      return r.json();
    });
  }
  function fail() { window.alert(T.error); }
  function fill(s, args) { return args.reduce(function (acc, a) { return acc.replace("{}", a); }, s); }
  function clock(ts) { return new Date(ts * 1000).toLocaleTimeString(); }

  // --- recent list -----------------------------------------------------------------------------------
  function renderList() {
    var ul = $("cp-list"); ul.textContent = "";
    if (!recent.length) { var li = document.createElement("li"); li.className = "fld"; li.textContent = T.empty; ul.appendChild(li); return; }
    recent.slice(0, 15).forEach(function (m) {
      var li = document.createElement("li"), t = document.createElement("span"), b = document.createElement("span"), x = document.createElement("button");
      t.className = "mono"; t.textContent = clock(m.ts);
      b.textContent = m.label + (m.note && m.label.indexOf(m.note) < 0 ? " – " + m.note : "") + (m.menu ? " (" + m.menu + ")" : "") +
        (m.ts_end ? " · " + fill(T.duration, [Math.round((m.ts_end - m.ts) * 10) / 10]) : "");
      x.type = "button"; x.className = "icon"; x.textContent = "×"; x.setAttribute("aria-label", T.remove);
      x.addEventListener("click", function () {
        post(base + "/markers/" + m.id + "/delete").then(function () { recent = recent.filter(function (r) { return r.id !== m.id; }); renderList(); }, fail);
      });
      li.appendChild(t); li.appendChild(b); li.appendChild(x); ul.appendChild(li);
    });
  }
  function remember(m) { recent.unshift(m); renderList(); }
  function menuValue() { return $("cp-menu").value.trim(); }

  // --- free marking ----------------------------------------------------------------------------------
  var pending = null;
  ctl.events.forEach(function (e) {
    var b = document.createElement("button"); b.type = "button"; b.className = "ev"; b.textContent = e.label;
    b.addEventListener("click", function () {
      if (e.ask) { pending = e; $("cp-ask-label").textContent = e.label + " – " + T.note_label; $("cp-ask").hidden = false; $("cp-ask-note").value = lastNote; $("cp-ask-note").focus(); return; }
      post(base + "/markers", { kind: e.id, menu: menuValue() }).then(remember, fail);
    });
    $("cp-events").appendChild(b);
  });
  var lastNote = "";
  $("cp-ask").addEventListener("submit", function (ev) {
    ev.preventDefault(); var note = $("cp-ask-note").value.trim();
    if (!pending || !note) { return; }
    lastNote = note;
    post(base + "/markers", { kind: pending.id, note: note, menu: menuValue() }).then(function (m) { remember(m); $("cp-ask").hidden = true; pending = null; }, fail);
  });
  $("cp-ask-x").addEventListener("click", function () { $("cp-ask").hidden = true; pending = null; });
  $("cp-custom").addEventListener("submit", function (ev) {
    ev.preventDefault(); var l = $("cp-custom-label").value.trim();
    if (!l) { return; }
    post(base + "/markers", { kind: "custom", label: l, menu: menuValue() }).then(function (m) { remember(m); $("cp-custom-label").value = ""; }, fail);
  });

  // --- guided checks ---------------------------------------------------------------------------------
  var run = null, poll = null;
  ctl.guided.forEach(function (g) {
    var b = document.createElement("button"); b.type = "button"; b.className = "opt";
    var s = document.createElement("span"); s.textContent = g.label; var n = document.createElement("small"); n.textContent = g.repeat + "×";
    b.appendChild(s); b.appendChild(n); b.addEventListener("click", function () { start(g); });
    $("cp-scripts").appendChild(b);
  });
  function show(step) { $("cp-main").hidden = !!step; $("cp-step").hidden = step !== "step"; $("cp-end").hidden = step !== "end"; }
  function stopPoll() { if (poll) { clearInterval(poll); poll = null; } }
  function start(g) {
    run = { g: g, i: 0, group: Date.now().toString(36), marker: null, since: 0 };
    render();
  }
  function current() { return run.g.steps[run.i % run.g.steps.length]; }
  function render() {
    stopPoll(); show("step");
    var total = run.g.steps.length * run.g.repeat, st = current(), ev = events[st.event];
    $("cp-progress").textContent = fill(T.step, [run.i + 1, total]) + " · " + fill(T.round, [Math.floor(run.i / run.g.steps.length) + 1]);
    $("cp-text").textContent = st.text;
    $("cp-hint").hidden = true; $("cp-note-wrap").hidden = true; $("cp-note").value = "";
    $("cp-go").hidden = false; $("cp-done").hidden = true; run.marker = null;
    if (st.ask) { $("cp-note-label").textContent = T.note_label; }
  }
  $("cp-go").addEventListener("click", function () {
    var st = current();
    post(base + "/markers", { kind: st.event, menu: menuValue(), step_group: run.group }).then(function (m) {
      run.marker = m.id; run.since = m.ts; remember(m);
      $("cp-go").hidden = true; $("cp-done").hidden = false; $("cp-text").textContent = st.text + " — " + T.doing;
      if (st.ask) { $("cp-note-wrap").hidden = false; $("cp-note").value = events[st.event].by_note ? lastNote : ""; }
      $("cp-hint").hidden = false; $("cp-hint").textContent = "";
      poll = setInterval(hint, 2500);
    }, fail);
  });
  function hint() {
    if (!run || !run.marker) { return; }
    fetch(base + "/activity?since=" + run.since, { credentials: "same-origin" }).then(function (r) { return r.json(); }).then(function (a) {
      $("cp-hint").textContent = a.baseline < 5 ? T.hint_nobase : (a.changes ? fill(T.hint_some, [a.changes]) : T.hint_none);
    }, function () {});
  }
  $("cp-done").addEventListener("click", function () {
    var st = current(), note = $("cp-note").value.trim();
    if (st.ask && !note) { $("cp-hint").hidden = false; $("cp-hint").textContent = T.note_needed; $("cp-note").focus(); return; }
    if (note) { lastNote = note; }
    stopPoll();
    post(base + "/markers/" + run.marker + "/end", { note: note }).then(function (m) {
      recent = recent.map(function (r) { return r.id === m.id ? m : r; }); renderList();
      run.i += 1;
      if (run.i >= run.g.steps.length * run.g.repeat) { run = null; $("cp-end-text").textContent = T.finished; show("end"); } else { render(); }
    }, fail);
  });
  $("cp-abort").addEventListener("click", function () {
    stopPoll();
    var m = run && run.marker; run = null;
    if (m) { post(base + "/markers/" + m + "/delete").then(function () { recent = recent.filter(function (r) { return r.id !== m; }); renderList(); }, fail); }
    show(null);
  });
  $("cp-again").addEventListener("click", function () { show(null); });
  renderList(); show(null);
})();
