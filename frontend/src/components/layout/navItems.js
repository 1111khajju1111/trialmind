// Priority 5 -- RBAC (thin, demo-appropriate). `roles: null` means visible
// to everyone; otherwise the item is only shown to those roles (plus
// Administrator, which always sees everything -- see TopNavigation.jsx).
// This only controls what's convenient to click; the backend (app/rbac.py)
// is the actual enforcement boundary, not this list.
export const NAV_ITEMS = [
  { to: "/", label: "Dashboard", icon: "\u{1F4CA}", end: true, roles: null },
  { to: "/studies", label: "Studies", icon: "\u{1F3E5}", roles: null },
  { to: "/trialmind", label: "Trial Matching", icon: "\u{1F9EC}", roles: ["Principal Investigator", "Study Coordinator"] },
  { to: "/patients", label: "Patients", icon: "\u{1F465}", roles: ["Principal Investigator", "Study Coordinator", "Monitor"] },
  { to: "/safety", label: "Safety", icon: "\u{1FA79}", roles: ["Pharmacovigilance", "Principal Investigator", "Study Coordinator"] },
  { to: "/compliance", label: "Compliance", icon: "\u2696\uFE0F", roles: ["Ethics Committee", "Study Coordinator", "Regulator"] },
  { to: "/regulatory", label: "Reg. Drafting", icon: "\u{1F4CB}", roles: ["Study Coordinator", "Ethics Committee"] },
  { to: "/lab-scheduling", label: "Lab", icon: "\u{1F9EA}", roles: ["Study Coordinator", "Monitor"] },
  { to: "/interop", label: "Interoperability", icon: "\u{1F517}", roles: null },
  { to: "/audit", label: "Audit", icon: "\u{1F9ED}", roles: null },
];
