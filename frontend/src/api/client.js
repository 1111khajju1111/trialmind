import axios from "axios";
import { getStoredRole } from "../context/RoleContext.jsx";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const client = axios.create({ baseURL: API_URL });

// Priority 5 -- RBAC (thin, demo-appropriate). Every request carries the
// coordinator's currently-selected role so the backend (app/rbac.py) can
// enforce role-gated actions and the global read-only rule for Regulator.
client.interceptors.request.use((config) => {
  config.headers["X-User-Role"] = getStoredRole();
  return config;
});

export const api = {
  // trials / protocol ingestion
  getTrials: () => client.get("/trials/"),
  
  // Backend /trials/upload takes multipart Form fields (to support optional
  // PDF upload), not a JSON body. Accept either a FormData (built by the
  // caller, e.g. when a file is attached) or a plain object -- plain objects
  // are converted to FormData here so a JSON POST (which the endpoint can't
  // parse and would 422 on) is never sent.
  uploadProtocol: (payload) => {
    const formData = payload instanceof FormData ? payload : (() => {
      const fd = new FormData();
      Object.entries(payload || {}).forEach(([key, value]) => {
        if (value !== undefined && value !== null) fd.append(key, value);
      });
      return fd;
    })();
    return client.post("/trials/upload", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },

  getTrialCriteria: (trialId) => client.get(`/trials/${trialId}/criteria`),
  linkTrialToStudy: (trialId, studyId) =>
    client.patch(`/trials/${trialId}/link-study`, null, { params: { study_id: studyId } }),

  // patient matching (agentic, async with polling)
  getPatients: () => client.get("/patients/"),
  // Priority 2: siteId optionally scopes the run to one site within the
  // trial's linked study.
  startMatching: (trialId, siteId) =>
    client.post("/patients/match/start", { trial_id: trialId, site_id: siteId ?? null }),
  getMatches: (runId) => client.get("/patients/matches", { params: runId ? { run_id: runId } : {} }),
  generateOutreach: (matchId) => client.post(`/patients/matches/${matchId}/outreach`),

  // audit / agent timeline
  getTimeline: (runId) => client.get(`/audit/timeline/${runId}`),
  getRuns: () => client.get("/audit/runs"),

  // regulatory drafting
  createDraft: (payload) => client.post("/regulatory/draft", payload),
  getDrafts: () => client.get("/regulatory/drafts"),

  // lab scheduling
  getSamples: () => client.get("/lab/samples"),
  getAlerts: () => client.get("/lab/alerts"),
  getEquipment: () => client.get("/lab/equipment"),

  sendOutreach: (matchId, payload) =>
  client.post(`/patients/matches/${matchId}/send-outreach`, payload),

  // approvals
  submitApproval: (payload) => client.post("/approvals/", payload),
  getApprovalLog: () => client.get("/approvals/log"),

  // demo reliability
  resetDemo: () => client.post("/admin/reset"),
  getHealth: () => client.get("/health"),

  // ---------- Priority 1: Core CTMS ----------
  getPortfolio: () => client.get("/dashboard/portfolio"),

  getStudies: () => client.get("/studies/"),
  getStudy: (studyId) => client.get(`/studies/${studyId}`),
  createStudy: (payload) => client.post("/studies/", payload),
  updateRecruitment: (studyId, payload) => client.patch(`/studies/${studyId}/recruitment`, payload),

  getSites: (studyId) => client.get(`/studies/${studyId}/sites`),
  createSite: (studyId, payload) => client.post(`/studies/${studyId}/sites`, payload),

  getMilestones: (studyId) => client.get(`/studies/${studyId}/milestones`),
  createMilestone: (studyId, payload) => client.post(`/studies/${studyId}/milestones`, payload),

  // ---------- Priority 4: Ethics + CTRI + Regulatory Compliance ----------
  getRegulatoryTimeline: (studyId) => client.get(`/studies/${studyId}/regulatory-timeline`),
  updateCTRI: (studyId, payload) => client.patch(`/studies/${studyId}/ctri`, payload),
  getComplianceAlerts: (studyId) =>
    client.get("/compliance/alerts", { params: studyId ? { study_id: studyId } : {} }),
  getRegulatoryDashboard: () => client.get("/dashboard/regulatory"),

  getDeviations: (studyId) => client.get(`/studies/${studyId}/deviations`),
  createDeviation: (studyId, payload) => client.post(`/studies/${studyId}/deviations`, payload),

  getMonitoringVisits: (studyId) => client.get(`/studies/${studyId}/monitoring-visits`),
  createMonitoringVisit: (studyId, payload) => client.post(`/studies/${studyId}/monitoring-visits`, payload),

  getStudySubjects: (studyId) => client.get(`/studies/${studyId}/subjects`),
  createStudySubject: (studyId, payload) => client.post(`/studies/${studyId}/subjects`, payload),
  updateStudySubject: (studyId, subjectId, payload) =>
    client.patch(`/studies/${studyId}/subjects/${subjectId}`, payload),
  // Priority 2: explicit AI Approved -> Eligible -> [Enroll Patient] -> Enrolled transition.
  enrollStudySubject: (studyId, subjectId, payload) =>
    client.post(`/studies/${studyId}/subjects/${subjectId}/enroll`, payload || {}),

  // ---------- Priority 3: Pharmacovigilance MVP ----------
  createAdverseEvent: (payload) => client.post("/safety/adverse-events", payload),
  getAdverseEvents: (params) => client.get("/safety/adverse-events", { params }),
  createSAE: (payload) => client.post("/safety/sae", payload),
  getSAEs: (params) => client.get("/safety/sae", { params }),
  getSafetyCase: (caseId) => client.get(`/safety/cases/${caseId}`),
  updateSafetyCaseStatus: (caseId, status) =>
    client.patch(`/safety/cases/${caseId}/status`, { status }),
  getSafetyDashboard: (studyId) =>
    client.get("/safety/dashboard", { params: studyId ? { study_id: studyId } : {} }),

  // ---------- Priority 3(b): Safety Signal Engine ----------
  detectSafetySignals: (payload) => client.post("/safety/signals/detect", payload),
  getSafetySignals: (params) => client.get("/safety/signals", { params }),
  getSafetySignal: (signalId) => client.get(`/safety/signals/${signalId}`),
  updateSafetySignalStatus: (signalId, status, reviewNotes) =>
    client.patch(`/safety/signals/${signalId}/status`, { status, review_notes: reviewNotes || undefined }),

  // ---------- Priority 5: RBAC ----------
  getRoles: () => client.get("/rbac/roles"),

  // ---------- Priority 7: FHIR + CDISC Demonstrator ----------
  listFhirResourceTypes: () => client.get("/interop/fhir"),
  getFhirBundle: (resourceType, studyId) =>
    client.get(`/interop/fhir/${resourceType}`, { params: studyId ? { study_id: studyId } : {} }),
  getMappingDoc: () => client.get("/interop/mapping"),
  listSdtmDomains: () => client.get("/export/sdtm"),
  // CSV download -- needs the raw response, not JSON, so it bypasses the
  // default axios json handling via responseType.
  downloadSdtm: (domain, studyId) =>
    client.get(`/export/sdtm/${domain}`, {
      params: studyId ? { study_id: studyId } : {},
      responseType: "blob",
    }),
};

export default api;