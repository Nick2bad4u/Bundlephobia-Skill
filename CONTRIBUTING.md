## Contributing to SonarCloud Skill

Thanks for contributing.

This repository is primarily a skill + helper tooling repo, so high-signal docs and safe defaults matter as much as code changes.

### Development setup

1. Clone the repository.
2. Ensure Python 3.10+ is available.
3. (Optional) create and activate a virtual environment.

PowerShell example:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Local sanity checks

From repo root, run:

```powershell
python -m compileall ".github/skills/sonar-manage-findings/scripts"
python ".github/skills/sonar-manage-findings/scripts/manage_sonar_findings.py" --help
```

If you touched command behavior, include example command invocations and expected output snippets in your PR description.

### Security requirements

- **Do not** commit secrets.
- **Do not** pass Sonar tokens as CLI literals.
- Use environment variables (`SONAR_TOKEN` or `--token-env`).
- Prefer `--dry-run` for mutation commands in docs/examples.

### Commit messages

This repo includes commit message conventions in:

- `.github/copilot-commit-message-instructions.md`

### Pull request checklist

- [ ] Documentation updated (README/SKILL/help text as needed)
- [ ] Commands in docs are still valid
- [ ] No secrets or tokens in changes
- [ ] Sanity checks pass locally
- [ ] Scope is focused and reversible
