# Security policy

## Reporting a vulnerability

Please do **not** open a public issue for a security problem.

Report it privately through the repository's **Security** tab (*Report a vulnerability*), or contact a maintainer
directly through the email on their GitHub profile. Include what you found, how to reproduce it, and what you think the
impact is. We will acknowledge within 3 working days and keep you updated until it is fixed.

## What is in scope

- **backend/**: the FastAPI service, file upload handling, PDF/DOCX parsing, database access, and the calls to OCR and LLM providers.
- **frontend/**: the React portal, including anything that could leak data or keys to the browser.
- This repository's workflows and git hooks.

Particularly interesting: path traversal or arbitrary file read/write through uploads or `/sheet/{id}/file`; malicious PDF or
DOCX input; SQL injection; prompt injection in a student answer that changes another question's score; and any way a provider
key (Google, Azure, Gemini, OpenRouter) or database credential could be exposed.

Known and accepted today: the API has **no authentication** and is meant to run on `127.0.0.1` only. Reports that depend on it
being exposed to the internet are still welcome, but the fix is "do not expose it" until auth exists.

## Handling secrets

- Never commit `.env` files, service-account JSON or keys. Only `*.example` files are tracked, and CI fails on anything else.
- Nothing prefixed `VITE_` may hold a secret: it is bundled into the browser.
- A secret scan (gitleaks) runs on every pull request and weekly over the full history. If you find a real secret in the
  history, report it as above so it can be rotated; do not just delete the file.

## Supported versions

Only `main` is supported.

## How the pipeline protects the repo

See [`docs/operations/ci-cd.md`](docs/operations/ci-cd.md): required CI gate, secret scanning, pinned actions and
least-privilege workflow tokens.
