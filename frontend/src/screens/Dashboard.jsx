import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { getWorker, getWorkerSummary, getEvents } from "../services/api";

export default function Dashboard() {
  const navigate   = useNavigate();
  const workerId   = localStorage.getItem("worker_id");
  const workerName = localStorage.getItem("worker_name") || "Partner";

  const [worker,  setWorker]  = useState(null);
  const [summary, setSummary] = useState(null);
  const [events,  setEvents]  = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      getWorker(workerId),
      getWorkerSummary(workerId),
      getEvents(),
    ]).then(([w, s, e]) => {
      setWorker(w);
      setSummary(s);
      setEvents(e.slice(0, 5));
    }).finally(() => setLoading(false));
  }, [workerId]);

  if (loading) return (
    <div className="screen">
      <div className="loading-center">
        <div className="spinner" />
        <span>Loading your dashboard...</span>
      </div>
    </div>
  );

  const plan = worker?.policy;
  const capUsedPct = summary
    ? Math.min((summary.weekly_cap_used / (summary.weekly_cap_used + summary.weekly_cap_remaining)) * 100, 100)
    : 0;

  const greetHour = new Date().getHours();
  const greet = greetHour < 12 ? "Good morning" : greetHour < 17 ? "Good afternoon" : "Good evening";

  return (
    <div className="screen" style={{ paddingBottom: 90 }}>
      {/* Header */}
      <div className="row" style={{ marginBottom: 24 }}>
        <div>
          <div style={{ fontSize: 13, color: "var(--muted)" }}>{greet}</div>
          <div style={{ fontSize: 20, fontWeight: 700 }}>{workerName} 👋</div>
        </div>
        <span className={`badge ${plan?.active ? "badge-green" : "badge-red"}`}>
          {plan?.active ? "ACTIVE" : "INACTIVE"}
        </span>
      </div>

      {/* Coverage card */}
      <div style={{
        background: "linear-gradient(135deg, rgba(26,107,255,0.25) 0%, rgba(0,201,167,0.1) 100%)",
        border: "1px solid rgba(26,107,255,0.35)",
        borderRadius: 20, padding: 20, marginBottom: 16, position: "relative", overflow: "hidden",
      }}>
        <div style={{ fontSize: 40, position: "absolute", right: 10, top: 10, opacity: 0.07 }}>🛡</div>
        <div className="label-sm" style={{ color: "#7EB3FF" }}>This week's protection</div>
        <div style={{ fontSize: 36, fontWeight: 700, letterSpacing: -1 }}>
          ₹{plan?.weekly_cap || 0}
        </div>
        <div style={{ fontSize: 12, color: "rgba(255,255,255,0.5)", marginTop: 2 }}>
          {worker?.plan?.charAt(0).toUpperCase() + worker?.plan?.slice(1)} Plan ·
          ₹{plan?.weekly_premium} paid ·
          Valid until {plan?.valid_until ? new Date(plan.valid_until).toLocaleDateString("en-IN", {day:"numeric",month:"short"}) : "—"}
        </div>
        {/* Cap progress bar */}
        <div style={{ marginTop: 14, height: 4, background: "rgba(255,255,255,0.1)", borderRadius: 2 }}>
          <div style={{
            height: "100%", borderRadius: 2, background: "var(--teal)",
            width: `${100 - capUsedPct}%`, transition: "width 0.5s ease"
          }} />
        </div>
        <div style={{ fontSize: 10, color: "rgba(255,255,255,0.4)", marginTop: 4 }}>
          ₹{summary?.weekly_cap_remaining || plan?.weekly_cap} remaining
        </div>
      </div>

      {/* Stats row */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 16 }}>
        <div className="card">
          <div style={{ fontSize: 24, fontWeight: 700, color: "var(--green)" }}>
            ₹{summary?.total_payout_this_week || 0}
          </div>
          <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 2 }}>Received this week</div>
        </div>
        <div className="card">
          <div style={{ fontSize: 24, fontWeight: 700, color: "var(--amber)" }}>
            ₹{summary?.estimated_loss_without_insurance || 0}
          </div>
          <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 2 }}>Loss without insurance</div>
        </div>
      </div>

      {/* Events section */}
      <div className="label-sm" style={{ marginBottom: 10 }}>Recent disruption events</div>

      {events.length === 0 ? (
        <div className="card" style={{ textAlign: "center", color: "var(--muted)", fontSize: 13, padding: 24 }}>
          No disruption events in your zone yet.<br />
          <span style={{ fontSize: 11, marginTop: 4, display: "block" }}>
            You're covered if one occurs.
          </span>
        </div>
      ) : (
        events.map((evt) => (
          <div key={evt.event_id} className="card" style={{ padding: "12px 14px" }}>
            <div className="row">
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <div style={{
                  width: 8, height: 8, borderRadius: "50%",
                  background: evt.severity === "red" ? "var(--red)" :
                              evt.severity === "orange" ? "var(--amber)" : "var(--blue)"
                }} />
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600 }}>{evt.trigger_type.replace(/_/g," ")}</div>
                  <div style={{ fontSize: 11, color: "var(--muted)" }}>
                    {evt.zone_id} · {new Date(evt.start_time).toLocaleString("en-IN",
                      {day:"numeric",month:"short",hour:"2-digit",minute:"2-digit"})}
                  </div>
                </div>
              </div>
              <span className={`badge badge-${evt.severity === "red" ? "red" : evt.severity === "orange" ? "amber" : "blue"}`}>
                {evt.severity.toUpperCase()}
              </span>
            </div>
          </div>
        ))
      )}

      <Link to="/claims" className="btn btn-secondary" style={{
        display: "block", textAlign: "center", marginTop: 8,
        textDecoration: "none", padding: "13px 0"
      }}>
        View all claims →
      </Link>

      <BottomNav active="home" />
    </div>
  );
}

function BottomNav({ active }) {
  return (
    <nav className="bottom-nav">
      {[
        { to: "/dashboard", label: "Home",   icon: "🏠" },
        { to: "/claims",    label: "Claims", icon: "📋" },
        { to: "/admin",     label: "Admin",  icon: "⚙️" },
      ].map((n) => (
        <Link key={n.to} to={n.to} className={`nav-item ${active === n.label.toLowerCase() ? "active" : ""}`}>
          <span style={{ fontSize: 20 }}>{n.icon}</span>
          {n.label}
        </Link>
      ))}
    </nav>
  );
}
