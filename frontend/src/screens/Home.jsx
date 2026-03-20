import { Link } from "react-router-dom";

export default function Home() {
  return (
    <div className="screen">
      <div className="logo-row" style={{ marginBottom: 18 }}>
        <div className="logo-icon">SS</div>
        <span className="logo-text">ShieldShift</span>
      </div>

      <h1 className="screen-title">Parametric income protection demo</h1>
      <p className="screen-sub">
        Basic frontend with working routes so your team can open and navigate the app quickly.
      </p>

      <div className="card">
        <div className="label-sm">Get started</div>
        <p style={{ fontSize: 14, color: "var(--muted)", lineHeight: 1.5, marginBottom: 14 }}>
          Start onboarding a worker profile, then use dashboard, claims, and admin routes.
        </p>
        <Link
          to="/onboarding"
          className="btn btn-primary"
          style={{ display: "block", textAlign: "center", textDecoration: "none" }}
        >
          Start onboarding
        </Link>
      </div>

      <div className="card" style={{ marginTop: 10 }}>
        <div className="label-sm">Quick routes</div>
        <div style={{ display: "grid", gap: 8 }}>
          {[
            { to: "/dashboard", label: "Dashboard" },
            { to: "/claims", label: "Claims" },
            { to: "/admin", label: "Admin Panel" },
          ].map((route) => (
            <Link
              key={route.to}
              to={route.to}
              className="btn btn-secondary"
              style={{ display: "block", textAlign: "center", textDecoration: "none", marginTop: 0 }}
            >
              Open {route.label}
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
