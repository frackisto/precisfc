/*
 * Chargé dans <head>, avant l'affichage : évite un « flash » de la mauvaise couleur.
 * - remplace la classe no-js par js (le menu replié devient utilisable) ;
 * - en mode « automatique », suit la préférence du système (clair ou sombre).
 * Sans JavaScript, la page reste en mode clair, ou dans le mode choisi par cookie.
 */
(function () {
  var root = document.documentElement;
  root.classList.remove("no-js");
  root.classList.add("js");
  if (root.getAttribute("data-theme-choice") === "auto" && window.matchMedia) {
    var prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    root.setAttribute("data-bs-theme", prefersDark ? "dark" : "light");
  }
})();
