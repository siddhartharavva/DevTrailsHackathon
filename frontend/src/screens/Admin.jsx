import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getAdminDashboard, getFlaggedClaims, fireTrigger, listWorkers, approveClaim } from "../services/api";

const TRIGGER_OPTIONS = [
  { id: "RAIN_HEAVY",   label: "Heavy Rain",      severity: "orange", raw: 72.4 },
  { id: "RAIN_EXTREME", label: "Extreme Rain",    severity: "red",    raw: 95.0 },
  { id: "HEAT_EXTREME", label: "Extreme Heat",    severity: "red",    raw: 44.5 },
  { id: "AQI_SEVERE",   label: "Severe AQI",      severity: "orange", raw: 320  },
  { id: "CIVIC_CURFEW", label: "Civic Curfew",    severity: "red",    raw: 0    },
  { id: "LOCAL_STRIKE", label: "Local Strike",    severity: "orange", raw: 0    },
];

const ZONES = [
  { id: "BLR_S", label: "Bengaluru South", city: "bengaluru" },
  { id: "BLR_N", label: "Bengaluru North", city: "bengaluru" },
  { id: "MUM_W", label: "Mumbai West",     city: "mumbai"    },
  { id: "DEL_C", label: "Delhi Central",   city: "delhi"     },
];

