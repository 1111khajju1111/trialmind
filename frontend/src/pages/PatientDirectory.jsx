import { useEffect, useMemo, useState } from "react";
import api from "../api/client.js";
import GlassCard from "../components/ui/GlassCard.jsx";

const VERDICT_LABEL = {
  ELIGIBLE: "Eligible",
  NOT_ELIGIBLE: "Not Eligible",
  POTENTIAL_MATCH: "Potential Match",
  VERIFICATION_REQUIRED: "Verification Required",
};

// Higher rank = more worth surfacing as a patient's "best" verdict when
// they've been evaluated against more than one trial.
const VERDICT_RANK = { ELIGIBLE: 3, POTENTIAL_MATCH: 2, VERIFICATION_REQUIRED: 1, NOT_ELIGIBLE: 0 };

function parseBiomarkers(raw) {
  if (!raw) return [];
  return raw.split(",").map((pair) => {
    const [key, value] = pair.split(":");
    return { key: (key || "").trim(), value: (value || "").trim() };
  }).filter((b) => b.key);
}

export default function PatientDirectory() {
  const [patients, setPatients] = useState([]);
  const [matches, setMatches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [conditionFilter, setConditionFilter] = useState("all");

  useEffect(() => {
    Promise.all([api.getPatients(), api.getMatches()])
      .then(([p, m]) => {
        setPatients(p.data);
        setMatches(m.data);
      })
      .catch(() => setError("Could not reach backend. Check VITE_API_URL."))
      .finally(() => setLoading(false));
  }, []);

  const conditions = useMemo(
    () => Array.from(new Set(patients.map((p) => p.condition).filter(Boolean))),
    [patients]
  );

  const matchesByPatient = useMemo(() => {
    const grouped = {};
    for (const m of matches) {
      (grouped[m.patient_id] ||= []).push(m);
    }
    return grouped;
  }, [matches]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return patients.filter((p) => {
      if (conditionFilter !== "all" && p.condition !== conditionFilter) return false;
      if (!q) return true;
      return (
        p.name?.toLowerCase().includes(q) ||
        p.condition?.toLowerCase().includes(q) ||
        p.location?.toLowerCase().includes(q)
      );
    });
  }, [patients, search, conditionFilter]);

  return (
    <div>
      <h1>Patient Directory</h1>
      <p className="subtitle">
        Every patient record available for matching, with a summary of how
        they've fared across trial runs so far. Search or filter by
        condition to narrow the list.
      </p>

      {error && <div className="alert-box">{error}</div>}
      {loading && <p className="loading">Loading...</p>}

      {!loading && (
        <GlassCard style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by name, condition, or location..."
            style={{ flex: "1 1 260px", margin: 0 }}
          />
          <select
            value={conditionFilter}
            onChange={(e) => setConditionFilter(e.target.value)}
            style={{ flex: "0 0 auto", width: "auto" }}
          >
            <option value="all">All conditions</option>
            {conditions.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </GlassCard>
      )}

      {!loading && !error && filtered.length === 0 && (
        <GlassCard>No patients match this search.</GlassCard>
      )}

      <div className="agent-grid" style={{ marginTop: 16 }}>
        {filtered.map((p) => {
          const patientMatches = matchesByPatient[p.id] || [];
          const best = patientMatches.reduce(
            (acc, m) => (!acc || VERDICT_RANK[m.verdict] > VERDICT_RANK[acc.verdict] ? m : acc),
            null
          );
          return (
            <GlassCard key={p.id}>
              <div className="card-header">
                <strong>{p.name}</strong>
                {best && (
                  <span className={`badge ${best.verdict}`}>{VERDICT_LABEL[best.verdict] || best.verdict}</span>
                )}
              </div>
              <p style={{ fontSize: 12.5, color: "var(--text-secondary)", margin: "4px 0" }}>
                {p.age ? `${p.age} yrs · ` : ""}{p.condition || "No condition on file"}
                {p.location ? ` · ${p.location}` : ""}
              </p>
              {parseBiomarkers(p.biomarkers).length > 0 && (
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6, margin: "8px 0" }}>
                  {parseBiomarkers(p.biomarkers).map((b) => (
                    <span
                      key={b.key}
                      className="badge normal"
                      style={{ fontSize: 11 }}
                      title={b.key}
                    >
                      {b.key}: {b.value}
                    </span>
                  ))}
                </div>
              )}
              <p style={{ fontSize: 12, color: "var(--text-muted)", margin: "8px 0 0" }}>
                {patientMatches.length === 0
                  ? "Not yet evaluated against any trial."
                  : `Evaluated ${patientMatches.length} time${patientMatches.length > 1 ? "s" : ""} across ${new Set(patientMatches.map((m) => m.trial_id)).size} trial(s).`}
              </p>
            </GlassCard>
          );
        })}
      </div>
    </div>
  );
}
