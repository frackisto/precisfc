/*
 * Tableau de bord : tableaux triables (DataTables) et graphiques (Chart.js).
 * Sans JavaScript, les tableaux restent complets et chaque graphique a ses chiffres
 * dans un tableau voisin : rien n'est perdu.
 */
(function () {
  "use strict";

  var FRENCH = {
    emptyTable: "Aucune donnée",
    info: "Lignes _START_ à _END_ sur _TOTAL_",
    infoEmpty: "Aucune ligne",
    infoFiltered: "(filtrées parmi _MAX_)",
    lengthMenu: "_MENU_ lignes par page",
    loadingRecords: "Chargement…",
    search: "Rechercher :",
    zeroRecords: "Aucun résultat",
    paginate: { first: "Première", last: "Dernière", next: "Suivante", previous: "Précédente" },
    aria: { orderable: "Trier par cette colonne", orderableReverse: "Inverser le tri" }
  };

  // --- Tableaux -------------------------------------------------------------------
  if (window.DataTable) {
    document.querySelectorAll("table[data-datatable]").forEach(function (table) {
      new window.DataTable(table, { language: FRENCH, pageLength: 25, order: [] });
    });
  }

  // --- Graphiques -----------------------------------------------------------------
  if (!window.Chart) {
    return;
  }
  var styles = getComputedStyle(document.documentElement);
  var dark = document.documentElement.getAttribute("data-bs-theme") === "dark";
  function color(name, fallback) {
    return styles.getPropertyValue(name).trim() || fallback;
  }
  // Mêmes couleurs que les pastilles de légende (site.css).
  var palette = [
    color("--pfc-link", "#0B1F3A"),
    dark ? color("--pfc-light", "#E9ECEF") : color("--pfc-accent", "#C9A227"),
    "#6C757D",
    dark ? color("--pfc-accent", "#C9A227") : color("--pfc-light", "#E9ECEF")
  ];
  var text = color("--bs-body-color", "#212529");
  var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var money = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 });
  function fcfa(value) {
    return money.format(value) + " FCFA";
  }

  document.querySelectorAll("canvas[data-chart]").forEach(function (canvas) {
    var source = document.getElementById(canvas.getAttribute("data-chart"));
    if (!source) {
      return;
    }
    var data = JSON.parse(source.textContent);
    var type = canvas.getAttribute("data-chart-type");
    var doughnut = type === "doughnut";
    var datasets = data.series.map(function (serie, index) {
      return {
        label: serie.label,
        data: serie.values,
        backgroundColor: doughnut ? palette : palette[index % palette.length],
        borderRadius: doughnut ? 0 : 4
      };
    });
    var tooltip = {
      callbacks: {
        label: function (context) {
          var value = doughnut ? context.parsed : context.parsed.y;
          return (doughnut ? context.label : context.dataset.label) + " : " + fcfa(value);
        }
      }
    };
    var options = {
      maintainAspectRatio: false,
      animation: reduceMotion ? false : undefined,
      plugins: { legend: { labels: { color: text } }, tooltip: tooltip }
    };
    if (!doughnut) {
      options.scales = {
        x: { stacked: true, ticks: { color: text } },
        y: { stacked: true, beginAtZero: true, ticks: { color: text, callback: function (value) { return money.format(value); } } }
      };
    }
    new window.Chart(canvas, { type: doughnut ? "doughnut" : "bar", data: { labels: data.labels, datasets: datasets }, options: options });
  });
})();
