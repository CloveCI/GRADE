# 0001: `staging` is the integration branch; `main` is protected and promotion-only

- **Status:** Accepted
- **Date:** 2026-11-08

## Context
Two people commit to GRADE, and work landed directly on `main` (plus side branches `master` and `newfront`). `main` is what
gets demoed and handed in, so a half-finished change on it is visible immediately, and nothing was integrated with the other
person's work before it reached `main`.

## Decision
- Feature branches start from `staging` and open PRs against `staging` (squash merge; the conventional PR title becomes the commit).
- `main` accepts only a PR from `staging` (merge commit), enforced by the `Only staging can merge into main` check.
- Both branches are protected by rulesets exported in `.github/rulesets/`: PR, one approval, required checks, no force-push or deletion.
  Only a repository admin can bypass them.

## Consequences
- A hotfix takes the same path (`fix/...` → `staging` → `main`); an admin can bypass in a genuine emergency.
- `staging` and `main` keep the same history, because promotions are merge commits.
- `master` and `newfront` are older lines of work; merge what is still wanted into `staging` through a PR, then delete them.
