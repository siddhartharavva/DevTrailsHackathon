import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getWorkerClaims } from "../services/api";

const STATUS_STYLE = {
  success:       { color: "var(--green)",  label: "Paid" },
  pending:       { color: "var(--amber)",  label: "Processing" },
  manual_review: { color: "var(--amber)",  label: "Under Review" },
  rejected:      { color: "var(--red)",    label: "Rejected" },
  failed:        { color: "var(--red)",    label: "Failed" },
};

export default function Claims() {
  const workerId = localStorage.getItem("worker_id");
  const [claims, setClaims] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;

    if (!workerId) {
      setLoading(false);
      setClaims([]);
      return () => {
        active = false;
      };
    }

    getWorkerClaims(workerId)
      .then((data) => {
        if (!active) return;
        setClaims(Array.isArray(data) ? data : []);
      })
      .catch(() => {
        if (!active) return;
        setClaims([]);
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [workerId]);

  if (loading) return (
    <div className="screen">
      <div className="loading-center">
        <div className="spinner" />
      </div>
    </div>
  );

  return (
    <div className="screen" style={{ paddingBottom: 90 }}>
      <div className="logo-row">
        <div className="logo-icon">📋</div>
        <span className="logo-text">My Claims</span>
      </div>

      {claims.length === 0 ? (
        <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center",
          justifyContent: "center", color: "var(--muted)", textAlign: "center", gap: 12 }}>
          <div style={{ fontSize: 48 }}>🛡</div>
          <div style={{ fontSize: 16, fontWeight: 600, color: "white" }}>No claims yet</div>
          <div style={{ fontSize: 13 }}>
            When a disruption event hits your zone,<br />
            your payout will appear here automatically.
          </div>
        </div>
      ) : (
        claims.map((c) => {
          const st = STATUS_STYLE[c.status] || STATUS_STYLE.pending;
          return (
            <div key={c.claim_id} className="card">
              <div className="row" style={{ marginBottom: 10 }}>
                <div style={{ fontSize: 22, fontWeight: 700,
                  color: c.status === "success" ? "var(--green)" : "white" }}>
                  {c.status === "success" ? "+" : ""}₹{c.amount?.toFixed(0)}
                </div>
                <span style={{ fontSize: 11, fontWeight: 700, color: st.color,
                  background: `${st.color}22`, padding: "3px 10px", borderRadius: 20,
                  border: `1px solid ${st.color}44` }}>
                  {st.label}
                </span>
              </div>

              <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 8 }}>
                Event: {c.event_id} ·{" "}
                {new Date(c.created_at).toLocaleString("en-IN",
                  {day:"numeric",month:"short",hour:"2-digit",minute:"2-digit"})}
              </div>

              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                {c.overlap_hours > 0 && (
                  <span style={{ fontSize: 10, color: "var(--muted)",
                    background: "var(--surface)", padding: "2px 8px", borderRadius: 6 }}>
                    {c.overlap_hours?.toFixed(1)}h disruption
                  </span>
                )}
                {c.gps_confidence > 0 && (
                  <span style={{ fontSize: 10, color: "var(--muted)",
                    background: "var(--surface)", padding: "2px 8px", borderRadius: 6 }}>
                    GPS {(c.gps_confidence * 100).toFixed(0)}% confidence
                  </span>
                )}
                {c.utr && (
                  <span style={{ fontSize: 10, color: "var(--muted)",
                    background: "var(--surface)", padding: "2px 8px",
                    borderRadius: 6, fontFamily: "var(--mono)" }}>
                    {c.utr}
                  </span>
                )}
              </div>

              {c.status === "manual_review" && (
                <div style={{ marginTop: 10, padding: "8px 10px",
                  background: "rgba(255,184,48,0.08)",
                  border: "1px solid rgba(255,184,48,0.2)",
                  borderRadius: 8, fontSize: 12, color: "var(--amber)" }}>
                  Your claim is being reviewed. We'll resolve this within 24 hours.
                </div>
              )}

              {c.status === "success" && (
                <div style={{ marginTop: 10, padding: "8px 10px",
                  background: "rgba(46,213,115,0.06)",
                  border: "1px solid rgba(46,213,115,0.15)",
                  borderRadius: 8, fontSize: 12, color: "var(--green)" }}>
                  Credited to your UPI account. No claim filed — fully automatic.
                </div>
              )}
            </div>
          );
        })
      )}

      {/* Bottom nav */}
      <nav className="bottom-nav">
        {[
          { to: "/dashboard", label: "Home",   icon: "🏠" },
          { to: "/claims",    label: "Claims", icon: "📋", active: true },
          { to: "/admin",     label: "Admin",  icon: "⚙️" },
        ].map((n) => (
          <Link key={n.to} to={n.to} className={`nav-item ${n.active ? "active" : ""}`}>
            <span style={{ fontSize: 20 }}>{n.icon}</span>
            {n.label}
          </Link>
        ))}
      </nav>
    </div>
  );
}
