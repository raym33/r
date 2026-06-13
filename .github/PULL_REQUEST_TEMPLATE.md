## Problem
What problem does this pull request solve?

## Solution
Describe the implementation and its user-visible behavior.

## Type of Change
- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change
- [ ] Documentation update
- [ ] Refactor
- [ ] New skill

## Related Issues
Fixes #(issue number)

## Security Impact
Describe affected trust boundaries, permissions, filesystem access, network access, secret
handling, or execution capabilities. Write `None` only when the change has no security
impact.

## Verification
List the commands and manual checks you ran.

```text
pytest -q
ruff check r_cli/ r_os/ tests/
ruff format --check r_cli/ r_os/ tests/
```

## Checklist
- [ ] Tests cover new or changed behavior.
- [ ] Denied and failure paths are tested where relevant.
- [ ] Documentation is updated and written in English.
- [ ] No secret, private prompt, personal file, or unredacted audit data is included.
- [ ] New capabilities are narrow, explicit, and deny by default.
- [ ] Breaking changes and migrations are documented.

## Platform Notes
List the operating systems and local model runtimes tested.

## Screenshots
Add screenshots only for user-interface changes.
