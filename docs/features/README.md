# Features

> **Audience:** developers working on a flagship feature · **Scope:** index of feature documentation · **Last verified:** 2026-11-08

One page per flagship feature. Each states its scope and the date it was last checked against the code, links to the code, and lists
failure modes worth knowing.

| Feature | What it is | Page |
|---|---|---|
| **Grading pipeline** | Upload → segment → OCR → retrieve → rubric score → review → PDF | [`grading-pipeline.md`](grading-pipeline.md) |

Everything GRADE does hangs off this one pipeline; the portal pages are views onto its stages. The system view is
[`../architecture/overview.md`](../architecture/overview.md).
