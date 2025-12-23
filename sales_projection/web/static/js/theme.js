(function () {
  const key = "sales_projection_theme";
  const root = document.documentElement;

  function prefersReducedMotion() {
    return window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  function setTransition(on) {
    if (prefersReducedMotion()) return;
    if (on) {
      root.style.transition = "background-color 220ms ease, color 220ms ease";
      // also help common elements feel smooth without heavy CSS edits
      document.body.style.transition = "background 220ms ease, color 220ms ease";
    } else {
      root.style.transition = "";
      document.body.style.transition = "";
    }
  }

  function apply(theme) {
    if (theme === "light") root.setAttribute("data-theme", "light");
    else root.removeAttribute("data-theme");
    syncToggleUI();
  }

  function getCurrentTheme() {
    return root.getAttribute("data-theme") === "light" ? "light" : "dark";
  }

  function syncToggleUI() {
    const btn = document.getElementById("themeToggle");
    if (!btn) return;

    const current = getCurrentTheme();
    if (current === "light") {
      btn.textContent = "🌙 Dark Mode";
      btn.setAttribute("title", "Switch to dark mode");
    } else {
      btn.textContent = "☀️ Light Mode";
      btn.setAttribute("title", "Switch to light mode");
    }
  }

  // Apply saved theme ASAP to avoid flash
  const saved = localStorage.getItem(key);
  if (saved) apply(saved);
  else syncToggleUI();

  document.addEventListener("DOMContentLoaded", () => {
    syncToggleUI();

    const btn = document.getElementById("themeToggle");
    if (!btn) return;

    btn.addEventListener("click", () => {
      setTransition(true);

      const current = getCurrentTheme();
      const next = current === "light" ? "dark" : "light";

      localStorage.setItem(key, next);
      apply(next);

      // remove transition after it finishes (keeps CSS clean)
      window.setTimeout(() => setTransition(false), 260);
    });
  });
})();
