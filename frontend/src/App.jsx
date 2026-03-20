import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Onboarding from "./screens/Onboarding";
import Dashboard  from "./screens/Dashboard";
import Claims     from "./screens/Claims";
import Admin      from "./screens/Admin";
import "./index.css";

function App() {
  const workerId = localStorage.getItem("worker_id");

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/onboarding" element={<Onboarding />} />
        <Route path="/dashboard"  element={workerId ? <Dashboard /> : <Navigate to="/onboarding" />} />
        <Route path="/claims"     element={workerId ? <Claims />    : <Navigate to="/onboarding" />} />
        <Route path="/admin"      element={<Admin />} />
        <Route path="*"           element={<Navigate to={workerId ? "/dashboard" : "/onboarding"} />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
