import { useState } from "react";
import { useAuth } from "../context/AuthContext.jsx";
import { IconMark } from "../design-system/icons.jsx";
import ThemeToggle from "../components/layout/ThemeToggle.jsx";

const DEMO_ACCOUNTS = [
  { username: "pi", role: "Principal Investigator" },
  { username: "coordinator", role: "Study Coordinator" },
  { username: "monitor", role: "Monitor" },
  { username: "ethics", role: "Ethics Committee" },
  { username: "pharmacovigilance", role: "Pharmacovigilance" },
  { username: "admin", role: "Administrator" },
  { username: "regulator", role: "Regulator (read-only)" },
];

export default function Login() {
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!username.trim() || !password) {
      setError("Enter a username and password.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await login(username.trim(), password);
    } catch (err) {
      setError(err.message || "Login failed. Check your credentials.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="login-shell">
      <div className="login-theme-toggle">
        <ThemeToggle />
      </div>
      <div className="login-card">
        <div className="login-brand">
          <span className="login-brand-icon"><IconMark /></span>
          <span className="login-brand-name">TRIAL<b>MIND</b></span>
        </div>
        <p className="login-subtitle">
          Sign in with your role account to access the platform.
        </p>

        {error && <div className="alert-box">{error}</div>}

        <form onSubmit={handleSubmit}>
          <label>Username</label>
          <input
            autoFocus
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="e.g. coordinator"
          />
          <label>Password</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
          />
          <button className="primary" type="submit" disabled={submitting} style={{ width: "100%", marginTop: 14 }}>
            {submitting ? "Signing in..." : "Sign In"}
          </button>
        </form>

        <div className="login-demo-accounts">
          <div className="login-demo-accounts-title">Demo accounts (password: trialmind123)</div>
          <ul>
            {DEMO_ACCOUNTS.map((a) => (
              <li key={a.username}>
                <code>{a.username}</code> — {a.role}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
