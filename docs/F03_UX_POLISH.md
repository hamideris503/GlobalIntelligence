# F03.UX.7 — Verification-gate polish

**Stage:** `F03.UX.7`
**Status:** `VERIFIED` for the scope implemented. **Scope note:** the stage text in
`GlobalIntelligence_v1.5_Delta_Engineering_Spec.md` is not present in this repository, so this stage
was limited to defects that are provable from the repo itself and need no product decision: the
frontend lint gate was red for the whole app. Only that was changed.

---

## 1. Before (evidence)

```
$ cd apps/web && npm run lint
   43:9   error  'src' is assigned a value but never used       @typescript-eslint/no-unused-vars
  164:9   error  'src' is assigned a value but never used
  188:9   error  'src' is assigned a value but never used
  462:80  error  'request' is defined but never used
  463:9   error  'headers' is assigned a value but never used
  663:9   error  'summary' is assigned a value but never used
✖ 6 problems (6 errors, 0 warnings)   exit 1
```

`package.json` runs eslint over the whole app, so one test file made the repository-wide gate fail —
every later stage inherits a red baseline.

## 2. What changed

`apps/web/e2e/pg-fullstack.spec.ts` only:

| Line | Before | After |
|---|---|---|
| 43, 164, 188 | `const src = await srcRes.json();` (never read) | `expect((await srcRes.json()).id).toBeTruthy();` |
| 462 | `async ({ page, request })` (request unused) | `async ({ page })` |
| 463 | `const headers = {...}` (unused after sign-in moved to the UI) | removed |
| 663 | `const summary = await dedupRes.json();` (never asserted) | `expect((await dedupRes.json()).documents).toBeGreaterThanOrEqual(2);` |

No rule was disabled, no `eslint-disable` comment was added, and no assertion was removed. Four of
the six sites now assert the value they already fetched, so the tests are slightly stronger than
before rather than weaker. The created-source id assertion also documents what the request is for.

## 3. Verification

```
$ npx eslint e2e/pg-fullstack.spec.ts     # exit 0, no output
$ npm run lint                            # exit 0 — 16 problems (0 errors, 16 warnings)
$ npm run typecheck                       # exit 0
```

The 16 remaining warnings are the pre-existing `react-refresh/only-export-components` notices on
`ui.tsx` (files that export both components and helpers); they are warnings, not errors, and were
present before this stage.

## 4. Constraints respected

- No commit, no push, no file deletion, no dependency install, no migration.
- The file is a test spec; no runtime code, API contract or UI behaviour changed, so no new
  browser/baseline run was required. The e2e suite itself needs a live PostgreSQL backend on
  `127.0.0.1:8020`, which is not part of this local dev stack — it was therefore linted and
  type-checked, not executed.

## 5. Known gaps

| Severity | Gap |
|---|---|
| `MEDIUM` | Without the delta spec text, the rest of `F03.UX.7` is unknown; the remaining UX backlog items (`UX-01`, `UX-06`, `UX-13`, `UX-19`, `UX-21`) depend on `F03.0` control-plane work or on an explicit dependency approval |
| `LOW` | `npx playwright test --list` does not expand a bare filename argument in this setup, so parse-level verification came from `tsc`/eslint rather than a Playwright collection run |

**Next stage:** `F03.0` (Control Plane backend) — descriptor contract, revisions, validate/test/preview
and audit — then `F12.1.1`.
