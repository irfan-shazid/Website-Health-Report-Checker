// Progressive enhancements. Every page works without JavaScript; the theme switch
// stays hidden until this runs because it can't do anything without it.
(function () {
  "use strict";

  var root = document.documentElement;

  // Theme switch: System / Light / Dark, remembered in localStorage.

  function savedTheme() {
    try {
      var theme = localStorage.getItem("theme");
      return theme === "light" || theme === "dark" ? theme : "system";
    } catch (error) {
      return "system";
    }
  }

  function saveTheme(theme) {
    try {
      if (theme === "system") localStorage.removeItem("theme");
      else localStorage.setItem("theme", theme);
    } catch (error) {
      // Storage blocked: the choice lasts for this page only.
    }
  }

  function applyTheme(theme) {
    var explicit = theme === "light" || theme === "dark";
    if (explicit) root.dataset.theme = theme;
    else delete root.dataset.theme;

    // Browser toolbar colour: the chosen theme's, or back to following the system.
    document.querySelectorAll('meta[name="theme-color"]').forEach(function (meta) {
      var systemScheme = (meta.media || "").indexOf("dark") >= 0 ? "dark" : "light";
      meta.content = meta.getAttribute("data-" + (explicit ? theme : systemScheme));
    });
  }

  function checkThemeRadios(theme) {
    document.querySelectorAll("[data-theme-switch] input[name=theme]").forEach(function (input) {
      input.checked = input.value === theme;
    });
  }

  function initThemeSwitch() {
    var switches = document.querySelectorAll("[data-theme-switch]");
    if (!switches.length) return;

    checkThemeRadios(savedTheme());
    switches.forEach(function (group) {
      group.hidden = false;
      group.addEventListener("change", function (event) {
        applyTheme(event.target.value);
        saveTheme(event.target.value);
      });
    });

    // Keep other open tabs in step.
    window.addEventListener("storage", function (event) {
      if (event.key !== "theme") return;
      var theme = savedTheme();
      applyTheme(theme);
      checkThemeRadios(theme);
    });
  }

  // Password fields: a Show/Hide button and a Caps Lock warning.

  function initPasswordFields() {
    document.querySelectorAll("[data-password-toggle]").forEach(function (button) {
      var input = document.getElementById(button.getAttribute("aria-controls"));
      var label = button.querySelector("[data-toggle-label]");
      if (!input || !label) return;

      button.hidden = false;
      button.addEventListener("click", function () {
        var reveal = input.type === "password";
        input.type = reveal ? "text" : "password";
        label.textContent = reveal ? "Hide" : "Show";
      });
      // Never submit (or let the browser remember) the field while it is visible.
      if (input.form) {
        input.form.addEventListener("submit", function () {
          input.type = "password";
          label.textContent = "Show";
        });
      }
    });

    document.querySelectorAll("[data-caps-lock-hint]").forEach(function (hint) {
      var input = document.getElementById(hint.dataset.capsLockHint);
      if (!input) return;

      function update(event) {
        if (!event.getModifierState) return;
        hint.textContent = event.getModifierState("CapsLock") ? "Caps Lock is on." : "";
      }
      input.addEventListener("keydown", update);
      input.addEventListener("keyup", update);
      input.addEventListener("blur", function () {
        hint.textContent = "";
      });
    });
  }

  // Forms: show a pending label on submit and block accidental double submits.

  function initPendingForms() {
    document.querySelectorAll("form").forEach(function (form) {
      form.addEventListener("submit", function (event) {
        if (form.dataset.submitting === "true") {
          event.preventDefault();
          return;
        }
        form.dataset.submitting = "true";
        var button = form.querySelector("[data-pending-label]");
        if (button) {
          button.dataset.idleLabel = button.textContent;
          button.textContent = button.dataset.pendingLabel;
          button.setAttribute("aria-disabled", "true");
        }
      });
    });

    // Coming back with the Back button restores the page from cache; make the form usable again.
    window.addEventListener("pageshow", function (event) {
      if (!event.persisted) return;
      document.querySelectorAll("form[data-submitting]").forEach(function (form) {
        delete form.dataset.submitting;
        var button = form.querySelector("[data-pending-label]");
        if (button && button.dataset.idleLabel) {
          button.textContent = button.dataset.idleLabel;
          button.removeAttribute("aria-disabled");
        }
      });
    });
  }

  // Move focus to an error summary so screen readers announce it and keyboard users start there.

  function focusErrorSummary() {
    var summary = document.querySelector("[data-focus-on-load]");
    if (summary) summary.focus();
  }

  initThemeSwitch();
  initPasswordFields();
  initPendingForms();
  focusErrorSummary();
})();
