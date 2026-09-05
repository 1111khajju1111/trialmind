import { createContext, useContext, useEffect, useState } from "react";

const RoleContext = createContext(null);
const STORAGE_KEY = "aiia_role";

// Priority 5 -- Role-Based Access + Audit.
// Login determines the role now (see AuthContext.jsx / app/auth.py):
// /auth/login resolves it server-side from the account that signed in and
// writes it here at login time. There is no free-standing role switcher
// anymore -- this context's setRole exists only for the login/logout flow
// to update it, not for arbitrary in-app role changes, and it no longer
// drives backend authorization by itself. Every request also carries the
// session's bearer token (see api/client.js), and the backend (app/rbac.py)
// resolves the authoritative role from that token, not from the
// X-User-Role header this context still populates -- that header is only
// a legacy/demo-mode fallback now. This context's role is UI-only: which
// nav items/actions to show, matching what the API will actually allow.
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
  const [role] = useState(getInitialRole);

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, role);
  }, [role]);

  const isReadOnly = READ_ONLY_ROLES.has(role);

  return (
    <RoleContext.Provider value={{ role, isReadOnly }}>
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
