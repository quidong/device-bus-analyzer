// Device dialog: side sheet on wide screens (all fields), step-by-step wizard on phones. type -> manufacturer + bus -> model.
// Every manufacturer and every bus is offered for every type; the manufacturer presets its usual bus.
(function () {
  var $ = function (id) { return document.getElementById(id); };
  var dlg = $("device-dialog"), form = $("device-form");
  var cat = JSON.parse($("catalog").dataset.catalog), T = JSON.parse($("catalog").dataset.t);
  var mq = window.matchMedia("(max-width: 700px)"), step = 1, editing = false, lockedProto = "", lastMaker = null;
  var sets = [].slice.call(form.querySelectorAll("fieldset[data-step]"));
  var radios = function (n) { return [].slice.call(form.querySelectorAll('input[name="' + n + '"]')); };
  var checked = function (n) { return radios(n).filter(function (r) { return r.checked; })[0] || null; };

  function setRadio(name, value, otherId) {
    var rs = radios(name), hit = rs.filter(function (r) { return r.value === value; })[0];
    rs.forEach(function (r) { r.checked = false; }); $(otherId).value = "";
    if (value && hit) { hit.checked = true; }
    else if (value) { rs.filter(function (r) { return r.value === "__other"; })[0].checked = true; $(otherId).value = value; }
  }
  function val(name, otherId) { var c = checked(name); return !c ? "" : (c.value === "__other" ? $(otherId).value.trim() : c.value); }
  var typeValue = function () { return val("type_sel", "type-other"); }, makerValue = function () { return val("man_sel", "man-other"); };
  var maker = function () { var n = makerValue(); return cat.manufacturers.filter(function (m) { return m.name === n; })[0] || null; };

  function refresh() {
    var t = typeValue(), ct = checked("type_sel"), cm = checked("man_sel");
    $("type-other-wrap").hidden = !(ct && ct.value === "__other"); $("type-other").required = !$("type-other-wrap").hidden;
    $("man-other-wrap").hidden = !(cm && cm.value === "__other"); $("man-other").required = !$("man-other-wrap").hidden;
    var m = maker(), proto = $("f-proto"), mk = m ? m.name : (cm && cm.value === "__other" ? "__other" : "");
    if (!editing && mk !== lastMaker) {                                       // a new manufacturer presets its usual bus once;
      lastMaker = mk; if (m && m.protocol) { proto.value = m.protocol; }      // the user may still pick another one afterwards
    }
    $("proto-wrap").hidden = editing;                                         // the bus cannot change once the device exists
    $("decoder-name").textContent = editing ? lockedProto : proto.value || "–";
    var fw = $("fw-link"), p = $("decoder-name").textContent; fw.hidden = !p || p === "–"; fw.href = "/firmware/" + encodeURIComponent(p);
    var mt = (m && m.model_types) || {}, models = (m ? m.models : []).filter(function (x) {   // models known for this type (or any)
      var ts = mt[x] || []; return !t || !ts.length || ts.indexOf(t) >= 0;
    }), dl = $("dl-models"), chips = $("model-chips");
    dl.replaceChildren(); chips.replaceChildren();
    models.forEach(function (x) {
      var o = document.createElement("option"); o.value = x; dl.appendChild(o);
      var b = document.createElement("button"); b.type = "button"; b.className = "chip"; b.textContent = x;
      b.addEventListener("click", function () { $("f-model").value = x; }); chips.appendChild(b);
    });
  }

  function go(n) {
    step = n; var wiz = form.classList.contains("wizard");
    sets.forEach(function (fs) { fs.hidden = wiz && Number(fs.dataset.step) !== n; });
    [].forEach.call($("steps").children, function (li, i) { li.className = i + 1 < n ? "done" : (i + 1 === n ? "now" : ""); });
    $("wz-back").hidden = !(wiz && n > 1); $("wz-next").hidden = !(wiz && n < 4); $("save").hidden = wiz && n < 4;
    $("dialog-cancel").hidden = wiz;
  }
  function validStep(n) {
    var fs = sets[n - 1], els = [].slice.call(fs.querySelectorAll("input,select"));
    for (var i = 0; i < els.length; i++) { if (!els[i].disabled && !els[i].checkValidity()) { els[i].reportValidity(); return false; } }
    return true;
  }
  $("wz-next").addEventListener("click", function () { if (validStep(step)) { go(step + 1); refresh(); } });
  $("wz-back").addEventListener("click", function () { go(step - 1); });
  mq.addEventListener("change", function () { form.classList.toggle("wizard", mq.matches); go(mq.matches ? 1 : step); });

  function open(mode, d) {
    editing = mode === "edit"; d = d || {}; lockedProto = d.protocol || "";
    form.reset(); lastMaker = null;
    form.action = editing ? "/devices/" + encodeURIComponent(d.name) : "/devices";
    $("dialog-title").textContent = editing ? T.edit : T["new"];
    $("f-name").value = d.name || ""; $("f-name").readOnly = editing;
    setRadio("type_sel", d.type || "", "type-other"); setRadio("man_sel", d.manufacturer || "", "man-other");
    $("f-model").value = d.model || ""; $("f-host").value = d.host || ""; $("f-port").value = d.port || 6053; $("f-key").value = "";
    $("f-enabled").checked = editing ? d.enabled === "1" : true;
    $("f-proto").disabled = editing; if (d.protocol) { $("f-proto").value = d.protocol; }
    if (!editing && d.protocol) {                                    // re-opened after an error: keep the chosen bus
      var cm = checked("man_sel"); lastMaker = maker() ? maker().name : (cm && cm.value === "__other" ? "__other" : "");
    }
    $("key-note").hidden = !(editing && d.haskey); $("clear-key-row").hidden = !(editing && d.haskey);
    var del = $("delete-link"); del.hidden = !editing; if (editing) { del.href = "/devices/" + encodeURIComponent(d.name) + "/delete"; }
    form.classList.toggle("wizard", mq.matches); refresh(); go(1);
    if (!dlg.open) { dlg.showModal(); }
  }
  form.addEventListener("submit", function () { $("h-type").value = typeValue(); $("h-man").value = makerValue(); });
  form.addEventListener("input", refresh); form.addEventListener("change", refresh);
  var close = function () { dlg.close(); };
  $("dialog-x").addEventListener("click", close); $("dialog-cancel").addEventListener("click", close);
  dlg.addEventListener("click", function (e) { if (e.target === dlg) { close(); } });
  ["new-device", "add-tile"].forEach(function (id) { $(id).addEventListener("click", function () { open("new"); }); });
  [].forEach.call(document.querySelectorAll(".edit-device"), function (b) {
    b.addEventListener("click", function () { open("edit", b.dataset); });
  });
  if (dlg.dataset.form) {                                           // server-side validation error: reopen with the entered values
    var f = JSON.parse(dlg.dataset.form), btn = document.querySelector('.edit-device[data-name="' + f.name + '"]');
    open(f.creating ? "new" : "edit", Object.assign({}, btn ? btn.dataset : {}, f, { enabled: f.enabled ? "1" : "" }));
  } else if (new URLSearchParams(location.search).get("new")) { open("new"); }
})();
