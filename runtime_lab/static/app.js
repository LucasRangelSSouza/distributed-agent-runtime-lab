const form = document.querySelector("#message-form");
const input = document.querySelector("#message");
const requestInput = document.querySelector("#request-id");
const messages = document.querySelector("#messages");
const connection = document.querySelector("#connection");

const trace = (name, value) => { document.querySelector(`#trace-${name}`).textContent = value; };
const escapeHtml = (value) => value.replace(/[&<>'"]/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;","\"":"&quot;"}[char]));

fetch("/healthz").then(response => response.ok ? response.json() : Promise.reject()).then(() => {
  connection.textContent = "Runtime connected"; connection.classList.add("ready");
}).catch(() => { connection.textContent = "Runtime unavailable"; connection.classList.add("offline"); });

form.addEventListener("submit", async event => {
  event.preventDefault();
  const message = input.value.trim();
  if (!message) return;
  const button = form.querySelector("button");
  button.disabled = true; button.textContent = "Routing request";
  messages.insertAdjacentHTML("beforeend", `<article class="message user">${escapeHtml(message)}</article>`);
  try {
    const response = await fetch("/api/messages", {method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({message, request_id: requestInput.value.trim() || undefined})});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "request failed");
    requestInput.value = data.request_id;
    messages.insertAdjacentHTML("beforeend", `<article class="message worker"><span>Assigned to ${escapeHtml(data.worker_id || "worker")}</span>${escapeHtml(data.response || "No response")}</article>`);
    trace("status", data.status); trace("worker", data.worker_id || "—"); trace("attempts", String(data.attempts)); trace("cache", data.cache_hit ? "Completed response returned" : "New execution");
    input.value = "";
  } catch (error) { messages.insertAdjacentHTML("beforeend", `<article class="message error">${escapeHtml(error.message)}</article>`); }
  finally { button.disabled = false; button.textContent = "Send to runtime"; messages.scrollTop = messages.scrollHeight; }
});
