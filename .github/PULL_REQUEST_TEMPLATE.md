## Summary

<!-- What changed and why? -->

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] Documentation
- [ ] CI/workflow/configuration
- [ ] Refactor

## Changes included

-

## Validation

<!-- Include commands and outcomes. -->

```text
python -m compileall .github/skills/bundle-size-analysis/scripts
python .github/skills/bundle-size-analysis/scripts/bundle_size_analysis.py --help
python .github/skills/bundle-size-analysis/scripts/bundle_size_analysis.py package react@18.2.0
```

## Security / safety checklist

- [ ] No credentials/tokens committed
- [ ] Private package names or registry metadata are redacted where needed
- [ ] Docs updated to match behavior changes

## Related issues

Closes #
