## Contributing to Bundlephobia Skill

Thanks for contributing.

This repository is primarily a skill + helper tooling repo, so high-signal docs and safe defaults matter as much as code changes.

### Development setup

1. Clone the repository.
2. Ensure Python 3.10+ is available.
3. Ensure Node.js/npm is available if validating package footprint commands.
4. (Optional) create and activate a virtual environment.

PowerShell example:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Local sanity checks

From repo root, run:

```powershell
python -m compileall ".github/skills/bundle-size-analysis/scripts"
python ".github/skills/bundle-size-analysis/scripts/bundle_size_analysis.py" --help
python ".github/skills/bundle-size-analysis/scripts/bundle_size_analysis.py" package react@18.2.0
```

If you touched command behavior, include example command invocations and expected output snippets in your PR description.

### Security requirements

- **Do not** commit secrets.
- **Do not** include private registry tokens in docs, logs, or screenshots.
- Treat private package names and package metadata as sensitive unless the owner says they are public.
- Prefer read-only examples and dry-run package commands.

### Commit messages

This repo includes commit message conventions in:

- `.github/copilot-commit-message-instructions.md`

### Pull request checklist

- [ ] Documentation updated (README/SKILL/help text as needed)
- [ ] Commands in docs are still valid
- [ ] No secrets or private package metadata in changes
- [ ] Sanity checks pass locally
- [ ] Scope is focused and reversible
