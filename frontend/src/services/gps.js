import { sendGPSPing } from "./api";

let pingInterval = null;

export async function startGPSTracking(workerId) {
  if (pingInterval) return; // already running

  const sendPing = async () => {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        try {
          await sendGPSPing({
            worker_id: workerId,
            lat: pos.coords.latitude,
            lon: pos.coords.longitude,
            accuracy_m: pos.coords.accuracy,
            battery_pct: await getBatteryLevel(),
            app_state: document.visibilityState === "visible" ? "foreground" : "background",
          });
        } catch (e) {
          console.warn("GPS ping failed:", e.message);
        }
      },
      (err) => console.warn("GPS error:", err.message),
      { enableHighAccuracy: true, timeout: 8000 }
    );
  };

  await sendPing(); // immediate first ping
  pingInterval = setInterval(sendPing, 10 * 60 * 1000); // every 10 min
}

export function stopGPSTracking() {
  if (pingInterval) {
    clearInterval(pingInterval);
    pingInterval = null;
  }
}

async function getBatteryLevel() {
  try {
    if ("getBattery" in navigator) {
      const battery = await navigator.getBattery();
      return Math.round(battery.level * 100);
    }
  } catch (_) {}
  return 100;
}
