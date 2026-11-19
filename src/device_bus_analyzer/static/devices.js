// Device dialog: type -> manufacturer -> model suggestions from the catalogue; free text is always allowed.
(function () {
  var $ = function (id) { return document.getElementById(id); };
  var cat = JSON.parse($("catalog").getAttribute("data-catalog"));
  var dlg = $("device-dialog"), form = $("device-form");

  function fill(list, values) {
    list.replaceChildren();
    values.forEach(function (v) { var o = document.createElement("option"); o.value = v; list.appendChild(o); });
  }
  function manufacturer() {
    var n = $("f-man").value.trim();
    return cat.manufacturers.filter(function (m) { return m.name === n; })[0] || null;
  }
  function refresh() {
    var t = $("f-type").value.trim();
    var mans = cat.manufacturers.filter(function (m) { return !t || !m.types.length || m.types.indexOf(t) >= 0; });
    fill($("dl-mans"), mans.map(function (m) { return m.name; }));
    var m = manufacturer();
    fill($("dl-models"), m ? m.models : []);
    if (m && m.protocol && !$("f-proto").disabled) { $("f-proto").value = m.protocol; }   // protocol follows the manufacturer
  }
  function open(mode, d) {
    var edit = mode === "edit";
    form.action = edit ? "/devices/" + encodeURIComponent(d.name) : "/devices";
    $("dialog-title").textContent = $("catalog").getAttribute(edit ? "data-title-edit" : "data-title-new");
    $("f-name").value = edit ? d.name : ""; $("f-name").readOnly = edit;
    $("f-type").value = edit ? d.type : ""; $("f-man").value = edit ? d.manufacturer : ""; $("f-model").value = edit ? d.model : "";
    $("f-host").value = edit ? d.host : ""; $("f-port").value = edit ? d.port : 6053; $("f-key").value = "";
    $("f-enabled").checked = edit ? d.enabled === "1" : true;
    $("f-proto").value = edit ? d.protocol : $("f-proto").options[0].value;
    $("f-proto").disabled = edit; $("proto-note").hidden = !edit;       // protocol is fixed once the device exists
    $("key-note").hidden = !(edit && d.haskey); $("clear-key-row").hidden = !(edit && d.haskey);
    refresh();
    dlg.showModal();
  }
  $("new-device").addEventListener("click", function () { open("new"); });
  Array.prototype.forEach.call(document.querySelectorAll(".edit-device"), function (b) {
    b.addEventListener("click", function () {
      open("edit", { name: b.dataset.name, protocol: b.dataset.protocol, type: b.dataset.type, manufacturer: b.dataset.manufacturer,
        model: b.dataset.model, host: b.dataset.host, port: b.dataset.port, haskey: b.dataset.haskey, enabled: b.dataset.enabled });
    });
  });
  $("dialog-cancel").addEventListener("click", function () { dlg.close(); });
  ["f-type", "f-man"].forEach(function (id) { $(id).addEventListener("input", refresh); });
  refresh();
  if (dlg.getAttribute("data-open")) {          // server-side validation error: reopen with the entered values
    var editing = form.getAttribute("action") !== "/devices";
    if (editing) { $("f-name").readOnly = true; $("f-proto").disabled = true; $("proto-note").hidden = false; }
    dlg.showModal();
  } else if (new URLSearchParams(location.search).get("new")) { open("new"); }
})();
