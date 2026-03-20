import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { registerWorker } from "../services/api";
import { startGPSTracking } from "../services/gps";

const STEPS = ["language", "platform", "earnings", "plan", "confirm"];

const LANGUAGES = [
  { code: "kn", label: "ಕನ್ನಡ" },
  { code: "hi", label: "हिन्दी" },
  { code: "ta", label: "தமிழ்" },
  { code: "te", label: "తెలుగు" },
  { code: "en", label: "English" },
];

const PLATFORMS = [
  { id: "blinkit", label: "Blinkit",  segment: "grocery" },
  { id: "zepto",   label: "Zepto",    segment: "grocery" },
  { id: "swiggy",  label: "Swiggy",   segment: "food"    },
  { id: "zomato",  label: "Zomato",   segment: "food"    },
  { id: "amazon",  label: "Amazon",   segment: "ecommerce" },
];

const PLANS = [
  { id: "basic",    daily: 1,  weekly: 7,  cap: 250, pct: 40, triggers: "Rain + Heat" },
  { id: "standard", daily: 3,  weekly: 21, cap: 500, pct: 60, triggers: "Rain + Heat + AQI" },
  { id: "max",      daily: 5,  weekly: 35, cap: 900, pct: 80, triggers: "All triggers + Curfew" },
];

const CITIES = ["bengaluru", "mumbai", "delhi", "hyderabad", "chennai", "kolkata", "pune"];

