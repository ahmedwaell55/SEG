(function () {
  const API_BASE = window.location.protocol === "file:" ? "http://127.0.0.1:8000" : "";
  const TOKEN_KEY = "ai_closer_access_token";
  const USER_KEY = "ai_closer_user";

  function getToken() {
    return localStorage.getItem(TOKEN_KEY);
  }

  function setSession(token, user) {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user || {}));
  }

  function clearSession() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  }

  function loginUrl() {
    const next = window.location.pathname === "/login" ? "" : `?next=${encodeURIComponent(window.location.pathname + window.location.search)}`;
    return `/login${next}`;
  }

  function redirectToLogin() {
    clearSession();
    if (window.location.pathname !== "/login") {
      window.location.href = loginUrl();
    }
  }

  function requireAuth() {
    if (window.location.pathname === "/login") return true;
    if (!getToken()) {
      redirectToLogin();
      return false;
    }
    return true;
  }

  async function apiFetch(path, options = {}) {
    const token = getToken();
    const response = await fetch(`${API_BASE}${path}`, {
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(options.headers || {}),
      },
      ...options,
    });

    if (response.status === 401) {
      redirectToLogin();
      throw new Error("Authentication required");
    }

    if (response.status === 204) {
      return null;
    }

    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = payload.detail || "Request failed";
      throw new Error(Array.isArray(detail) ? detail.map((item) => item.msg).join(", ") : detail);
    }
    return payload;
  }

  function formatDate(value) {
    if (!value) return "-";
    const date = new Date(`${value}T00:00:00`);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
  }

  function acceptanceClass(label) {
    const value = String(label || "unknown").toLowerCase();
    if (value === "high") return "high";
    if (value === "medium") return "medium";
    if (value === "low") return "low";
    return "unknown";
  }

  function acceptanceBadge(label, probability) {
    if (!label) return '<span class="badge unknown">No data</span>';
    const score = Number.isFinite(Number(probability)) ? ` ${probability}%` : "";
    return `<span class="badge ${acceptanceClass(label)}">${label}${score}</span>`;
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function listMarkup(items) {
    const safe = Array.isArray(items) ? items.filter(Boolean).map((item) => normalizeListItem(item)).filter(Boolean) : [];
    if (!safe.length) return "<p>No items detected.</p>";
    return `<ul>${safe.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
  }

  function normalizeListItem(item) {
    if (item == null) return "";
    if (typeof item === "string") {
      return item
        .replace(/<[^:>]+:\s*'([^']+)'>/g, "$1")
        .replace(/\s+/g, " ")
        .trim();
    }
    if (typeof item !== "object") {
      return String(item).trim();
    }

    const objection = item.objection || item.text || item.value || "";
    const signal = item.signal || "";
    const category = item.category || "";
    const severity = item.severity || "";
    const strength = item.strength || "";
    const evidence = item.verbatim_evidence || "";

    const title = objection || signal || "";
    const parts = [title];
    if (category) parts.push(`Category: ${category}`);
    if (severity) parts.push(`Severity: ${severity}`);
    if (strength) parts.push(`Strength: ${strength}`);
    if (evidence) parts.push(`Evidence: "${evidence}"`);

    if (parts.length > 0 && parts[0]) return parts.join(" | ");

    const generic = Object.entries(item)
      .map(([key, value]) => `${key}: ${String(value)}`)
      .join(" | ");
    return generic.trim();
  }

  let toastTimer;
  function toast(message) {
    const node = document.getElementById("toast");
    if (!node) return;
    node.textContent = message;
    node.classList.add("visible");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => node.classList.remove("visible"), 3400);
  }

  async function logout() {
    const token = getToken();
    try {
      if (token) {
        await fetch(`${API_BASE}/auth/logout`, {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
        });
      }
    } finally {
      clearSession();
      window.location.href = "/login";
    }
  }

  function ensureLogoutButton() {
    const nav = document.querySelector(".nav-actions");
    if (!nav || document.getElementById("logoutButton")) return;
    const button = document.createElement("button");
    button.className = "icon-button logout-button";
    button.id = "logoutButton";
    button.type = "button";
    button.title = "Log out";
    button.textContent = "Log Out";
    nav.appendChild(button);
  }

  function wireLogoutButton() {
    ensureLogoutButton();
    const button = document.getElementById("logoutButton");
    if (button) {
      button.addEventListener("click", logout);
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    if (requireAuth()) {
      wireLogoutButton();
    }
  });

  window.AICloser = {
    apiFetch,
    clearSession,
    formatDate,
    acceptanceBadge,
    acceptanceClass,
    escapeHtml,
    getToken,
    listMarkup,
    logout,
    requireAuth,
    setSession,
    toast,
    apiBase: API_BASE,
  };
})();
