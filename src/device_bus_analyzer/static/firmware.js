// Copy button for the firmware files. The Clipboard API needs HTTPS or localhost; on a plain LAN address fall back to a temporary textarea.
(function () {
  function copy(text) {
    if (navigator.clipboard && window.isSecureContext) { return navigator.clipboard.writeText(text); }
    return new Promise(function (resolve, reject) {
      var ta = document.createElement("textarea"); ta.value = text; ta.setAttribute("readonly", ""); ta.style.position = "fixed"; ta.style.opacity = "0";
      document.body.appendChild(ta); ta.select();
      try { document.execCommand("copy") ? resolve() : reject(); } catch (e) { reject(e); } finally { document.body.removeChild(ta); }
    });
  }
  [].forEach.call(document.querySelectorAll("button.copy"), function (b) {
    b.addEventListener("click", function () {
      var label = b.textContent, text = document.getElementById(b.dataset.target).textContent;
      copy(text).then(function () { b.textContent = b.dataset.ok; setTimeout(function () { b.textContent = label; }, 1800); }, function () {});
    });
  });
})();
