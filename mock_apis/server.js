/**
 * ShieldShift Mock APIs
 * Simulates: Curfew/Gazette API, Platform Status API, Worker Registry API
 * Run: node server.js
 */

const express = require("express");
const app = express();
app.use(express.json());

const PORT = process.env.PORT || 4000;

// ── ZONE DATA ────────────────────────────────────────────────────────────────

const ZONES = {
  "BLR_S": { city: "bengaluru", name: "Bengaluru South", lat: 12.9140, lon: 77.6101 },
  "BLR_N": { city: "bengaluru", name: "Bengaluru North", lat: 13.0358, lon: 77.5970 },
  "MUM_W": { city: "mumbai",    name: "Mumbai West",     lat: 19.0596, lon: 72.8295 },
  "DEL_C": { city: "delhi",     name: "Delhi Central",   lat: 28.6448, lon: 77.2167 },
  "HYD_H": { city: "hyderabad", name: "Hyderabad HITECH",lat: 17.4474, lon: 78.3762 },
};

// In-memory active events store (resets on server restart)
let activeEvents = [];
let eventCounter = 1;

// ── ROOT ─────────────────────────────────────────────────────────────────────

app.get("/", (req, res) => {
  res.json({
    service: "ShieldShift Mock APIs",
    version: "1.0.0",
    endpoints: {
      curfew:   "/curfew/events, /curfew/fire, /curfew/zone/:zone_id",
      platform: "/platform/zone-status, /platform/order-volume/:zone_id",
      registry: "/registry/verify, /registry/worker/:phone",
    },
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// MOCK API 1 — CURFEW / CIVIC GAZETTE
// Simulates municipal curfew orders, Section 144, local bandhs
// ═══════════════════════════════════════════════════════════════════════════

app.get("/curfew/events", (req, res) => {
  const { zone_id, city } = req.query;
  let events = activeEvents.filter((e) => e.type === "civic");
  if (zone_id) events = events.filter((e) => e.zone_id === zone_id);
  if (city)    events = events.filter((e) => e.city === city);
  res.json({ events, count: events.length, source: "mock_gazette_api" });
});

app.get("/curfew/zone/:zone_id", (req, res) => {
  const { zone_id } = req.params;
  const zoneEvents = activeEvents.filter(
    (e) => e.zone_id === zone_id && e.type === "civic" && e.active
  );
  const zone = ZONES[zone_id] || { city: "unknown", name: zone_id };
  res.json({
    zone_id,
    zone_name: zone.name,
    city: zone.city,
    curfew_active: zoneEvents.length > 0,
    active_events: zoneEvents,
    checked_at: new Date().toISOString(),
  });
});

app.post("/curfew/fire", (req, res) => {
  const { zone_id, severity = "orange", description, duration_hours = 4 } = req.body;
  if (!zone_id) return res.status(400).json({ error: "zone_id required" });
  const zone = ZONES[zone_id] || { city: "unknown", name: zone_id };
  const event = {
    event_id: `CURFEW_${String(eventCounter++).padStart(4, "0")}`,
    type: "civic",
    trigger_type: "CIVIC_CURFEW",
    zone_id,
    city: zone.city,
    zone_name: zone.name,
    severity,
    description: description || `Section 144 imposed in ${zone.name}`,
    issued_at: new Date().toISOString(),
    expires_at: new Date(Date.now() + duration_hours * 3600000).toISOString(),
    active: true,
    source: "mock_gazette_api",
  };
  activeEvents.push(event);
  res.json({ success: true, event });
});

app.post("/curfew/resolve/:event_id", (req, res) => {
  const evt = activeEvents.find((e) => e.event_id === req.params.event_id);
  if (evt) evt.active = false;
  res.json({ resolved: true, event_id: req.params.event_id });
});

// ═══════════════════════════════════════════════════════════════════════════
// MOCK API 2 — PLATFORM STATUS (Simulates Blinkit/Zepto/Swiggy)
// Simulates order volume drops and zone availability
// ═══════════════════════════════════════════════════════════════════════════

app.get("/platform/zone-status", (req, res) => {
  const { zone_id, platform = "blinkit" } = req.query;
  if (!zone_id) return res.status(400).json({ error: "zone_id required" });

  // Check if there's an active weather or civic event in this zone
  const hasActiveEvent = activeEvents.some(
    (e) => e.zone_id === zone_id && e.active
  );

  const baseVolume = Math.floor(Math.random() * 30) + 60; // 60–90 baseline
  const currentVolume = hasActiveEvent
    ? Math.floor(baseVolume * (Math.random() * 0.3 + 0.05)) // 5–35% of normal
    : baseVolume;

  res.json({
    zone_id,
    platform,
    zone_operational: !hasActiveEvent || currentVolume > 20,
    current_order_volume_pct: currentVolume,   // % of normal volume
    baseline_volume_pct: baseVolume,
    active_dark_stores: hasActiveEvent ? Math.floor(Math.random() * 2) : Math.floor(Math.random() * 3) + 2,
    avg_delivery_time_min: hasActiveEvent ? Math.floor(Math.random() * 30) + 45 : Math.floor(Math.random() * 15) + 20,
    disruption_active: hasActiveEvent,
    checked_at: new Date().toISOString(),
    source: `mock_${platform}_api`,
  });
});

app.get("/platform/order-volume/:zone_id", (req, res) => {
  const { zone_id } = req.params;
  const { platform = "blinkit", hours = 24 } = req.query;

  // Generate hourly volume data
  const data = [];
  const now = new Date();
  for (let i = parseInt(hours); i >= 0; i--) {
    const ts = new Date(now - i * 3600000);
    const hour = ts.getHours();
    // Peak hours: 8–10am, 12–2pm, 6–9pm
    const isPeak = (hour >= 8 && hour <= 10) || (hour >= 12 && hour <= 14) || (hour >= 18 && hour <= 21);
    const hasEvent = activeEvents.some(
      (e) => e.zone_id === zone_id && e.active &&
             new Date(e.issued_at) <= ts
    );
    const volume = hasEvent
      ? Math.floor(Math.random() * 15) + 2
      : isPeak
        ? Math.floor(Math.random() * 40) + 60
        : Math.floor(Math.random() * 30) + 20;
    data.push({ timestamp: ts.toISOString(), volume_pct: volume });
  }

  res.json({ zone_id, platform, hourly_volume: data, source: `mock_${platform}_api` });
});

// ═══════════════════════════════════════════════════════════════════════════
// MOCK API 3 — WORKER REGISTRY (Simulates e-Shram / Platform Worker ID)
// ═══════════════════════════════════════════════════════════════════════════

// Pre-seeded mock worker database
const MOCK_REGISTRY = {
  "9876543210": { name: "Ravi M.",    platform: "blinkit", city: "bengaluru", verified: true,  worker_id: "ESHRAM_BLR_001" },
  "9876543211": { name: "Suresh K.",  platform: "zepto",   city: "delhi",     verified: true,  worker_id: "ESHRAM_DEL_002" },
  "9876543212": { name: "Priya L.",   platform: "swiggy",  city: "mumbai",    verified: true,  worker_id: "ESHRAM_MUM_003" },
  "9876543213": { name: "Arjun P.",   platform: "blinkit", city: "bengaluru", verified: false, worker_id: null },
};

app.post("/registry/verify", (req, res) => {
  const { phone, platform } = req.body;
  if (!phone) return res.status(400).json({ error: "phone required" });

  const record = MOCK_REGISTRY[phone];
  if (record) {
    return res.json({
      verified: record.verified,
      worker_id: record.worker_id,
      name: record.name,
      registered_platform: record.platform,
      city: record.city,
      platform_match: record.platform === platform,
      source: "mock_eshram_registry",
    });
  }

  // Unknown phone — treat as new worker (not in e-Shram yet)
  res.json({
    verified: false,
    worker_id: null,
    message: "Worker not found in registry — self-registration accepted",
    source: "mock_eshram_registry",
  });
});

app.get("/registry/worker/:phone", (req, res) => {
  const record = MOCK_REGISTRY[req.params.phone];
  if (!record) return res.status(404).json({ error: "not_found" });
  res.json({ ...record, source: "mock_eshram_registry" });
});

// ── ACTIVE EVENTS UTILS ──────────────────────────────────────────────────────

app.get("/events/active", (req, res) => {
  const active = activeEvents.filter((e) => e.active);
  res.json({ events: active, count: active.length });
});

app.delete("/events/clear", (req, res) => {
  activeEvents = [];
  res.json({ cleared: true });
});

// ── START ────────────────────────────────────────────────────────────────────

app.listen(PORT, () => {
  console.log(`\n🔌 ShieldShift Mock APIs running on http://localhost:${PORT}`);
  console.log(`   /curfew    → Civic event simulation`);
  console.log(`   /platform  → Order volume simulation`);
  console.log(`   /registry  → Worker ID verification\n`);
});
