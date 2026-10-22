/*
 * Graphique des meilleurs buteurs (page de classement).
 * Les données viennent d'un bloc JSON produit par le serveur (json_script) ; le même
 * contenu figure dans le tableau en dessous, lisible sans JavaScript.
 */
(function () {
  "use strict";

  var canvas = document.getElementById("graphique-buteurs");
  var source = document.getElementById("donnees-buteurs");
  if (!canvas || !source || !window.Chart) {
    return;
  }
  var data = JSON.parse(source.textContent);
  var styles = getComputedStyle(document.documentElement);
  var primary = styles.getPropertyValue("--pfc-link").trim() || "#0B1F3A";
  var text = styles.getPropertyValue("--bs-body-color").trim() || "#212529";
  var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  new window.Chart(canvas, {
    type: "bar",
    data: {
      labels: data.labels,
      datasets: [{ label: "Buts", data: data.values, backgroundColor: primary, borderRadius: 4 }]
    },
    options: {
      indexAxis: "y",
      animation: reduceMotion ? false : undefined,
      plugins: { legend: { display: false } },
      scales: {
        x: { beginAtZero: true, ticks: { precision: 0, color: text } },
        y: { ticks: { color: text } }
      }
    }
  });
})();
