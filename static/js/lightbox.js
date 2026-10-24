/*
 * Visionneuse des albums photo (fenêtre Bootstrap, flèches du clavier).
 * Sans JavaScript, chaque vignette reste un lien vers la photo en grand.
 */
(function () {
  "use strict";

  var grid = document.querySelector("[data-lightbox]");
  var element = document.getElementById("visionneuse");
  if (!grid || !element || !window.bootstrap) {
    return;
  }
  var links = Array.prototype.slice.call(grid.querySelectorAll("[data-lightbox-item]"));
  var image = element.querySelector("[data-lightbox-image]");
  var caption = element.querySelector("[data-lightbox-caption]");
  var counter = element.querySelector("[data-lightbox-counter]");
  var modal = new window.bootstrap.Modal(element);
  var current = 0;

  function show(index) {
    current = (index + links.length) % links.length;
    var link = links[current];
    var thumbnail = link.querySelector("img");
    image.src = link.href;
    image.alt = thumbnail ? thumbnail.alt : "";
    caption.textContent = link.getAttribute("data-caption") || "";
    counter.textContent = (current + 1) + " / " + links.length;
  }

  links.forEach(function (link, index) {
    link.addEventListener("click", function (event) {
      event.preventDefault();
      show(index);
      modal.show();
    });
  });
  element.querySelector("[data-lightbox-prev]").addEventListener("click", function () { show(current - 1); });
  element.querySelector("[data-lightbox-next]").addEventListener("click", function () { show(current + 1); });
  element.addEventListener("keydown", function (event) {
    if (event.key === "ArrowLeft") { show(current - 1); }
    if (event.key === "ArrowRight") { show(current + 1); }
  });
})();
