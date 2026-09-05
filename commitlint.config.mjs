// Shared commitlint config (ESM; the .mjs suffix makes Node treat it as a
// module without a package.json "type" field). Copy verbatim. The rules
// restate config-conventional's defaults so a preset change cannot widen
// them silently, plus `deps`: the prefix Dependabot uses when its bumps
// should appear in the release-please CHANGELOG (see release-setup).
export default {
  extends: ["@commitlint/config-conventional"],
  rules: {
    "header-max-length": [2, "always", 100],
    "type-enum": [
      2,
      "always",
      [
        "feat",
        "fix",
        "docs",
        "style",
        "refactor",
        "perf",
        "test",
        "build",
        "ci",
        "chore",
        "deps",
        "revert",
      ],
    ],
  },
};
