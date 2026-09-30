const $ = (selector) => document.querySelector(selector);
const userPattern = /^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/;
const eventNames = {
  provider_registered: "Provider registered",
  provider_updated: "Provider settings updated",
  consent_started: "Consent link created",
  connected: "Identity connected",
  consent_denied: "Consent declined",
  request_queued: "Token request queued",
  request_succeeded: "Token ready",
  request_failed: "Token request failed",
};
const traceKey = "aggregator-demo-trace";
let providerNames = new Set();
let activeTab = "mock";
let busy = false;
let trace = [];

function safeUser(value) {
  const user = value.trim();
  if (!userPattern.test(user)) throw new Error("Use letters, numbers, dots, underscores, or hyphens (up to 64 characters).");
  return user;
}

function setMessage(message, isError = false) {
  const element = $("#demo-message");
  element.textContent = message;
  element.classList.toggle("error", isError);
}

function setBusy(value) {
  busy = value;
  $("#start-mock").disabled = value;
  $("#start-github").disabled = value;
}

function setStep(step, caption) {
  for (const item of document.querySelectorAll("#journey li")) {
    const number = Number(item.dataset.step);
    item.classList.toggle("complete", number < step || (step === 6 && number === 5));
    item.classList.toggle("active", number === step);
    item.querySelector(".step-state").textContent = number < step || step === 6 ? "Done" : number === step ? "Now" : "Waiting";
  }
  $("#journey-label").textContent = step === 6 ? "COMPLETE" : step > 0 ? "IN PROGRESS" : "WAITING";
  $("#journey-label").classList.toggle("neutral", step === 0);
  $("#flow-caption").textContent = caption;
}

function saveTrace() {
  try { sessionStorage.setItem(traceKey, JSON.stringify(trace.slice(-8))); } catch (_) { /* Storage is optional. */ }
}

function addTrace(method, path, status) {
  trace.push({ method, path, status: String(status) });
  trace = trace.slice(-8);
  saveTrace();
  renderTrace();
}

function renderTrace() {
  const list = $("#trace-list");
  list.replaceChildren();
  if (!trace.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "No requests from this page yet.";
    list.append(empty);
    return;
  }
  for (const entry of trace.slice().reverse()) {
    const row = document.createElement("div");
    row.className = "trace-row";
    const method = document.createElement("span");
    method.className = "method " + (entry.method === "POST" ? "post" : "get");
    method.textContent = entry.method;
    const path = document.createElement("code");
    path.textContent = entry.path;
    const status = document.createElement("span");
    status.className = "http-status";
    status.textContent = entry.status;
    row.append(method, path, status);
    list.append(row);
  }
}

async function api(path, options = {}) {
  const response = await fetch(path, { cache: "no-store", ...options });
  if (!response.ok) {
    let detail = "Request failed (HTTP " + response.status + ").";
    try { detail = (await response.json()).detail || detail; } catch (_) { /* Keep the status. */ }
    throw new Error(typeof detail === "string" ? detail : "Request failed (HTTP " + response.status + ").");
  }
  return [response, await response.json()];
}

function showResult(title, text) {
  $("#result-title").textContent = title;
  $("#result-text").textContent = text;
  $("#result-card").hidden = false;
}

function chooseTab(name) {
  activeTab = name;
  for (const kind of ["mock", "github"]) {
    const selected = kind === name;
    $("#tab-" + kind).classList.toggle("selected", selected);
    $("#tab-" + kind).setAttribute("aria-selected", String(selected));
    $("#" + kind + "-panel").hidden = !selected;
  }
}

async function loadProviders() {
  try {
    const [, providers] = await api("/providers");
    providerNames = new Set(providers.map((row) => row.name));
    $("#github-note").textContent = providerNames.has("github")
      ? "GitHub is registered. You may be asked to approve access in your browser."
      : "First run make register-github in Ubuntu, then refresh this page.";
  } catch (_) {
    $("#github-note").textContent = "Provider list unavailable. Check that the local service is running.";
  }
}

