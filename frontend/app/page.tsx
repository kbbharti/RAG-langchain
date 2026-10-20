"use client";

import { FormEvent, useRef, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
type Citation = { filename: string; page: number };
type Message = { role: "user" | "assistant"; content: string; citations?: Citation[] };

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState("");
  const [sessionId, setSessionId] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const inputFile = useRef<HTMLInputElement>(null);

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const file = inputFile.current?.files?.[0];
    if (!file) return;
    setBusy(true);
    setNotice(`Indexing ${file.name}…`);
    const body = new FormData();
    body.append("file", file);
    try {
      const response = await fetch(`${API}/ingest`, { method: "POST", body });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail ?? "PDF ingestion failed.");
      setNotice(`Indexed ${result.chunks_indexed} chunks from ${result.filename}.`);
      if (inputFile.current) inputFile.current.value = "";
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "PDF ingestion failed.");
    } finally {
      setBusy(false);
    }
  }

  async function ask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = question.trim();
    if (!text || busy) return;
    setQuestion("");
    setMessages((current) => [...current, { role: "user", content: text }]);
    setBusy(true);
    try {
      const response = await fetch(`${API}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: text, session_id: sessionId }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail ?? "The request failed.");
      setSessionId(result.session_id);
      setMessages((current) => [
        ...current,
        { role: "assistant", content: result.answer, citations: result.citations },
      ]);
    } catch (error) {
      setMessages((current) => [
        ...current,
        { role: "assistant", content: error instanceof Error ? error.message : "Request failed." },
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="shell">
      <header className="topbar"><span className="brand-mark">R</span><span>DOCUMENT INTELLIGENCE</span><span className="status"><i /> Databricks RAG</span></header>
      <section className="hero">
        <p className="eyebrow">YOUR KNOWLEDGE, IN CONTEXT</p>
        <h1>Ask your <em>documents.</em></h1>
        <p className="subhead">Answers grounded in your PDFs, with page-level citations you can verify.</p>
        <form className="upload" onSubmit={upload}>
          <label className="file-label">＋ <span>Choose a PDF</span><input ref={inputFile} type="file" accept="application/pdf,.pdf" required /></label>
          <button className="upload-button" disabled={busy}>Index PDF <span>↗</span></button>
        </form>
        {notice && <p className="notice" role="status">{notice}</p>}
      </section>
      <section className="chat-card" aria-label="Chat with documents">
        <div className="chat-heading"><div><span className="live-dot" /> DOCUMENT CHAT</div><span>{sessionId ? `SESSION ${sessionId.slice(0, 8)}` : "NEW SESSION"}</span></div>
        <div className="conversation" aria-live="polite">
          {messages.length === 0 ? <div className="empty"><span className="spark">✳</span><p>Start with a question</p><span>Once you’ve indexed a PDF, ask about anything inside it.</span></div> : messages.map((message, index) => (
            <article className={`message ${message.role}`} key={`${index}-${message.role}`}>
              <span className="role-label">{message.role === "user" ? "YOU" : "ANSWER"}</span>
              <p>{message.content}</p>
              {!!message.citations?.length && <div className="citations">{message.citations.map((citation) => <span key={`${citation.filename}-${citation.page}`}>↳ {citation.filename} · p. {citation.page}</span>)}</div>}
            </article>
          ))}
          {busy && <p className="thinking">Finding the relevant passages<span>…</span></p>}
        </div>
        <form className="question-form" onSubmit={ask}>
          <input aria-label="Your question" placeholder="Ask a question about your PDFs…" value={question} onChange={(event) => setQuestion(event.target.value)} />
          <button aria-label="Send question" disabled={busy || !question.trim()}>↑</button>
        </form>
      </section>
      <footer>GROUNDED IN YOUR SOURCES <span>·</span> POWERED BY LANGCHAIN + DATABRICKS</footer>
    </main>
  );
}
