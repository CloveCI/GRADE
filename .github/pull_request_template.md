> Base branch: **`staging`** for normal work. Only the `staging` → `main` promotion PR targets `main`.

## What and why
<!-- One or two sentences. The reviewer should not need to read the diff to know the intent. -->

## Type
<!-- feat | fix | refactor | perf | test | docs | ci | build | chore. The PR title must follow: type(scope): summary -->

## How it was tested
<!-- Commands you ran and what you saw (pytest, npm run build, a sheet you graded). "CI is green" is the floor, not the answer. -->

## Impact
<!-- Nothing deploys automatically; say what someone running main has to do after pulling. -->
- [ ] No schema change
- [ ] Schema change: added to `db.py` (`init_db`) **and** a new file in `backend/supabase/migrations/`
- [ ] New or changed environment variable, documented in `backend/.env.example` / `frontend/.env.example`:
- [ ] Grading behaviour changed (prompt, rubric, layout, OCR tiers): cached results need `force_regrade`
- [ ] Segmentation or automatic layout changed: checked on the CIE samples in `backend/cie/`

## Checklist
- [ ] No secrets, `.env` files, service-account JSON, build output or large binaries added
- [ ] Docs updated if behaviour or setup changed
