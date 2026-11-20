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
  function show(step) { $("cp-lead").hidden = $("cp-tip").hidden = !!step; $("cp-main").hidden = !!step; $("cp-step").hidden = step !== "step"; $("cp-end").hidden = step !== "end"; }
  function stopPoll() { if (poll) { clearInterval(poll); poll = null; } }
  function start(g) {
    run = { g: g, i: 0, group: Date.now().toString(36), marker: null, since: 0 };
    idle();
  }
  function current() { return run.g.steps[run.i % run.g.steps.length]; }
  // First screen of a run: only "Go". After it every step shows its instruction straight away and ends with "Done"
  // (the Done of one step starts the next one), so "Go" is tapped once per run, not once per step.
  function idle() {
    stopPoll(); show("step"); run.marker = null;
    $("cp-progress").hidden = true; $("cp-text").hidden = true; $("cp-hint").hidden = true; $("cp-note-wrap").hidden = true;
    $("cp-go").hidden = false; $("cp-done").hidden = true;
  }
  var K = /[?&]fast=1/.test(location.search) ? 0.25 : 1;                  // test hook: ?fast=1 shortens every timer
  var timer = null;
  function stopTimer() { if (timer) { clearInterval(timer); timer = null; } $("cp-timer").hidden = true; }
  function countdown(sec, onEnd) {                                          // visible countdown with progress bar; onEnd fires once at 0
    var total = Math.max(1, Math.round(sec * K)), left = total, w = $("cp-wait"), bar = $("cp-bar");
    stopTimer(); $("cp-timer").hidden = false; w.textContent = fill(T.wait, [left]); bar.style.width = "0%";
    timer = setInterval(function () {
      left -= 1; bar.style.width = Math.round((total - left) * 100 / total) + "%";
      if (left <= 0) { stopTimer(); onEnd(); } else { w.textContent = fill(T.wait, [left]); }
    }, K < 1 ? 100 : 1000);
  }
  function header() { $("cp-check").textContent = fill(T.check, [run.g.label]); }
  function beginRest() {                                                    // phase 1: hands off, the noise of exactly this appliance state
    var me = run;
    stopPoll(); show("step"); header();
    $("cp-go").hidden = true; $("cp-done").hidden = true; $("cp-note-wrap").hidden = true; $("cp-hint").hidden = true;
    $("cp-progress").hidden = false; $("cp-progress").textContent = T.phase_rest;
    $("cp-text").hidden = false; $("cp-text").textContent = T.rest;
    post(base + "/markers", { kind: "rest", menu: menuValue(), step_group: run.group }).then(function (m) {
      if (run !== me) { post(base + "/markers/" + m.id + "/delete").then(function () {}, function () {}); return; }
      run.marker = m.id; remember(m);
      countdown(run.g.rest, function () {
        if (run !== me) { return; }
        post(base + "/markers/" + m.id + "/end", {}).then(function (e) {
          recent = recent.map(function (r) { return r.id === e.id ? e : r; }); renderList(); run.marker = null; beginStep();
        }, fail);
      });
    }, fail);
  }
  function beginStep() {                                                    // phase 2: the action; ends with "Done", then (if needed) phase 3: waiting
    var st = current(), total = run.g.steps.length * run.g.repeat;
    stopPoll(); stopTimer(); show("step"); header();
    $("cp-go").hidden = true; $("cp-done").hidden = true;
    $("cp-progress").hidden = false; $("cp-progress").textContent = fill(T.step, [run.i + 1, total]) + " \u00b7 " + fill(T.round, [Math.floor(run.i / run.g.steps.length) + 1]);
    $("cp-text").hidden = false; $("cp-text").textContent = st.text;
    $("cp-note").value = ""; $("cp-note-wrap").hidden = true; $("cp-hint").hidden = true;
    if (st.ask) { $("cp-note-label").textContent = T.note_label; }
    var me = run;
    post(base + "/markers", { kind: st.event, menu: menuValue(), step_group: run.group }).then(function (m) {
      if (run !== me) { return; }                                         // aborted meanwhile
      run.marker = m.id; run.since = m.ts; remember(m);
      $("cp-done").hidden = false;
      if (st.ask) { $("cp-note-wrap").hidden = false; $("cp-note").value = events[st.event].by_note ? lastNote : ""; }
      $("cp-hint").hidden = false; $("cp-hint").textContent = T.hint_none;   // immediately: nothing seen so far
      poll = setInterval(hint, 2500);
    }, fail);
  }
  $("cp-go").addEventListener("click", function () { if (run.g.rest > 0) { beginRest(); } else { beginStep(); } });
  function hint() {
    if (!run || !run.marker) { return; }
    fetch(base + "/activity?since=" + run.since, { credentials: "same-origin" }).then(function (r) { return r.json(); }).then(function (a) {
      $("cp-hint").textContent = a.baseline < 5 ? T.hint_nobase : (a.changes ? fill(T.hint_some, [a.changes]) : T.hint_none);
    }, function () {});
  }
  function nextStep() {
    run.i += 1;
    if (run.i >= run.g.steps.length * run.g.repeat) { run = null; $("cp-end-text").textContent = T.finished; show("end"); } else { beginStep(); }
  }
  $("cp-done").addEventListener("click", function () {
    var st = current(), note = $("cp-note").value.trim(), me = run;
    if (st.ask && !note) { $("cp-hint").hidden = false; $("cp-hint").textContent = T.note_needed; $("cp-note").focus(); return; }
    if (note) { lastNote = note; }
    stopPoll(); $("cp-done").hidden = true;
    post(base + "/markers/" + run.marker + "/end", { note: note }).then(function (m) {
      recent = recent.map(function (r) { return r.id === m.id ? e2(m) : r; }); renderList(); run.marker = null;
      if (st.hold) {                                                      // after the action: hold still and wait, with a progress bar
        $("cp-text").textContent = T.waiting; $("cp-note-wrap").hidden = true; $("cp-hint").hidden = true;
        countdown(st.hold, function () { if (run === me) { nextStep(); } });
      } else { nextStep(); }
    }, fail);
  });
  function e2(m) { return m; }
  $("cp-abort").addEventListener("click", function () {
    stopPoll(); stopTimer();
    var m = run && run.marker; run = null;
    if (m) { post(base + "/markers/" + m + "/delete").then(function () { recent = recent.filter(function (r) { return r.id !== m; }); renderList(); }, fail); }
    show(null);
  });
  $("cp-again").addEventListener("click", function () { show(null); });
  renderList(); show(null);
})();
