import js from "@eslint/js";
import globals from "globals";

export default [
  { ignores: ["artifacts/**", "build/**", "node_modules/**"] },
  js.configs.recommended,
  { files: ["scripts/*.mjs", "eslint.config.mjs"], languageOptions: { globals: globals.node } },
  {
    files: ["niri_fx/*.js"],
    languageOptions: { sourceType: "script", globals: { ...globals.browser } },
  },
  { files: ["niri_fx/studio.js"], languageOptions: { globals: { MotionPreview: "readonly" } } },
  {
    files: ["niri_fx/motion-preview.js"],
    rules: { "no-unused-vars": ["error", { varsIgnorePattern: "^MotionPreview$" }] },
  },
];
