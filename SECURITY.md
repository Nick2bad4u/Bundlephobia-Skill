# Security Policy

## Supported scope

This repository contains an AI skill and helper scripts for npm package-size analysis.

Security-sensitive areas include:

- package metadata from private repositories
- npm registry credentials in local environments
- workflow automation that packages and publishes release assets
- any command output that includes private dependency names or internal artifact paths

## Reporting a vulnerability

If you discover a vulnerability, please avoid opening a public issue with exploit details.

Instead, contact the maintainer privately (for example via GitHub security reporting or direct private channel) and include:

1. affected file(s) / workflow(s)
2. reproducible steps
3. impact assessment
4. any suggested mitigation

## Secret handling rules

- Never hardcode npm tokens or registry credentials.
- Never include private tokens in command arguments, logs, screenshots, or issue bodies.
- Prefer environment variables or npm's configured auth store for private registries.
- Redact private package names when sharing output publicly unless disclosure is intentional.

## Operational safety

- Prefer read-only checks: Bundlephobia API queries, `npm pack --dry-run --json`, and local artifact measurement.
- Verify the target repo and package name before publishing or sharing package-size output.
- Keep generated archives and reports out of commits unless they are intentional release assets.
