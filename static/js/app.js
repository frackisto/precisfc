/*
 * Comportements communs du site.
 *
 * 1. Jeton CSRF ajouté automatiquement à toutes les requêtes AJAX qui modifient des
 *    données (fetch et jQuery) : sans lui, Django les refuse (erreur 403).
 * 2. Bascule clair / sombre sans rechargement (le formulaire fonctionne aussi sans JS).
 */
(function () {
  "use strict";

  var SAFE_METHODS = /^(GET|HEAD|OPTIONS|TRACE)$/i;

  function csrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute("content") : "";
  }

  function isSameOrigin(url) {
    var target = new URL(url, window.location.href);
    return target.origin === window.location.origin;
  }

  // --- 1. CSRF : fetch ---------------------------------------------------------
  var nativeFetch = window.fetch;
  window.fetch = function (resource, options) {
    options = options || {};
    var method = options.method || (resource instanceof Request ? resource.method : "GET");
    var url = resource instanceof Request ? resource.url : String(resource);
    if (!SAFE_METHODS.test(method) && isSameOrigin(url)) {
      var headers = new Headers(options.headers || (resource instanceof Request ? resource.headers : {}));
      if (!headers.has("X-CSRFToken")) {
        headers.set("X-CSRFToken", csrfToken());
      }
      options.headers = headers;
      options.credentials = options.credentials || "same-origin";
    }
    return nativeFetch.call(window, resource, options);
  };

  // --- 1. CSRF : jQuery ----------------------------------------------------------
  if (window.jQuery) {
    window.jQuery.ajaxSetup({
      beforeSend: function (xhr, settings) {
        if (!SAFE_METHODS.test(settings.type) && isSameOrigin(settings.url)) {
          xhr.setRequestHeader("X-CSRFToken", csrfToken());
        }
      }
    });
  }

  // --- 2. Thème clair / sombre ---------------------------------------------------
  document.addEventListener("submit", function (event) {
    var form = event.target.closest("[data-theme-toggle]");
    if (!form) {
      return;
    }
    event.preventDefault();
    var root = document.documentElement;
    var next = root.getAttribute("data-bs-theme") === "dark" ? "light" : "dark";
    root.setAttribute("data-bs-theme", next);
    root.setAttribute("data-theme-choice", next);

    var button = form.querySelector("button[name=theme]");
    button.value = next === "dark" ? "light" : "dark";
    button.setAttribute("aria-label", next === "dark" ? "Passer en mode clair" : "Passer en mode sombre");

    var data = new FormData(form);
    data.set("theme", next);
    fetch(form.action, { method: "POST", body: data, redirect: "manual" });
  });
})();
