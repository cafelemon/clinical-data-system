# P3 Clinical Dataset Acceptance

P3 completes the clinical dataset core path on top of P2 authentication and scopes:

```text
project -> center -> stage files / subjects -> subject detail -> item status
```

## Backend

- Added PostgreSQL-backed `subjects`, `subject_sections`, `subject_items`, and `stage_files`.
- Added `clinical_data:write`; admin, project manager, center manager, and clinical coordinator can write clinical dataset records.
- `GET /api/stage-files` idempotently materializes rows from `stage_templates` by project, center, and stage.
- `POST /api/subjects` creates the subject and automatically creates 6 subject sections plus built-in subject items.
- All P3 APIs require login and apply P2 project/center scope filtering.

## Subject Sections

1. `SCREENING` - 筛选阶段
2. `ENROLLMENT_PREP` - 入组与检查准备阶段
3. `EXAM_EXECUTION` - 检查执行阶段
4. `EARLY_FOLLOWUP` - 检查后早期随访阶段
5. `DELAYED_FOLLOWUP` - 异常或延迟随访阶段
6. `COMPLETION` - 试验完成阶段

## Frontend

- `/clinical-dataset` is now a working project/center clinical dataset page.
- Startup and closeout sections display materialized stage files from PostgreSQL.
- Trial section displays subjects and supports create/edit for users with `clinical_data:write`.
- `/clinical-dataset/subjects/:subjectId` displays 6 sections and subject items, with status editing for write users.
- Read-only users can view records but do not see create/edit/status update controls.

## Verification

- Backend: `pytest`, `ruff check`, `alembic upgrade head`, and `alembic check`.
- Frontend: `npm run lint` and `npm run build`.
- API scenarios: unauthenticated access returns `401`, read-only writes return `403`, duplicate screening numbers return `409`, and scoped users only see authorized project/center data.
