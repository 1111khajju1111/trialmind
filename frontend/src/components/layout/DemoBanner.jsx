import { useEffect, useState } from "react";
import api from "../../api/client.js";

export default function DemoBanner() {
  // Defaults to shown (fail-open toward the safer "label it as demo"
  // state) until the health check confirms otherwise, and stays hidden
  // outright if the backend explicitly reports demo_mode: false.
  const [demoMode, setDemoMode] = useState(true);

  useEffect(() => {
    api.getHealth()
      .then((res) => setDemoMode(res.data?.demo_mode !== false))
      .catch(() => setDemoMode(true));
  }, []);

  if (!demoMode) return null;

  return (
    <div className="demo-banner">
      <span className="demo-banner-dot" aria-hidden="true">●</span>
      DEMO ENVIRONMENT &middot; SYNTHETIC DATA
    </div>
  );
}
