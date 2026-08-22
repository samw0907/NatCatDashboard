// frontend/src/App.tsx

import { useEffect, useState } from "react";
import "maplibre-gl/dist/maplibre-gl.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

function App() {
  const [backendStatus, setBackendStatus] = useState<"checking" | "ok" | "unreachable">(
    "checking",
  );

  useEffect(() => {
    fetch(`${API_BASE_URL}/health`)
      .then((res) => (res.ok ? setBackendStatus("ok") : setBackendStatus("unreachable")))
      .catch(() => setBackendStatus("unreachable"));
  }, []);

  return (
    <main style={{ fontFamily: "system-ui, sans-serif", padding: "2rem" }}>
      <h1>NatCatDashboard</h1>
      <p>Scaffold placeholder — queue, map and event detail views land in Phase 5.</p>
      <p>Backend health check: {backendStatus}</p>
    </main>
  );
}

export default App;
