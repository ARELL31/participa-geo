import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import tseslint from "typescript-eslint";

/**
 * Flat ESLint configuration for the Vite/React/TypeScript app.
 *
 * The project is browser-only; TypeScript already resolves global identifiers,
 * so `no-undef` is disabled for TS files (the typescript-eslint guidance).
 */
export default tseslint.config(
  {
    ignores: [
      "dist/**",
      "node_modules/**",
      "test-results/**",
      "playwright-report/**",
      "coverage/**",
      "src/lib/api.generated.ts",
    ],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["**/*.{ts,tsx}"],
    plugins: { "react-hooks": reactHooks },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "no-undef": "off",
      "@typescript-eslint/no-explicit-any": "warn",
    },
  },
  {
    files: ["vite.config.ts", "vitest.config.ts", "playwright.config.ts"],
    rules: {
      "react-hooks/rules-of-hooks": "off",
    },
  },
);
