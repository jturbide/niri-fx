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
        createComboPreview: "readonly",
        createPointerSpring: "readonly",
        createPointerDemo: "readonly",
        POINTER_PREVIEW_SHADER: "readonly",
        createSessionSetup: "readonly",
        createFragmentPreviewControls: "readonly",
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
    files: ["niri_fx/fragment-controls.js"],
    languageOptions: {
      globals: {
        createFragmentMotion: "readonly",
        createFragmentRenderer: "readonly",
        createFragmentDemo: "readonly",
      },
    },
    rules: {
      "no-unused-vars": ["error", { varsIgnorePattern: "^createFragmentPreviewControls$" }],
    },
  },
  {
    files: ["niri_fx/session-setup.js"],
    rules: { "no-unused-vars": ["error", { varsIgnorePattern: "^createSessionSetup$" }] },
  },
  {
    files: ["niri_fx/combo-preview.js"],
    rules: { "no-unused-vars": ["error", { varsIgnorePattern: "^createComboPreview$" }] },
  },
  {
    files: ["niri_fx/motion-preview.js"],
    rules: { "no-unused-vars": ["error", { varsIgnorePattern: "^MotionPreview$" }] },
  },
];
