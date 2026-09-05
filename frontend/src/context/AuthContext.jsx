import { createContext, useContext, useState } from "react";
import api from "../api/client.js";

const AuthContext = createContext(null);

const TOKEN_KEY = "trialmind_auth_token";
const USER_KEY = "trialmind_auth_user";
// Kept in sync so the existing RoleContext (and everything already built
// on useRole()) keeps working unchanged -- login is now what decides the
// role, instead of a free-standing dropdown.
const ROLE_KEY = "aiia_role";

function readStoredUser() {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() =>
    typeof window === "undefined" ? null : window.localStorage.getItem(TOKEN_KEY)
  );
  const [user, setUser] = useState(readStoredUser);

  const login = async (username, password) => {
    let res;
    try {
      res = await api.login(username, password);
    } catch (err) {
      // Login now returns a real 401 on bad credentials (see
      // routers/auth.py) instead of a 200 with an {error} body, so a
      // failed login surfaces here as a rejected request.
      const detail = err.response?.data?.detail;
      throw new Error(detail || "Login failed. Check your credentials.");
    }
    const { token: newToken, username: uname, display_name, role } = res.data;
    window.localStorage.setItem(TOKEN_KEY, newToken);
    window.localStorage.setItem(
      USER_KEY,
      JSON.stringify({ username: uname, display_name, role })
    );
    window.localStorage.setItem(ROLE_KEY, role);
    setToken(newToken);
    setUser({ username: uname, display_name, role });
    return { username: uname, display_name, role };
  };

  const logout = () => {
    api.logout().catch(() => {});
    window.localStorage.removeItem(TOKEN_KEY);
    window.localStorage.removeItem(USER_KEY);
    window.localStorage.removeItem(ROLE_KEY);
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{ token, user, isAuthenticated: !!token && !!user, login, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}

// Read synchronously (outside React), same pattern as getStoredRole(), so
// the axios client can attach the bearer token without needing to be
// inside the component tree.
export function getStoredToken() {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}
