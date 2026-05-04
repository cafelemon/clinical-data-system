# P4 File Upload Acceptance

P4 turns the P3 clinical dataset registry into a file-backed collection loop.

## Backend

- Added `files` and `file_versions` tables.
- Files must bind to exactly one `stage_file_id` or `subject_item_id`.
- The backend derives project, center, stage, subject, and scope from the binding record.
- Uploaded files are stored under `FILE_STORAGE_ROOT` with UUID stored names and relative paths.
- SHA256 hash, MIME type, file size, category, current version, uploader, and status are recorded.
- `GET /api/files/{id}/preview` supports PDF and images only; Office, Excel, CSV, JSON, and video use download.
- `DELETE /api/files/{id}` performs hard delete of database records and physical version files.

## Status Sync

- Upload and replace set the bound `stage_files` or `subject_items` row to:
  - `upload_status=uploaded`
  - `review_status=pending_review`
- Subject item changes recalculate the parent subject data status.
- Deleting the last file bound to a row resets it to:
  - `upload_status=not_uploaded`
  - `review_status=pending_review`

## Permissions

- Added `files:read`, `files:write`, and `files:delete`.
- Admin has all file permissions.
- Project manager has read, write, and delete.
- Center manager and clinical coordinator have read and write.
- Reviewer, RD user, and readonly roles have read only.
- All file operations enforce P2 project/center data scopes.

## Frontend

- Stage file rows in `/clinical-dataset` support upload, download, PDF/image preview, replace, version list, and delete.
- Subject item rows in `/clinical-dataset/subjects/:subjectId` support the same file operations.
- Readonly users can only download or preview authorized files.
- Delete actions require browser confirmation.

## Verification

- Backend: `ruff check`, `pytest`, `alembic upgrade head`, and `alembic check`.
- Frontend: `npm run lint` and `npm run build`.
- API coverage includes upload, download, preview, replace/versioning, hard delete, status sync, permissions, scope denial, oversized files, and invalid bindings.
