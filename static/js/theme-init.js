// Loaded without defer: applies a saved colour theme before the first paint, so there is no flash.
(function () {
  try {
    var theme = localStorage.getItem("theme");
    if (theme === "light" || theme === "dark") {
      document.documentElement.dataset.theme = theme;
    }
  } catch (error) {
    // Storage blocked: follow the system setting.
  }
})();
