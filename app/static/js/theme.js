const STORAGE_KEY = "smartbubble-theme";

export function initTheme() {
  const html = document.documentElement;
  const buttons = document.querySelectorAll(".theme-btn");

  function applyTheme(theme) {
    html.setAttribute("data-theme", theme);
    buttons.forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.theme === theme);
    });
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch (_) {
      /* ignore */
    }
  }

  let saved = null;
  try {
    saved = localStorage.getItem(STORAGE_KEY);
  } catch (_) {
    /* ignore */
  }
  if (saved === "ios" || saved === "android") {
    applyTheme(saved);
  }

  buttons.forEach((btn) => {
    btn.addEventListener("click", () => applyTheme(btn.dataset.theme));
  });
}
