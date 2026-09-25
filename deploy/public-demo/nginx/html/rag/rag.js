"use strict";
const form = document.getElementById("ask");
const result = document.getElementById("result");
function line(text, className) {
  const p = document.createElement("p");
  p.textContent = text;
  if (className) p.className = className;
  result.appendChild(p);
}
form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = document.getElementById("question").value.trim();
  if (!question) return;
  result.replaceChildren();
  line("Asking the gateway...");
  try {
    const response = await fetch("/v1/answer", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question }) });
    const payload = await response.json();
    result.replaceChildren();
    if (!response.ok) { line(payload.error || "The gateway rejected the request."); return; }
    line(`Status: ${payload.status}`);
    line(payload.answer);
    for (const c of payload.citations || []) line(`Cited: ${c.document_id} (${c.dataset}, ${c.dataset_version})`, "citation");
  } catch (error) {
    result.replaceChildren();
    line("The gateway is unavailable.");
  }
});
