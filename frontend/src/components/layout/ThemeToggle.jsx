import { useTheme } from "../../context/ThemeContext.jsx";

export default function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === "dark";

  return (
    <button
      className="theme-toggle"
      onClick={toggleTheme}
      aria-label={`Switch to ${isDark ? "light" : "dark"} theme`}
      title={`Switch to ${isDark ? "light" : "dark"} theme`}
    >
      <span className={`theme-toggle-icon ${isDark ? "" : "is-active"}`}>☀️</span>
      <span className={`theme-toggle-icon ${isDark ? "is-active" : ""}`}>🌙</span>
    </button>
  );
}