export default function Admin() {
  const [dashboard, setDashboard] = useState(null);
  const [flagged,   setFlagged]   = useState([]);
  const [workers,   setWorkers]   = useState([]);
  const [tab,       setTab]       = useState("overview");
  const [loading,   setLoading]   = useState(true);
  const [firing,    setFiring]    = useState(false);
  const [fireMsg,   setFireMsg]   = useState("");
  const [trigger,   setTrigger]   = useState({ type: "RAIN_HEAVY", zone: "BLR_S", duration: 4 });

  const load = () => {
    Promise.all([getAdminDashboard(), getFlaggedClaims(), listWorkers()])
      .then(([d, f, w]) => { setDashboard(d); setFlagged(f); setWorkers(w); })
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const handleFireTrigger = async () => {
    setFiring(true);
    setFireMsg("");
    try {
      const opt  = TRIGGER_OPTIONS.find((t) => t.id === trigger.type);
      const zone = ZONES.find((z) => z.id === trigger.zone);
      const res  = await fireTrigger({
        trigger_type: trigger.type,
        severity: opt.severity,
        zone_id: trigger.zone,
        city: zone.city,
        description: `${opt.label} in ${zone.label}`,
        raw_value: opt.raw,
        duration_hours: trigger.duration,
      });
      setFireMsg(`✅ Event fired: ${res.event_id}. Processing payouts for eligible workers.`);
      setTimeout(load, 3000);
    } catch (e) {
      setFireMsg("❌ " + (e.response?.data?.detail || "Failed to fire trigger"));
    } finally {
      setFiring(false);
    }
  };

  const handleApprove = async (claimId) => {
    await approveClaim(claimId);
    setFlagged((f) => f.filter((c) => c.claim_id !== claimId));
  };

  if (loading) return (
    <div className="screen">
      <div className="loading-center"><div className="spinner" /></div>
    </div>
  );

  return (
    <div className="screen" style={{ paddingBottom: 90 }}>
      <div className="logo-row">
        <div className="logo-icon">⚙️</div>
        <span className="logo-text">Admin Panel</span>
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 8, marginBottom: 20, overflowX: "auto" }}>
        {["overview", "trigger", "fraud", "workers"].map((t) => (
          <button key={t} onClick={() => setTab(t)}
            style={{
              padding: "7px 14px", borderRadius: 20, border: "none", cursor: "pointer",
              background: tab === t ? "var(--blue)" : "var(--surface)",
              color: "white", fontFamily: "var(--font)", fontWeight: 600, fontSize: 12,
              whiteSpace: "nowrap",
            }}>
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {/* ── OVERVIEW ── */}
      {tab === "overview" && dashboard && (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, marginBottom: 16 }}>
            {[
              { val: dashboard.total_workers,   label: "Workers",   color: "var(--blue)"  },
              { val: dashboard.week_claims,     label: "Claims",    color: "var(--teal)"  },
              { val: dashboard.flagged_claims,  label: "Flagged",   color: "var(--red)"   },
            ].map((s) => (
              <div key={s.label} className="card" style={{ textAlign: "center", padding: 12 }}>
                <div style={{ fontSize: 22, fontWeight: 700, color: s.color }}>{s.val}</div>
                <div style={{ fontSize: 10, color: "var(--muted)", marginTop: 2 }}>{s.label}</div>
              </div>
            ))}
          </div>

          <div className="card">
            <div className="row">
              <span style={{ fontSize: 13, color: "var(--muted)" }}>Week payouts</span>
              <span style={{ fontSize: 16, fontWeight: 700, color: "var(--green)" }}>
                ₹{dashboard.week_payout_inr?.toFixed(0)}
              </span>
            </div>
            <div className="divider" />
            <div className="row">
              <span style={{ fontSize: 13, color: "var(--muted)" }}>Fraud rate</span>
              <span style={{ fontSize: 14, fontWeight: 700,
                color: dashboard.fraud_rate > 0.05 ? "var(--red)" : "var(--green)" }}>
                {(dashboard.fraud_rate * 100).toFixed(1)}%
              </span>
            </div>
          </div>

          {dashboard.active_events?.length > 0 && (
            <>
              <div className="label-sm" style={{ marginTop: 16, marginBottom: 8 }}>Active Events</div>
              {dashboard.active_events.map((e) => (
                <div key={e.event_id} className="card"
                  style={{ borderColor: e.severity === "red" ? "rgba(255,71,87,0.3)" : "rgba(255,184,48,0.3)" }}>
                  <div className="row">
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 600 }}>{e.trigger_type.replace(/_/g," ")}</div>
                      <div style={{ fontSize: 11, color: "var(--muted)" }}>{e.zone_id} · {e.city}</div>
                    </div>
                    <span className={`badge badge-${e.severity === "red" ? "red" : "amber"}`}>
                      {e.severity.toUpperCase()}
                    </span>
                  </div>
                </div>
              ))}
            </>
          )}
        </>
      )}

      {/* ── TRIGGER PANEL (DEMO) ── */}
      {tab === "trigger" && (
        <>
          <div className="card" style={{ borderColor: "rgba(255,71,87,0.25)" }}>
            <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 4 }}>🔥 Fire Demo Trigger</div>
            <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 14 }}>
              Simulates a disruption event and runs the full payout pipeline for eligible workers.
            </div>

            <div className="field-group">
              <div className="field-label">Event type</div>
              <select value={trigger.type} onChange={(e) => setTrigger((t) => ({ ...t, type: e.target.value }))}>
                {TRIGGER_OPTIONS.map((o) => (
                  <option key={o.id} value={o.id}>{o.label} ({o.severity})</option>
                ))}
              </select>
            </div>

            <div className="field-group">
              <div className="field-label">Affected zone</div>
              <select value={trigger.zone} onChange={(e) => setTrigger((t) => ({ ...t, zone: e.target.value }))}>
                {ZONES.map((z) => (
                  <option key={z.id} value={z.id}>{z.label}</option>
                ))}
              </select>
            </div>

            <div className="field-group">
              <div className="field-label">Duration (hours)</div>
              <input type="number" value={trigger.duration} min={1} max={12}
                onChange={(e) => setTrigger((t) => ({ ...t, duration: parseFloat(e.target.value) }))} />
            </div>

            <button className="btn btn-primary" onClick={handleFireTrigger} disabled={firing}>
              {firing ? "Firing..." : "🚨 Fire Trigger & Process Payouts"}
            </button>

            {fireMsg && (
              <div style={{ marginTop: 12, padding: "10px 12px", borderRadius: 10, fontSize: 12,
                background: fireMsg.startsWith("✅") ? "rgba(46,213,115,0.08)" : "rgba(255,71,87,0.08)",
                border: `1px solid ${fireMsg.startsWith("✅") ? "rgba(46,213,115,0.2)" : "rgba(255,71,87,0.2)"}`,
                color: fireMsg.startsWith("✅") ? "var(--green)" : "var(--red)" }}>
                {fireMsg}
              </div>
            )}
          </div>

          <div className="card" style={{ fontSize: 12, color: "var(--muted)" }}>
            <div style={{ fontWeight: 600, color: "white", marginBottom: 6 }}>What happens when you fire:</div>
            {[
              "Event created in database",
              "All active workers in zone identified",
              "3-gate eligibility check runs for each worker",
              "Anomaly detection scores each claim",
              "Payout amounts calculated via regression formula",
              "Razorpay sandbox UPI transfers initiated",
              "SMS notifications dispatched",
              "Claims written to database",
            ].map((step, i) => (
              <div key={i} style={{ display: "flex", gap: 8, marginBottom: 4 }}>
                <span style={{ color: "var(--blue)", fontWeight: 600 }}>{i + 1}.</span>
                <span>{step}</span>
              </div>
            ))}
          </div>
        </>
      )}

      {/* ── FRAUD MONITOR ── */}
      {tab === "fraud" && (
        <>
          <div className="label-sm" style={{ marginBottom: 10 }}>
            Flagged claims ({flagged.length})
          </div>
          {flagged.length === 0 ? (
            <div className="card" style={{ textAlign: "center", color: "var(--muted)", padding: 24 }}>
              No flagged claims 🎉
            </div>
          ) : (
            flagged.map((c) => (
              <div key={c.claim_id} className="card"
                style={{ borderColor: "rgba(255,71,87,0.2)" }}>
                <div className="row" style={{ marginBottom: 8 }}>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600 }}>{c.worker_id}</div>
                    <div style={{ fontSize: 11, color: "var(--muted)" }}>
                      {c.worker_city} · ₹{c.amount?.toFixed(0)} · {c.status}
                    </div>
                  </div>
                  <div style={{ fontSize: 16, fontWeight: 700, color: "var(--red)",
                    background: "rgba(255,71,87,0.1)", padding: "4px 10px", borderRadius: 8,
                    fontFamily: "var(--mono)" }}>
                    {c.anomaly_score?.toFixed(2)}
                  </div>
                </div>
                {c.failure_reason && (
                  <div style={{ fontSize: 11, color: "var(--amber)", marginBottom: 8 }}>
                    Reason: {c.failure_reason.replace(/_/g, " ")}
                  </div>
                )}
                <button className="btn btn-secondary"
                  style={{ margin: 0, padding: "8px", fontSize: 12 }}
                  onClick={() => handleApprove(c.claim_id)}>
                  Manually approve
                </button>
              </div>
            ))
          )}
        </>
      )}

      {/* ── WORKERS LIST ── */}
      {tab === "workers" && (
        <>
          <div className="label-sm" style={{ marginBottom: 10 }}>
            Registered workers ({workers.length})
          </div>
          {workers.map((w) => (
            <div key={w.worker_id} className="card" style={{ padding: "12px 14px" }}>
              <div className="row">
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600 }}>{w.name || w.worker_id}</div>
                  <div style={{ fontSize: 11, color: "var(--muted)" }}>
                    {w.platform} · {w.city} · {w.plan} plan
                  </div>
                </div>
                <span className={`badge badge-${w.policy_active ? "green" : "red"}`}>
                  {w.policy_active ? "ACTIVE" : "INACTIVE"}
                </span>
              </div>
              <div style={{ display: "flex", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
                <span style={{ fontSize: 10, color: "var(--muted)",
                  background: "var(--navy)", padding: "2px 8px", borderRadius: 6 }}>
                  ₹{w.avg_daily_earnings}/day
                </span>
                <span style={{ fontSize: 10, color: "var(--muted)",
                  background: "var(--navy)", padding: "2px 8px", borderRadius: 6 }}>
                  Claims: {w.claims_last_4_weeks}
                </span>
                <span style={{ fontSize: 10,
                  color: w.reliability_score > 0.7 ? "var(--green)" : "var(--amber)",
                  background: "var(--navy)", padding: "2px 8px", borderRadius: 6 }}>
                  Reliability: {(w.reliability_score * 100).toFixed(0)}%
                </span>
              </div>
            </div>
          ))}
        </>
      )}

      {/* Bottom nav */}
      <nav className="bottom-nav">
        {[
          { to: "/dashboard", label: "Home",   icon: "🏠" },
          { to: "/claims",    label: "Claims", icon: "📋" },
          { to: "/admin",     label: "Admin",  icon: "⚙️", active: true },
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
