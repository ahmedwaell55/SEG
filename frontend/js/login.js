(function () {
  const form = document.getElementById("loginForm");
  const username = document.getElementById("username");
  const password = document.getElementById("password");
  const message = document.getElementById("loginMessage");
  const submit = document.getElementById("loginSubmit");

  if (window.AICloser.getToken()) {
    window.location.href = "/";
    return;
  }

  function setMessage(text, type = "error") {
    if (!message) return;
    message.textContent = text;
    message.dataset.type = type;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    setMessage("");
    submit.disabled = true;
    submit.textContent = "Signing in...";

    try {
      const response = await fetch(`${window.AICloser.apiBase}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: username.value.trim(),
          password: password.value,
        }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(payload.detail || "Invalid username or password");
      }
      window.AICloser.setSession(payload.access_token, payload.user);
      const next = new URLSearchParams(window.location.search).get("next") || "/";
      window.location.href = next.startsWith("/") ? next : "/";
    } catch (error) {
      setMessage(error.message || "Login failed");
    } finally {
      submit.disabled = false;
      submit.textContent = "Log In";
    }
  });
})();
