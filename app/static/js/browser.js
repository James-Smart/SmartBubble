const state = { resolve: null };

function hostFromUrl(url) {
  try {
    return new URL(url).host;
  } catch (_) {
    // The URL in a demo message is fake and may not parse. Show it as typed.
    return url.replace(/^https?:\/\//, "").split("/")[0];
  }
}

export function openBrowser(url) {
  const browser = document.getElementById("browser");
  const content = document.getElementById("browser-content");
  const host = hostFromUrl(url);

  document.getElementById("browser-host").textContent = host;
  document.querySelectorAll(".perm-host").forEach((el) => {
    el.textContent = host;
  });
  content.textContent = "";
  browser.classList.add("open");
  return content;
}

function closeBrowser() {
  const browser = document.getElementById("browser");
  browser.classList.remove("open");
  hidePermission(false);
}

function hidePermission(answer) {
  document.getElementById("perm-backdrop").classList.remove("open");
  if (state.resolve) {
    const resolve = state.resolve;
    state.resolve = null;
    resolve(answer);
  }
}

export function askPermission() {
  document.getElementById("perm-backdrop").classList.add("open");
  return new Promise((resolve) => {
    state.resolve = resolve;
  });
}

export function initBrowser() {
  document.getElementById("browser-done").addEventListener("click", closeBrowser);

  document.querySelectorAll(".perm-allow").forEach((btn) => {
    btn.addEventListener("click", () => hidePermission(true));
  });
  document.querySelectorAll(".perm-deny").forEach((btn) => {
    btn.addEventListener("click", () => hidePermission(false));
  });

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    const backdrop = document.getElementById("perm-backdrop");
    // Escape backs out of the prompt first, then out of the page.
    if (backdrop.classList.contains("open")) {
      hidePermission(false);
    } else {
      closeBrowser();
    }
  });
}