async function checkReady() {
  try {
    const response = await fetch("/readyz", { cache: "no-store" });
    $("#service-status").classList.toggle("offline", !response.ok);
    $("#service-status span:last-child").textContent = response.ok ? "Service ready" : "Service starting";
  } catch (_) {
    $("#service-status").classList.add("offline");
    $("#service-status span:last-child").textContent = "Service offline";
  }
}

function renderActivity(events) {
  const list = $("#activity-list");
  list.replaceChildren();
  if (!events.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "Waiting for the first event. Try the sample flow above.";
    list.append(empty);
    return;
  }
  for (const event of events.slice(0, 8)) {
    const row = document.createElement("div");
    row.className = "activity-row";
    const dot = document.createElement("span");
    dot.className = "event-dot " + (event.kind === "request_failed" || event.kind === "consent_denied" ? "bad" : "");
    const body = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = eventNames[event.kind] || "Event";
    const subtitle = document.createElement("p");
    subtitle.textContent = event.provider + (event.user ? " · " + event.user : "") + (event.request_ref ? " · request " + event.request_ref : "");
    const time = document.createElement("time");
    time.dateTime = event.at;
    time.textContent = new Date(event.at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    body.append(title, subtitle);
    row.append(dot, body, time);
    list.append(row);
  }
}

async function refreshActivity() {
  try { const [, events] = await api("/activity"); renderActivity(events); }
  catch (_) { /* Polling resumes automatically when the service returns. */ }
}

function beginFlow() {
  trace = [];
  saveTrace();
  renderTrace();
  $("#result-card").hidden = true;
  setStep(0, "Preparing the provider…");
  setBusy(true);
}

async function startMock() {
  if (busy) return;
  let user;
  try { user = safeUser($("#mock-user").value); }
  catch (error) { setMessage(error.message, true); return; }
  beginFlow();
  setMessage("Registering the sample provider with OpenBao…");
  try {
    const bytes = new Uint8Array(24);
    crypto.getRandomValues(bytes);
    const secret = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
    const body = {
      name: "demo", provider: "custom", client_id: "sample-client", client_secret: secret,
      scopes: ["openid"], provider_options: {
        auth_code_url: "http://localhost:8090/ci/authorize",
        token_url: "http://mock-oauth2-server.oidc.svc.cluster.local:8080/ci/token",
      },
    };
    const [registered] = await api("/providers", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    addTrace("POST", "/providers", registered.status);
    setStep(1, "OpenBao has the sample provider settings.");
    setMessage("Creating a one-time consent link…");
    const path = "/providers/demo/users/" + encodeURIComponent(user) + "/connect";
    const [connected, data] = await api(path, { method: "POST" });
    addTrace("POST", "/providers/demo/users/{user}/connect", connected.status);
    setStep(2, "The local identity provider is ready for the callback.");
    const authUrl = new URL(data.auth_url);
    if (authUrl.protocol !== "http:" || authUrl.hostname !== "localhost" || authUrl.port !== "8090") {
      throw new Error("The sample consent URL was unexpected. Check that the local mock service is running.");
    }
    $("#consent-user").textContent = user;
    $("#consent-username").value = user;
    $("#consent-form").action = authUrl.href;
    $("#consent-overlay").hidden = false;
    $("#cancel-consent").focus();
    setMessage("Continue the sample consent flow in the dialog.");
  } catch (error) {
    setMessage(error.message, true);
    setBusy(false);
  }
}

async function startGithub() {
  if (busy) return;
  let user;
  try { user = safeUser($("#github-user").value); }
  catch (error) { setMessage(error.message, true); return; }
  if (!providerNames.has("github")) {
    setMessage("Run make register-github in Ubuntu, then refresh this page.", true);
    return;
  }
  beginFlow();
  setStep(1, "Your GitHub provider is registered in OpenBao.");
  try {
    const path = "/providers/github/users/" + encodeURIComponent(user) + "/connect";
    const [response, data] = await api(path, { method: "POST" });
    addTrace("POST", "/providers/github/users/{user}/connect", response.status);
    setStep(2, "Opening GitHub in your browser…");
    const authUrl = new URL(data.auth_url);
    if (authUrl.protocol !== "https:" || authUrl.hostname !== "github.com") {
      throw new Error("The GitHub consent URL was unexpected.");
    }
    window.location.assign(authUrl.href);
  } catch (error) {
    setMessage(error.message, true);
    setBusy(false);
  }
}

async function finishConnection(provider, user) {
  chooseTab(provider === "github" ? "github" : "mock");
  $("#" + (provider === "github" ? "github" : "mock") + "-user").value = user;
  setStep(3, "The provider returned through the callback. Requesting a token…");
  setMessage("Identity connected. The service is now fetching a token from OpenBao.");
  showResult("Identity connected", provider + " · " + user + " returned to the callback.");
  addTrace("GET", "/callback", 303);
  try {
    const path = "/" + provider + "/" + encodeURIComponent(user);
    const [accepted, job] = await api(path);
    addTrace("GET", "/" + provider + "/{user}", accepted.status);
    setStep(4, "Request accepted. A background worker is asking OpenBao for the token.");
    for (let attempt = 0; attempt < 40; attempt++) {
      const [response, result] = await api("/requests/" + encodeURIComponent(job.request_id) + "/status");
      if (attempt === 0 || result.status === "succeeded" || result.status === "failed") {
        addTrace("GET", "/requests/{id}/status", response.status + " · " + result.status);
      }
      if (result.status === "succeeded") {
        setStep(6, "Connection complete. OpenBao supplied the token to the worker.");
        showResult("Connection and token ready", provider + " · " + user + " is connected. Request " + job.request_id.slice(0, 8) + " succeeded. The token stays hidden on this page.");
        setMessage("The worker retrieved the token. This page reads only the request status.");
        refreshActivity();
        return;
      }
      if (result.status === "failed") throw new Error(result.error?.message || "Token retrieval failed.");
      await new Promise((resolve) => setTimeout(resolve, 500));
    }
    throw new Error("The request is still running. Check the live activity feed or try again.");
  } catch (error) {
    setMessage(error.message, true);
    showResult("Connection completed", "Token retrieval needs attention. Check the message above.");
  }
}

function init() {
  try {
    const saved = JSON.parse(sessionStorage.getItem(traceKey) || "[]");
    if (Array.isArray(saved)) trace = saved.filter((row) => row && typeof row.method === "string" && typeof row.path === "string" && typeof row.status === "string").slice(-8);
  } catch (_) { trace = []; }
  renderTrace();
  $("#tab-mock").addEventListener("click", () => chooseTab("mock"));
  $("#tab-github").addEventListener("click", () => chooseTab("github"));
  $("#start-mock").addEventListener("click", startMock);
  $("#start-github").addEventListener("click", startGithub);
  $("#refresh-activity").addEventListener("click", refreshActivity);
  $("#cancel-consent").addEventListener("click", () => {
    $("#consent-overlay").hidden = true;
    setMessage("Sample consent cancelled. Start again whenever you are ready.");
    setBusy(false);
  });
  checkReady();
  loadProviders();
  refreshActivity();
  setInterval(() => { checkReady(); refreshActivity(); }, 3000);
  const query = new URLSearchParams(window.location.search);
  const provider = query.get("connected");
  const user = query.get("user");
  if (provider || user) {
    history.replaceState(null, "", "/");
    if ((provider === "demo" || provider === "github") && user && userPattern.test(user)) {
      finishConnection(provider, user);
    } else {
      setMessage("The callback returned an unexpected identity.", true);
    }
  }
}

document.addEventListener("DOMContentLoaded", init);
