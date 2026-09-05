// Priority 5 -- RBAC (thin, demo-appropriate). `roles: null` means visible
// to everyone; otherwise the item is only shown to those roles (plus
// Administrator, which always sees everything -- see TopNavigation.jsx).
// This only controls what's convenient to click; the backend (app/rbac.py)
// is the actual enforcement boundary, not this list.
//
// `icon` names resolve against the single icon family in
// ../../design-system/icons.jsx (see ICONS map) -- no emoji here.
// TrialMind's screening console (protocols, matching runs, candidate
// review, outreach) is now part of the single Dashboard page rather than
// its own nav item -- see pages/Dashboard.jsx.
export const NAV_ITEMS = [
  { to: "/", label: "Dashboard", icon: "dashboard", end: true, roles: null },
  { to: "/studies", label: "Studies", icon: "studies", roles: null },
  { to: "/patients", label: "Patients", icon: "patients", roles: ["Principal Investigator", "Study Coordinator", "Monitor"] },
  { to: "/safety", label: "Safety", icon: "safety", roles: ["Pharmacovigilance", "Principal Investigator", "Study Coordinator"] },
  { to: "/compliance", label: "Compliance", icon: "compliance", roles: ["Ethics Committee", "Study Coordinator", "Regulator"] },
  { to: "/regulatory", label: "Reg. Drafting", icon: "regulatory", roles: ["Study Coordinator", "Ethics Committee"] },
  { to: "/lab-scheduling", label: "Lab", icon: "lab", roles: ["Study Coordinator", "Monitor"] },
  { to: "/interop", label: "Interoperability", icon: "interop", roles: null },
  { to: "/audit", label: "Audit", icon: "audit", roles: null },
];
