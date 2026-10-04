import js from "@eslint/js";
import globals from "globals";

export default [
  { ignores: ["artifacts/**", "build/**", "node_modules/**"] },
  js.configs.recommended,
  {
    files: ["scripts/**/*.mjs", "tests/*.mjs", "eslint.config.mjs"],
    languageOptions: { globals: globals.node },
  },
  {
    files: ["niri_fx/*.js", "docs/gallery/*.js"],
    languageOptions: { sourceType: "script", globals: { ...globals.browser } },
  },
  {
    files: ["niri_fx/studio.js"],
    languageOptions: {
      globals: {
        MotionPreview: "readonly",
        createEffectCore: "readonly",
        createFxLibrary: "readonly",
      },
    },
  },
  {
    files: ["niri_fx/library.js"],
    languageOptions: { globals: { createEffectCore: "readonly" } },
    rules: { "no-unused-vars": ["error", { varsIgnorePattern: "^createFxLibrary$" }] },
  },
  {
    files: ["niri_fx/effect-core.js"],
    rules: { "no-unused-vars": ["error", { varsIgnorePattern: "^createEffectCore$" }] },
  },
  {
    files: ["niri_fx/motion-preview.js"],
    rules: { "no-unused-vars": ["error", { varsIgnorePattern: "^MotionPreview$" }] },
  },
];
