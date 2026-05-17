# Security Policy

## Supported scope

This repository contains automation and helper scripts for SonarCloud/SonarQube project triage.

Security-sensitive areas include:

- credential/token handling
- API mutation commands (`transition-issue`, `review-hotspot`, settings/profile/gate mutations)
- workflow automation that can post comments or update repository state

## Reporting a vulnerability

If you discover a vulnerability, please avoid opening a public issue with exploit details.

Instead, contact the maintainer privately (for example via GitHub security reporting or direct private channel) and include:

1. affected file(s) / workflow(s)
2. reproducible steps
3. impact assessment
4. any suggested mitigation

## Secret handling rules

- Never hardcode Sonar tokens.
- Never include tokens in command arguments.
- Use environment variables (e.g. `SONAR_TOKEN`).
- Prefer secret manager retrieval into environment variables.

PowerShell example:

```powershell
$env:SONAR_TOKEN = Get-Secret SONAR_TOKEN_TYPEFEST -AsPlainText
```

## Operational safety

- Use `--dry-run` for mutation commands before applying changes.
- Verify target project key/base URL before running mutations.
- Re-check state after changes (`summary`, issue/hotspot detail commands).
