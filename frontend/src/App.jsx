import { useEffect, useState } from "react";

const demoEmails = ["alex@example.com", "taylor@example.com", "jordan@example.com"];

function App() {
  const [sessions, setSessions] = useState([]);
  const [selectedSessionId, setSelectedSessionId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [message, setMessage] = useState("");
  const [selectedEmail, setSelectedEmail] = useState(demoEmails[0]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    refreshSessions();
  }, []);

  useEffect(() => {
    if (selectedSessionId) {
      loadSession(selectedSessionId);
    }
  }, [selectedSessionId]);

  async function refreshSessions() {
    const response = await fetch("/api/chat/sessions");
    const data = await response.json();
    setSessions(data);
    if (!selectedSessionId && data.length > 0) {
      setSelectedSessionId(data[0].id);
    }
  }

  async function createSession() {
    setLoading(true);
    setError("");
    try {
      const response = await fetch("/api/chat/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_email: selectedEmail }),
      });
      if (!response.ok) {
        throw new Error("Failed to create session");
      }
      const data = await response.json();
      await refreshSessions();
      setSelectedSessionId(data.session.id);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function loadSession(sessionId) {
    setLoading(true);
    try {
      const response = await fetch(`/api/chat/sessions/${sessionId}`);
      const data = await response.json();
      setDetail(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function sendMessage(event) {
    event.preventDefault();
    if (!message.trim() || !selectedSessionId) {
      return;
    }
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`/api/chat/sessions/${selectedSessionId}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });
      if (!response.ok) {
        throw new Error("Failed to send message");
      }
      const data = await response.json();
      setDetail(data);
      setMessage("");
      await refreshSessions();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function saveFeedback(rating) {
    if (!selectedSessionId) return;
    setLoading(true);
    try {
      const response = await fetch(`/api/chat/sessions/${selectedSessionId}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rating }),
      });
      const data = await response.json();
      setDetail(data);
      await refreshSessions();
    } finally {
      setLoading(false);
    }
  }

  async function handoffTicket() {
    if (!detail?.ticket?.id) return;
    setLoading(true);
    try {
      await fetch(`/api/tickets/${detail.ticket.id}/handoff`, { method: "POST" });
      await loadSession(selectedSessionId);
      await refreshSessions();
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app-shell">
      <aside className="panel panel-left">
        <div className="panel-header">
          <p className="eyebrow">Support Desk</p>
          <h1>Customer Support Agent</h1>
        </div>
        <div className="session-creator">
          <label>
            Demo user
            <select value={selectedEmail} onChange={(event) => setSelectedEmail(event.target.value)}>
              {demoEmails.map((email) => (
                <option key={email} value={email}>
                  {email}
                </option>
              ))}
            </select>
          </label>
          <button onClick={createSession} disabled={loading}>
            Open Session
          </button>
        </div>
        <div className="session-list">
          {sessions.map((session) => (
            <button
              key={session.id}
              className={`session-card ${selectedSessionId === session.id ? "selected" : ""}`}
              onClick={() => setSelectedSessionId(session.id)}
            >
              <div className="session-card-top">
                <strong>{session.user_name}</strong>
                <span className={`badge badge-${session.status}`}>{session.status}</span>
              </div>
              <p>{session.latest_message || "No messages yet"}</p>
              <small>{session.user_email}</small>
            </button>
          ))}
        </div>
      </aside>

      <main className="panel panel-center">
        <div className="panel-header">
          <p className="eyebrow">Conversation</p>
          <h2>{detail?.session?.user_name || "Select a session"}</h2>
        </div>
        <div className="messages">
          {detail?.messages?.map((item, index) => (
            <div key={`${item.created_at}-${index}`} className={`message message-${item.role}`}>
              <span>{item.role === "user" ? "User" : "Agent"}</span>
              <p>{item.content}</p>
            </div>
          ))}
        </div>
        <form className="composer" onSubmit={sendMessage}>
          <textarea
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            placeholder="Ask about billing, login, invoices, refunds, or technical issues..."
            rows={4}
          />
          <button type="submit" disabled={loading || !selectedSessionId}>
            Send
          </button>
        </form>
        {error && <p className="error-text">{error}</p>}
      </main>

      <aside className="panel panel-right">
        <div className="panel-header">
          <p className="eyebrow">Context</p>
          <h2>Agent Insights</h2>
        </div>
        <section className="info-block">
          <h3>User Profile</h3>
          {detail?.context?.user ? (
            <>
              <p>{detail.context.user.name}</p>
              <p>{detail.context.user.company}</p>
              <p>{detail.context.user.plan} plan</p>
            </>
          ) : (
            <p>No user selected.</p>
          )}
        </section>
        <section className="info-block">
          <h3>Subscription</h3>
          {detail?.context?.subscription ? (
            <>
              <p>{detail.context.subscription.plan_name}</p>
              <p>Status: {detail.context.subscription.status}</p>
              <p>Renewal: {new Date(detail.context.subscription.renewal_date).toLocaleString()}</p>
            </>
          ) : (
            <p>No subscription data.</p>
          )}
        </section>
        <section className="info-block">
          <h3>Latest Order</h3>
          {detail?.context?.orders?.[0] ? (
            <>
              <p>{detail.context.orders[0].order_number}</p>
              <p>Status: {detail.context.orders[0].status}</p>
              <p>
                {detail.context.orders[0].amount} {detail.context.orders[0].currency}
              </p>
            </>
          ) : (
            <p>No order data.</p>
          )}
        </section>
        <section className="info-block">
          <h3>Decision</h3>
          {detail?.decision ? (
            <>
              <p>Intent: {detail.decision.intent}</p>
              <p>Confidence: {(detail.decision.confidence * 100).toFixed(0)}%</p>
              <p>FAQ matched: {detail.decision.faq_match.matched ? "Yes" : "No"}</p>
              <p>Tools: {detail.decision.tool_calls.join(", ") || "None"}</p>
              <p>Risk: {detail.decision.risk_level}</p>
            </>
          ) : (
            <p>No decision yet.</p>
          )}
        </section>
        <section className="info-block">
          <h3>Ticket</h3>
          {detail?.ticket ? (
            <>
              <p>#{detail.ticket.id}</p>
              <p>{detail.ticket.category}</p>
              <p>Status: {detail.ticket.status}</p>
              <button onClick={handoffTicket} disabled={loading || detail.ticket.status === "handed_off"}>
                Human Takeover
              </button>
            </>
          ) : (
            <p>No open ticket.</p>
          )}
        </section>
        <section className="info-block">
          <h3>Satisfaction</h3>
          <div className="feedback-row">
            <button onClick={() => saveFeedback("up")} disabled={loading || !selectedSessionId}>
              Helpful
            </button>
            <button onClick={() => saveFeedback("down")} disabled={loading || !selectedSessionId}>
              Needs Work
            </button>
          </div>
        </section>
      </aside>
    </div>
  );
}

export default App;
