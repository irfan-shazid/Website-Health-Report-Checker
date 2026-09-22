// Loaded without defer: applies a saved colour theme before the first paint, so there is no flash.
(function () {
  try {
    var theme = localStorage.getItem("theme");
    if (theme === "light" || theme === "dark") {
      document.documentElement.dataset.theme = theme;
      // The theme-color tags are above this script, so they already exist.
      document.querySelectorAll('meta[name="theme-color"]').forEach(function (meta) {
        meta.content = meta.getAttribute("data-" + theme);
      });
    }
  } catch (error) {
    // Storage blocked: follow the system setting.
  }
})();
