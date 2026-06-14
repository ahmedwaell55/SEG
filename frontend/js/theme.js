(function () {
  const key = "ai-closer-theme";
  const saved = localStorage.getItem(key);
  if (saved === "dark") {
    document.documentElement.dataset.theme = "dark";
  }

  function syncButton() {
    const button = document.getElementById("themeToggle");
    if (!button) return;
    button.textContent = document.documentElement.dataset.theme === "dark" ? "Light" : "Dark";
  }

  document.addEventListener("DOMContentLoaded", () => {
    const button = document.getElementById("themeToggle");
    syncButton();
    if (!button) return;
    button.addEventListener("click", () => {
      const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
      if (next === "dark") {
        document.documentElement.dataset.theme = "dark";
      } else {
        delete document.documentElement.dataset.theme;
      }
      localStorage.setItem(key, next);
      syncButton();
    });
  });
})();

