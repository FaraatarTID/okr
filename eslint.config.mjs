// Flat ESLint config for the two JavaScript workspaces.
//
// Scope: the typed rule block and the `lint` script both target the two `src`
// trees, so `npm run lint` covers exactly what was measured. Generated API
// clients are ignored because they are machine-written.
//
// The rule levels are measured rather than guessed; the evidence is in the C4
// rows of docs/REMAINING_ENGINEERING_PLAN.md. `no-explicit-any` is an error
// because the tree has zero violations, so enforcing it costs nothing.
// `no-unused-vars` (19) and `exhaustive-deps` (18) start as warnings because
// they carry real existing debt that this change deliberately does not clear.
import js from "@eslint/js";
import tseslint from "typescript-eslint";
import reactHooks from "eslint-plugin-react-hooks";

const SOURCE = [
  "spa-web/src/**/*.ts",
  "spa-web/src/**/*.tsx",
  "spa-bff/src/**/*.ts",
];

export default [
  {
    ignores: [
      "**/node_modules/**",
      "**/.next/**",
      "**/dist/**",
      "**/coverage/**",
      "spa-web/src/lib/api/generated/**",
      "spa-bff/src/generated/**",
    ],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: SOURCE,
    plugins: { "react-hooks": reactHooks },
    languageOptions: {
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
    rules: {
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/no-floating-promises": "error",
      "@typescript-eslint/no-unused-vars": "warn",
      "react-hooks/exhaustive-deps": "warn",
    },
  },
  {
    // TypeScript already resolves identifiers; the base rule only produces
    // false positives on type positions and ambient globals.
    files: SOURCE,
    rules: { "no-undef": "off" },
  },
];