export default function Onboarding() {
  const navigate = useNavigate();
  const [step, setStep]       = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState("");
  const [form, setForm]       = useState({
    language: "en", phone: "", name: "",
    platform: "", platform_segment: "",
    city: "bengaluru", zone_id: "BLR_S",
    zone_lat: 12.9140, zone_lon: 77.6101,
    avg_daily_earnings: 520,
    avg_deliveries_per_day: 22,
    avg_delivery_distance: 1.8,
    plan: "standard",
    upi_id: "",
  });

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const next = () => { setError(""); setStep((s) => Math.min(s + 1, STEPS.length - 1)); };
  const back = () => setStep((s) => Math.max(s - 1, 0));

  const submit = async () => {
    if (!form.phone || !form.upi_id) {
      setError("Phone number and UPI ID are required.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const res = await registerWorker({ ...form });
      localStorage.setItem("worker_id", res.worker_id);
      localStorage.setItem("worker_name", form.name || "Partner");
      localStorage.setItem("plan", form.plan);
      await startGPSTracking(res.worker_id);
      navigate("/dashboard");
    } catch (e) {
      setError(e.response?.data?.detail || "Registration failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="screen">
      <div className="logo-row">
        <div className="logo-icon">🛡</div>
        <span className="logo-text">ShieldShift</span>
        <span style={{ marginLeft: "auto", fontSize: 12, color: "var(--muted)" }}>
          {step + 1} / {STEPS.length}
        </span>
      </div>

      {/* Progress bar */}
      <div style={{ height: 3, background: "var(--border)", borderRadius: 2, marginBottom: 28 }}>
        <div style={{
          height: "100%", borderRadius: 2, background: "var(--blue)",
          width: `${((step + 1) / STEPS.length) * 100}%`,
          transition: "width 0.3s ease"
        }} />
      </div>

      {/* ── STEP 0: LANGUAGE ── */}
      {step === 0 && (
        <>
          <div className="screen-title">Choose your language</div>
          <div className="screen-sub">ನಿಮ್ಮ ಭಾಷೆ ಆರಿಸಿ / अपनी भाषा चुनें</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 20 }}>
            {LANGUAGES.map((l) => (
              <div key={l.code}
                onClick={() => set("language", l.code)}
                style={{
                  padding: "14px 10px", textAlign: "center", borderRadius: 12,
                  border: `1px solid ${form.language === l.code ? "var(--blue)" : "var(--border)"}`,
                  background: form.language === l.code ? "rgba(26,107,255,0.15)" : "var(--surface)",
                  color: form.language === l.code ? "#7EB3FF" : "white",
                  cursor: "pointer", fontWeight: 500, fontSize: 15,
                }}>
                {l.label}
              </div>
            ))}
          </div>
          <button className="btn btn-primary" style={{ marginTop: "auto" }} onClick={next}>
            Continue →
          </button>
        </>
      )}

      {/* ── STEP 1: PLATFORM ── */}
      {step === 1 && (
        <>
          <div className="screen-title">Which platform do you work on?</div>
          <div className="screen-sub">Select your primary delivery app</div>
          {PLATFORMS.map((p) => (
            <div key={p.id}
              onClick={() => { set("platform", p.id); set("platform_segment", p.segment); }}
              style={{
                padding: "14px 16px", borderRadius: 12, marginBottom: 8, cursor: "pointer",
                border: `1px solid ${form.platform === p.id ? "var(--blue)" : "var(--border)"}`,
                background: form.platform === p.id ? "rgba(26,107,255,0.15)" : "var(--surface)",
                display: "flex", alignItems: "center", justifyContent: "space-between",
              }}>
              <span style={{ fontWeight: 600 }}>{p.label}</span>
              <span style={{ fontSize: 11, color: "var(--muted)", textTransform: "capitalize" }}>
                {p.segment}
              </span>
            </div>
          ))}
          <div className="field-group" style={{ marginTop: 14 }}>
            <div className="field-label">Your city</div>
            <select value={form.city} onChange={(e) => set("city", e.target.value)}>
              {CITIES.map((c) => (
                <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>
              ))}
            </select>
          </div>
          <div style={{ display: "flex", gap: 10, marginTop: "auto" }}>
            <button className="btn btn-secondary" style={{ margin: 0 }} onClick={back}>← Back</button>
            <button className="btn btn-primary" disabled={!form.platform} onClick={next}>Continue →</button>
          </div>
        </>
      )}

      {/* ── STEP 2: EARNINGS ── */}
      {step === 2 && (
        <>
          <div className="screen-title">Your earnings profile</div>
          <div className="screen-sub">This helps us calculate your fair premium and payout</div>
          <div className="field-group">
            <div className="field-label">Average daily earnings (₹)</div>
            <input type="number" value={form.avg_daily_earnings}
              onChange={(e) => set("avg_daily_earnings", parseFloat(e.target.value))}
              placeholder="e.g. 520" />
          </div>
          <div className="field-group">
            <div className="field-label">Average deliveries per day</div>
            <input type="number" value={form.avg_deliveries_per_day}
              onChange={(e) => set("avg_deliveries_per_day", parseInt(e.target.value))}
              placeholder="e.g. 22" />
          </div>
          <div className="card" style={{ background: "rgba(0,201,167,0.06)", borderColor: "rgba(0,201,167,0.2)" }}>
            <div style={{ fontSize: 12, color: "var(--teal)" }}>
              Per delivery: ₹{(form.avg_daily_earnings / Math.max(form.avg_deliveries_per_day, 1)).toFixed(0)}
              &nbsp;· This will be validated against platform norms
            </div>
          </div>
          <div className="field-group">
            <div className="field-label">Phone number</div>
            <input type="tel" value={form.phone}
              onChange={(e) => set("phone", e.target.value)}
              placeholder="10-digit mobile number" maxLength={10} />
          </div>
          <div className="field-group">
            <div className="field-label">Your name (optional)</div>
            <input type="text" value={form.name}
              onChange={(e) => set("name", e.target.value)}
              placeholder="e.g. Ravi M." />
          </div>
          <div style={{ display: "flex", gap: 10, marginTop: "auto" }}>
            <button className="btn btn-secondary" style={{ margin: 0 }} onClick={back}>← Back</button>
            <button className="btn btn-primary" onClick={next}>Continue →</button>
          </div>
        </>
      )}

      {/* ── STEP 3: PLAN ── */}
      {step === 3 && (
        <>
          <div className="screen-title">Pick your shield</div>
          <div className="screen-sub">Weekly auto-pay via UPI. Pause anytime.</div>
          {PLANS.map((p) => (
            <div key={p.id}
              onClick={() => set("plan", p.id)}
              style={{
                padding: "14px 16px", borderRadius: 14, marginBottom: 10, cursor: "pointer",
                border: `1px solid ${form.plan === p.id ? "var(--blue)" : "var(--border)"}`,
                background: form.plan === p.id ? "rgba(26,107,255,0.12)" : "var(--surface)",
              }}>
              <div className="row">
                <div>
                  <div style={{ fontWeight: 700, textTransform: "capitalize", marginBottom: 2 }}>{p.id}</div>
                  <div style={{ fontSize: 12, color: "var(--muted)" }}>₹{p.daily}/day · {p.triggers}</div>
                </div>
                <div style={{ textAlign: "right" }}>
                  <div style={{ fontSize: 18, fontWeight: 700, color: "var(--teal)" }}>₹{p.weekly}</div>
                  <div style={{ fontSize: 10, color: "var(--muted)" }}>/week</div>
                </div>
              </div>
              {form.plan === p.id && (
                <div style={{ marginTop: 10, padding: "8px 10px", background: "rgba(26,107,255,0.1)", borderRadius: 8, fontSize: 12, color: "#7EB3FF" }}>
                  Up to ₹{p.cap}/week · {p.pct}% income replacement
                </div>
              )}
            </div>
          ))}
          <div className="field-group" style={{ marginTop: 10 }}>
            <div className="field-label">UPI ID for payouts</div>
            <input type="text" value={form.upi_id}
              onChange={(e) => set("upi_id", e.target.value)}
              placeholder="e.g. ravi@paytm" />
          </div>
          <div style={{ display: "flex", gap: 10, marginTop: "auto" }}>
            <button className="btn btn-secondary" style={{ margin: 0 }} onClick={back}>← Back</button>
            <button className="btn btn-primary" disabled={!form.upi_id} onClick={next}>Review →</button>
          </div>
        </>
      )}

      {/* ── STEP 4: CONFIRM ── */}
      {step === 4 && (
        <>
          <div className="screen-title">Confirm your details</div>
          <div className="screen-sub">Review before activating your policy</div>
          {[
            ["Platform",  PLATFORMS.find((p) => p.id === form.platform)?.label || form.platform],
            ["City",      form.city.charAt(0).toUpperCase() + form.city.slice(1)],
            ["Daily earnings", `₹${form.avg_daily_earnings}`],
            ["Deliveries/day", form.avg_deliveries_per_day],
            ["Plan",      form.plan.charAt(0).toUpperCase() + form.plan.slice(1)],
            ["Weekly premium", `₹${PLANS.find((p) => p.id === form.plan)?.weekly}/week`],
            ["Weekly cap", `₹${PLANS.find((p) => p.id === form.plan)?.cap}`],
            ["UPI ID",    form.upi_id],
          ].map(([k, v]) => (
            <div key={k} className="row" style={{ padding: "10px 0", borderBottom: "1px solid var(--border)" }}>
              <span style={{ fontSize: 13, color: "var(--muted)" }}>{k}</span>
              <span style={{ fontSize: 13, fontWeight: 600 }}>{v}</span>
            </div>
          ))}
          {error && (
            <div style={{ marginTop: 14, padding: "10px 14px", background: "rgba(255,71,87,0.1)",
              border: "1px solid rgba(255,71,87,0.3)", borderRadius: 10, fontSize: 13, color: "var(--red)" }}>
              {error}
            </div>
          )}
          <div style={{ display: "flex", gap: 10, marginTop: "auto", paddingTop: 16 }}>
            <button className="btn btn-secondary" style={{ margin: 0 }} onClick={back}>← Edit</button>
            <button className="btn btn-primary" onClick={submit} disabled={loading}>
              {loading ? "Activating..." : "Activate Policy →"}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
