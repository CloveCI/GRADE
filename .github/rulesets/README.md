# Repository rulesets

Exports of the rulesets to apply to this repository, kept so they can be reviewed and re-created. Once applied, the live source
of truth is Settings > Rules > Rulesets; compare after any change.

- `protect-main.json` ("Protect main"): the default branch. Merge commits only (promotions from staging). Required checks:
  `CI gate`, `Secret scan (gitleaks)`, `Conventional PR title`, and `Only staging can merge into main` (the promotion guard).
- `protect-staging.json` ("Protect staging"): `refs/heads/staging`. Squash only, linear history. Same checks minus the guard.

Create with: `gh api -X POST repos/Afeef-crypto/GRADE/rulesets --input .github/rulesets/protect-staging.json`
(use `-X PUT .../rulesets/<id>` to update an existing one). Bypass is the repository Admin role (`actor_id: 5`).
Rulesets on a private repository need GitHub Pro or Team.

Apply them only after the `staging` branch exists on GitHub and CI has run once, so GitHub knows the check names. With two
maintainers, "1 approval + code-owner review" means the other maintainer approves; CODEOWNERS lists both for `*`.
