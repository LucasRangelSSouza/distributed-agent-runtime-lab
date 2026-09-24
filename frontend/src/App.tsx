import { FormEvent, useEffect, useMemo, useState } from "react";
import { Activity, Bot, CheckCircle2, Copy, Send, ShieldCheck } from "lucide-react";
import { Button } from "./components/ui/button";

type Result = { request_id: string; conversation_id?: string; response: string; worker_id: string; attempts: number; cache_hit: boolean; status: string };
type Message = { role: "user" | "worker"; content: string; detail?: string };
const newId = () => crypto.randomUUID();

export default function App() {
  const [conversationId, setConversationId] = useState<string>(newId());
  const [requestId, setRequestId] = useState("");
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<Message[]>([{ role: "worker", content: "The deterministic runtime is ready. Every submission keeps a visible request ID." }]);
  const [result, setResult] = useState<Result | null>(null);
  const [connected, setConnected] = useState(false);
  const [sending, setSending] = useState(false);
  const activeRequest = useMemo(() => requestId || "Generated on send", [requestId]);

  useEffect(() => { fetch("/healthz").then((r) => setConnected(r.ok)).catch(() => setConnected(false)); }, []);
  async function submit(event: FormEvent) {
    event.preventDefault(); const message = draft.trim(); if (!message || sending) return;
    const id = requestId || newId(); setRequestId(id); setSending(true); setMessages((items) => [...items, { role: "user", content: message }]);
    try {
      const response = await fetch("/api/messages", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message, request_id: id, conversation_id: conversationId }) });
      const payload = await response.json() as Result; if (!response.ok) throw new Error("The runtime rejected this request.");
      setResult(payload); setConversationId(payload.conversation_id || conversationId); setMessages((items) => [...items, { role: "worker", content: payload.response, detail: `${payload.worker_id} · attempt ${payload.attempts}${payload.cache_hit ? " · replay" : ""}` }]); setDraft("");
    } catch (error) { setMessages((items) => [...items, { role: "worker", content: error instanceof Error ? error.message : "The request failed." }]); } finally { setSending(false); }
  }
  return <main className="mx-auto grid min-h-screen max-w-7xl gap-6 p-6 lg:grid-cols-[360px_minmax(0,1fr)] lg:items-center lg:p-12">
    <aside className="space-y-8 rounded-3xl border border-slate-800 bg-slate-900/40 p-8 shadow-2xl shadow-black/20"><div><p className="mb-3 text-xs font-bold tracking-[0.2em] text-cyan-300">LOCAL RUNTIME LAB</p><h1 className="text-4xl font-bold tracking-tight">Distributed behavior, visible at the edge.</h1><p className="mt-5 text-base leading-7 text-slate-400">This local surface exposes request replay, worker assignment, and the active conversation identity.</p></div><div className="space-y-3 text-sm"><p className="flex items-center gap-3"><Activity size={16} className={connected ? "text-emerald-400" : "text-rose-400"} />{connected ? "Runtime connected" : "Runtime unavailable"}</p><p className="flex items-center gap-3"><ShieldCheck size={16} className="text-cyan-300" />Deterministic stub mode</p></div><div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4"><p className="text-xs font-semibold text-slate-500">CONVERSATION ID</p><p className="mt-2 break-all font-mono text-xs text-slate-300">{conversationId}</p><Button variant="outline" className="mt-4 w-full" onClick={() => { setConversationId(newId()); setRequestId(""); setResult(null); setMessages([]); }}><Copy size={15} className="mr-2" />New conversation</Button></div></aside>
    <section className="overflow-hidden rounded-3xl border border-slate-800 bg-slate-900 shadow-2xl shadow-black/20"><header className="flex items-start justify-between border-b border-slate-800 p-6"><div><p className="text-xs font-bold tracking-[0.2em] text-cyan-300">REQUEST CONSOLE</p><h2 className="mt-2 text-2xl font-semibold">Conversation</h2></div><div className="rounded-full border border-slate-700 px-3 py-2 text-xs text-slate-400">{result?.status ?? "Awaiting request"}</div></header><div className="min-h-[360px] space-y-4 p-6">{messages.map((message, index) => <article key={index} className={`max-w-[82%] rounded-2xl p-4 ${message.role === "user" ? "ml-auto bg-cyan-100 text-slate-950" : "bg-slate-800 text-slate-100"}`}><div className="flex gap-3"><Bot size={18} className={message.role === "user" ? "hidden" : "mt-0.5 text-cyan-300"} /><div><p className="leading-6">{message.content}</p>{message.detail && <p className="mt-2 text-xs text-slate-400">{message.detail}</p>}</div></div></article>)}</div><form onSubmit={submit} className="border-t border-slate-800 p-6"><label className="text-sm font-medium text-slate-300" htmlFor="message">Message</label><textarea id="message" value={draft} onChange={(e) => setDraft(e.target.value)} maxLength={2000} className="mt-2 min-h-28 w-full rounded-xl border border-slate-700 bg-slate-950 p-4 text-base text-slate-100 outline-none transition focus:border-cyan-300 focus:ring-2 focus:ring-cyan-300/20" placeholder="Ask the deterministic worker to process a short message." /><div className="mt-4 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between"><label className="block flex-1 text-xs font-semibold tracking-wide text-slate-500">REQUEST ID<input value={requestId} onChange={(e) => setRequestId(e.target.value)} className="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950 p-3 font-mono text-xs text-slate-300 outline-none focus:border-cyan-300" placeholder={activeRequest} /></label><Button type="submit" disabled={sending || !draft.trim()}>{sending ? "Routing request" : <><Send size={16} className="mr-2" />Send to runtime</>}</Button></div></form><footer className="grid gap-px border-t border-slate-800 bg-slate-800 text-sm sm:grid-cols-3"><p className="bg-slate-900 p-4"><span className="block text-xs text-slate-500">WORKER</span>{result?.worker_id ?? "—"}</p><p className="bg-slate-900 p-4"><span className="block text-xs text-slate-500">ATTEMPTS</span>{result?.attempts ?? "—"}</p><p className="bg-slate-900 p-4"><span className="block text-xs text-slate-500">REPLAY</span>{result ? (result.cache_hit ? <><CheckCircle2 className="mr-1 inline h-4 text-emerald-400" />Completed response</> : "New execution") : "—"}</p></footer></section>
  </main>;
}
