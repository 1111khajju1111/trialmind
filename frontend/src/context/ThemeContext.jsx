import { createContext, useContext, useEffect } from "react";

const ThemeContext = createContext(null);

// Igloo-inspired demo direction (P0, CRITICAL REQUIREMENT): light theme is
// the only presentation mode for the demo. Dark mode's tokens/toggle stay
// in the codebase (design-system/index.css, ThemeToggle.jsx) for a future
// pass, but nothing in the demo path can select them anymore -- there is
// no stored preference and no system-preference branch to fall into dark.
const DEMO_THEME = "light";

export function ThemeProvider({ children }) {
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", DEMO_THEME);
  }, []);

  return (
    <ThemeContext.Provider value={{ theme: DEMO_THEME }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within a ThemeProvider");
  return ctx;
}
