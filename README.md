# Bundlephobia Skill

[![latest GitHub release.](https://flat.badgen.net/github/release/Nick2bad4u/Bundlephobia-Skill?color=cyan)](https://github.com/Nick2bad4u/Bundlephobia-Skill/releases) [![GitHub stars.](https://flat.badgen.net/github/stars/Nick2bad4u/Bundlephobia-Skill?color=yellow)](https://github.com/Nick2bad4u/Bundlephobia-Skill/stargazers) [![GitHub forks.](https://flat.badgen.net/github/forks/Nick2bad4u/Bundlephobia-Skill?color=green)](https://github.com/Nick2bad4u/Bundlephobia-Skill/forks) [![GitHub open issues.](https://flat.badgen.net/github/open-issues/Nick2bad4u/Bundlephobia-Skill?color=red)](https://github.com/Nick2bad4u/Bundlephobia-Skill/issues) [![GitHub PRs.](https://flat.badgen.net/github/open-prs/Nick2bad4u/Bundlephobia-Skill?color=orange)](https://github.com/Nick2bad4u/Bundlephobia-Skill/pulls?q=sort%3Aupdated-desc+is%3Apr+is%3Aopen) [![GitHub license](https://flat.badgen.net/github/license/Nick2bad4u/Bundlephobia-Skill?color=purple)](https://github.com/Nick2bad4u/Bundlephobia-Skill/blob/main/LICENSE) [![GitHub Dependabot](https://flat.badgen.net/github/dependabot/Nick2bad4u/Bundlephobia-Skill?color=blue)](https://github.com/Nick2bad4u/Bundlephobia-Skill/network/updates)

A Copilot / AI skill for inspecting npm package bundle cost with **Bundlephobia** and related package-size checks.

This repository provides:

- a reusable `bundle-size-analysis` skill (`.github/skills/bundle-size-analysis/SKILL.md`)
- a Python CLI helper for Bundlephobia package queries, package.json scans, npm publish footprint checks, and local artifact gzip checks
- GitHub automation for packaging the skill bundle

---

## What this skill can do

Using live package-size services and local package data, you can:

- submit npm packages to Bundlephobia's API and collect minified/gzipped cost
- scan a `package.json` dependency list the same way Bundlephobia's site scan works
- inspect Bundlephobia exports, dependency composition, history, and similar packages
- check local publish footprint with `npm pack --json --dry-run`
- measure built JS/CSS artifact sizes and gzip sizes
- run threshold checks for package, pack, and artifact budgets
- choose the right evidence source for bundle size, install footprint, publish footprint, or actual app bundle analysis

---

## Repository layout

```text
.github/
  skills/
    bundle-size-analysis/
      SKILL.md
      agents/
        openai.yaml
      references/
        check-selection.md
      scripts/
        bundle_size_analysis.py
README.md
CONTRIBUTING.md
SECURITY.md
CHANGELOG.md
```

---

## Quick start

### 1. Prerequisites

- Python 3.10+
- Node.js/npm when using `pack` or local package checks
- Network access when querying Bundlephobia

### 2. Query package sizes

From repository root:

```powershell
python ".github/skills/bundle-size-analysis/scripts/bundle_size_analysis.py" package react@18.2.0 lodash@4.17.21
```

Fetch deeper Bundlephobia data:

```powershell
python ".github/skills/bundle-size-analysis/scripts/bundle_size_analysis.py" package react@18.2.0 --exports --dependencies --history 10 --similar
```

Machine-readable output:

```powershell
python ".github/skills/bundle-size-analysis/scripts/bundle_size_analysis.py" package react@18.2.0 --json
```

---

## Common commands

```powershell
# Scan runtime dependencies from package.json
python ".github/skills/bundle-size-analysis/scripts/bundle_size_analysis.py" scan --package-json package.json

# Include dev and optional dependencies in a package.json scan
python ".github/skills/bundle-size-analysis/scripts/bundle_size_analysis.py" scan --package-json package.json --include-dev --include-optional

# Check npm publish footprint
python ".github/skills/bundle-size-analysis/scripts/bundle_size_analysis.py" pack --repo .

# Measure local build artifacts
python ".github/skills/bundle-size-analysis/scripts/bundle_size_analysis.py" artifacts dist build

# Run the combined audit
python ".github/skills/bundle-size-analysis/scripts/bundle_size_analysis.py" audit --repo .

# Fail when any queried package exceeds a gzip budget
python ".github/skills/bundle-size-analysis/scripts/bundle_size_analysis.py" scan --package-json package.json --max-gzip-kb 50
```

For the full command surface and workflow guidance, see:

- `.github/skills/bundle-size-analysis/SKILL.md`

---

## Security notes

- Do not commit private package metadata, registry tokens, or generated output that exposes secrets.
- The helper does not require Bundlephobia credentials.
- `npm pack --dry-run` is read-only, but review output before sharing it publicly for private packages.

More details: [`SECURITY.md`](./SECURITY.md)

---

## Contributing

Contributions are welcome. Please read:

- [`CONTRIBUTING.md`](./CONTRIBUTING.md)
- [`CHANGELOG.md`](./CHANGELOG.md)

---

## Releases and downloads

This repository includes a release workflow that creates a downloadable zip bundle:

- Workflow: `.github/workflows/release-skill.yml`
- Trigger:
  - push a tag like `v0.1.0`
  - run manually via **workflow_dispatch** with:
    - `release_type`: `patch` / `minor` / `major`
    - `version`: optional explicit `x.y.z` (overrides `release_type`)
    - `ref`: branch to release from (default `main`)
- Asset: `bundlephobia-skill-<tag>.zip`

Examples:

```powershell
# Manual patch bump from main
gh workflow run "Release Skill Bundle" -f release_type=patch -f ref=main

# Manual explicit release version
gh workflow run "Release Skill Bundle" -f release_type=patch -f version=0.2.0 -f ref=main
```

---

## License

Released under [The Unlicense](./LICENSE).
