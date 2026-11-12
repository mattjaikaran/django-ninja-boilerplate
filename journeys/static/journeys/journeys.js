/* Interactions for the staff journeys pages.
   Loaded as an external file so the production CSP (script-src 'self')
   allows it. Uses only classes, the hidden and open attributes, and
   text content. It never writes element.style. */
(function () {
  "use strict";

  function initIndex() {
    var search = document.getElementById("jr-search");
    var count = document.getElementById("jr-count");
    var empty = document.getElementById("jr-empty");
    var cards = Array.prototype.slice.call(document.querySelectorAll(".jr-card"));
    var filters = Array.prototype.slice.call(document.querySelectorAll(".jr-filter"));
    if (!search || !count || !empty || cards.length === 0) {
      return;
    }

    var activeFilter = "all";

    function apply() {
      var query = search.value.trim().toLowerCase();
      var visible = 0;

      cards.forEach(function (card) {
        var matchesStatus =
          activeFilter === "all" || card.getAttribute("data-status") === activeFilter;
        var haystack = (card.getAttribute("data-search") || "").toLowerCase();
        var matchesQuery = query === "" || haystack.indexOf(query) !== -1;
        var show = matchesStatus && matchesQuery;
        card.hidden = !show;
        if (show) {
          visible += 1;
        }
      });

      filters.forEach(function (button) {
        var pressed = button.getAttribute("data-filter") === activeFilter;
        button.setAttribute("aria-pressed", pressed ? "true" : "false");
      });

      count.textContent =
        "Showing " + visible + " of " + cards.length + " journeys.";
      empty.hidden = visible !== 0;
    }

    search.addEventListener("input", apply);

    filters.forEach(function (button) {
      button.addEventListener("click", function () {
        activeFilter = button.getAttribute("data-filter") || "all";
        apply();
      });
    });

    apply();
  }

  function initDetail() {
    var expandButtons = Array.prototype.slice.call(
      document.querySelectorAll("[data-expand]")
    );
    var steps = Array.prototype.slice.call(
      document.querySelectorAll("details.jr-step")
    );
    if (steps.length === 0) {
      return;
    }

    expandButtons.forEach(function (button) {
      button.addEventListener("click", function () {
        var open = button.getAttribute("data-expand") === "open";
        steps.forEach(function (step) {
          step.open = open;
        });
      });
    });

    // Open the step named in the URL fragment, such as #J-001-S2.
    var hash = window.location.hash.slice(1);
    if (hash) {
      var target = document.getElementById(hash);
      if (target && target.classList.contains("jr-flow-item")) {
        var details = target.querySelector("details.jr-step");
        if (details) {
          details.open = true;
        }
      }
    }
  }

  function ready(fn) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", fn);
    } else {
      fn();
    }
  }

  ready(function () {
    initIndex();
    initDetail();
  });
})();
