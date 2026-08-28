import { createContext, useContext, useEffect, useState } from "react";

const RoleContext = createContext(null);
const STORAGE_KEY = "aiia_role";

// Priority 5 -- Role-Based Access + Audit (thin, demo-appropriate RBAC).
// There is no login in this hackathon build: the coordinator picks their
// acting role here, it's persisted locally, and every API request carries
// it as the X-User-Role header (see api/client.js). The backend
// (app/rbac.py) is the actual enforcement point -- this context only
// drives which nav items/actions the UI offers, so the UI experience
// matches what the API will actually allow.
export const ROLES = [
  "Principal Investigator",
  "Study Coordinator",
  "Monitor",
  "Ethics Committee",
  "Pharmacovigilance",
  "Administrator",
  "Regulator",
];

export const READ_ONLY_ROLES = new Set(["Regulator"]);

const DEFAULT_ROLE = "Study Coordinator";

function getInitialRole() {
  if (typeof window === "undefined") return DEFAULT_ROLE;
  const stored = window.localStorage.getItem(STORAGE_KEY);
  return ROLES.includes(stored) ? stored : DEFAULT_ROLE;
}

export function RoleProvider({ children }) {
  const [role, setRole] = useState(getInitialRole);

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, role);
  }, [role]);

  const isReadOnly = READ_ONLY_ROLES.has(role);

  return (
    <RoleContext.Provider value={{ role, setRole, isReadOnly }}>
      {children}
    </RoleContext.Provider>
  );
}

export function useRole() {
  const ctx = useContext(RoleContext);
  if (!ctx) throw new Error("useRole must be used within a RoleProvider");
  return ctx;
}

// Read synchronously (outside React) so the axios client can attach the
// header without needing to be inside a component tree.
export function getStoredRole() {
  return getInitialRole();
}
