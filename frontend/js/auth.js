const API = "https://microtarefas-production.up.railway.app";

const alertEl = document.getElementById("alert");
const stepEmail = document.getElementById("step-email");
const stepOtp = document.getElementById("step-otp");

let currentEmail = "";

function showAlert(message, type = "error") {
  alertEl.textContent = message;
  alertEl.className = `alert alert-${type} show`;
}

function hideAlert() {
  alertEl.className = "alert";
}

function setLoading(btn, loading) {
  btn.disabled = loading;
  btn.textContent = loading ? "Aguarde..." : btn.dataset.label;
}

// Passo 1 — solicitar OTP
document.getElementById("form-email").addEventListener("submit", async (e) => {
  e.preventDefault();
  hideAlert();

  const btn = document.getElementById("btn-email");
  btn.dataset.label = "Enviar código";
  setLoading(btn, true);

  const email = document.getElementById("email").value.trim();

  try {
    const res = await fetch(`${API}/auth/runner/request-otp`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });

    const data = await res.json();

    if (!res.ok) {
      showAlert(data.detail || "Erro ao enviar código.");
      return;
    }

    currentEmail = email;
    document.getElementById("otp-hint").textContent = `Código enviado para ${email}.`;
    stepEmail.classList.remove("active");
    stepOtp.classList.add("active");

    if (data.dev_otp) {
      document.getElementById("otp").value = data.dev_otp;
      showAlert(`[DEV] OTP: ${data.dev_otp}`, "success");
    } else {
      document.getElementById("otp").focus();
    }
  } catch {
    showAlert("Erro de conexão com o servidor.");
  } finally {
    setLoading(btn, false);
  }
});

// Passo 2 — verificar OTP
document.getElementById("form-otp").addEventListener("submit", async (e) => {
  e.preventDefault();
  hideAlert();

  const btn = document.getElementById("btn-otp");
  btn.dataset.label = "Entrar";
  setLoading(btn, true);

  const code = document.getElementById("otp").value.trim();

  try {
    const res = await fetch(`${API}/auth/runner/verify-otp`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: currentEmail, code }),
    });

    const data = await res.json();

    if (!res.ok) {
      showAlert(data.detail || "Código inválido.");
      return;
    }

    localStorage.setItem("token", data.access_token);
    localStorage.setItem("runner", JSON.stringify(data.runner));
    window.location.href = "dashboard.html";
  } catch {
    showAlert("Erro de conexão com o servidor.");
  } finally {
    setLoading(btn, false);
  }
});

// Reenviar código
document.getElementById("btn-resend").addEventListener("click", async () => {
  hideAlert();
  try {
    const res = await fetch(`${API}/auth/runner/request-otp`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: currentEmail }),
    });
    const data = await res.json();
    if (res.ok) {
      showAlert("Novo código enviado!", "success");
    } else {
      showAlert(data.detail || "Erro ao reenviar.");
    }
  } catch {
    showAlert("Erro de conexão com o servidor.");
  }
});

// Redirecionar se já logado
if (localStorage.getItem("token")) {
  window.location.href = "dashboard.html";
}
