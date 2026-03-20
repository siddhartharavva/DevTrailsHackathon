import axios from "axios";

const API = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000/api",
  timeout: 10000,
});

// ── ONBOARDING ───────────────────────────────────────────────────────────────

export const registerWorker = (data) =>
  API.post("/onboarding/register", data).then((r) => r.data);

export const getWorker = (workerId) =>
  API.get(`/onboarding/worker/${workerId}`).then((r) => r.data);

export const sendGPSPing = (data) =>
  API.post("/onboarding/gps/ping", data).then((r) => r.data);

// ── CLAIMS ───────────────────────────────────────────────────────────────────

export const getWorkerClaims = (workerId) =>
  API.get(`/claims/worker/${workerId}`).then((r) => r.data);

export const getWorkerSummary = (workerId) =>
  API.get(`/claims/worker/${workerId}/summary`).then((r) => r.data);

export const getClaim = (claimId) =>
  API.get(`/claims/${claimId}`).then((r) => r.data);

// ── TRIGGERS ─────────────────────────────────────────────────────────────────

export const getEvents = () =>
  API.get("/triggers/events").then((r) => r.data);

export const fireTrigger = (data) =>
  API.post("/triggers/fire", data).then((r) => r.data);

export const checkWeather = (city, zoneId) =>
  API.post("/triggers/check-weather", { city, zone_id: zoneId }).then((r) => r.data);

// ── ADMIN ────────────────────────────────────────────────────────────────────

export const getAdminDashboard = () =>
  API.get("/admin/dashboard").then((r) => r.data);

export const getFlaggedClaims = () =>
  API.get("/admin/claims/flagged").then((r) => r.data);

export const listWorkers = () =>
  API.get("/admin/workers").then((r) => r.data);

export const approveClaim = (claimId) =>
  API.post(`/admin/claims/${claimId}/approve`).then((r) => r.data);
