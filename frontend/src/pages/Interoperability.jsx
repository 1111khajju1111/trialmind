import { useEffect, useState } from "react";
import api from "../api/client.js";
import GlassCard from "../components/ui/GlassCard.jsx";
import GradientButton from "../components/ui/GradientButton.jsx";
import { IconLink, IconExport } from "../design-system/icons.jsx";

// Priority 7 -- FHIR + CDISC Demonstrator. A convincing interoperability
// preview built from live data, not a certified conformance statement --
// see backend/app/services/interop.py for the field-mapping notes this
// page's "View field mapping" button surfaces.

const FHIR_RESOURCES = ["Patient", "ResearchStudy", "ResearchSubject", "Observation", "AdverseEvent", "Consent"];
const SDTM_DOMAINS = [
  { code: "DM", label: "Demographics (DM)" },
  { code: "AE", label: "Adverse Events (AE)" },
];

export default function Interoperability() {
  const [studies, setStudies] = useState([]);
  const [studyId, setStudyId] = useState("");
  const [preview, setPreview] = useState(null);
  const [previewLabel, setPreviewLabel] = useState(null);
  const [mapping, setMapping] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(null);

  useEffect(() => {
    api.getStudies().then((r) => setStudies(r.data)).catch(() => {});
  }, []);

  const previewFhir = async (resourceType) => {
    setBusy(resourceType);
    setError(null);
    try {
      const res = await api.getFhirBundle(resourceType, studyId || undefined);
      setPreview(res.data);
      setPreviewLabel(`FHIR Bundle — ${resourceType}`);
      setMapping(null);
    } catch (e) {
      setError("Could not fetch FHIR bundle.");
    } finally {
      setBusy(null);
    }
  };

  const downloadSdtm = async (domain) => {
    setBusy(domain);
    setError(null);
    try {
      const res = await api.downloadSdtm(domain, studyId || undefined);
      const url = window.URL.createObjectURL(new Blob([res.data], { type: "text/csv" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `${domain}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      setError("Could not export SDTM CSV.");
    } finally {
      setBusy(null);
    }
  };

  const showMapping = async () => {
    setBusy("mapping");
    setError(null);
    try {
      const res = await api.getMappingDoc();
      setMapping(res.data);
      setPreview(null);
      setPreviewLabel(null);
    } catch (e) {
      setError("Could not load mapping documentation.");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div>
      <h1>Interoperability</h1>
      <p className="subtitle">
        FHIR R4 resource previews and CDISC SDTM-style exports built from live study data —
        a convincing demonstrator of standards alignment, not a certified conformance claim.
        See the field mapping for exactly which internal fields feed which standard field.
      </p>

      {error && <div className="alert-box">{error}</div>}

      <GlassCard>
        <label>Scope to a study (optional)</label>
        <select value={studyId} onChange={(e) => setStudyId(e.target.value)}>
          <option value="">All studies</option>
          {studies.map((s) => (
            <option key={s.id} value={s.id}>{s.title} ({s.study_code})</option>
          ))}
        </select>
      </GlassCard>

      <div className="section-heading">
        <span className="section-heading-icon"><IconLink /></span> FHIR R4 Resources
      </div>
      <GlassCard>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {FHIR_RESOURCES.map((r) => (
            <GradientButton key={r} variant="secondary" onClick={() => previewFhir(r)} disabled={busy === r}>
              {busy === r ? "Loading..." : `Preview ${r}`}
            </GradientButton>
          ))}
        </div>
      </GlassCard>

      <div className="section-heading">
        <span className="section-heading-icon"><IconExport /></span> CDISC SDTM Export
      </div>
      <GlassCard>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {SDTM_DOMAINS.map((d) => (
            <GradientButton key={d.code} variant="primary" onClick={() => downloadSdtm(d.code)} disabled={busy === d.code}>
              {busy === d.code ? "Exporting..." : `Export ${d.label} CSV`}
            </GradientButton>
          ))}
        </div>
      </GlassCard>

      <GlassCard>
        <GradientButton variant="secondary" onClick={showMapping} disabled={busy === "mapping"}>
          {busy === "mapping" ? "Loading..." : "View field mapping documentation"}
        </GradientButton>
      </GlassCard>

      {previewLabel && preview && (
        <GlassCard>
          <strong>{previewLabel}</strong>
          <p style={{ fontSize: 12, color: "var(--text-muted)" }}>{preview.total} resource(s)</p>
          <pre className="draft-content" style={{ maxHeight: 400, overflow: "auto" }}>
            {JSON.stringify(preview, null, 2)}
          </pre>
        </GlassCard>
      )}

      {mapping && (
        <GlassCard>
          <strong>Internal Data Model → FHIR / SDTM Mapping</strong>
          <pre className="draft-content" style={{ maxHeight: 500, overflow: "auto", whiteSpace: "pre-wrap" }}>
            {mapping}
          </pre>
        </GlassCard>
      )}
    </div>
  );
}
