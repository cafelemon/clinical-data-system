from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.files import ensure_relative_path, safe_path_part
from app.models import SubjectSnapshot
from app.models.subject_snapshot import SUBJECT_SNAPSHOT_RELEASED

SUBJECT_SNAPSHOT_STATUS_RELEASED = "released"


@dataclass(frozen=True)
class SnapshotJsonExport:
    snapshot: SubjectSnapshot
    path: Path
    filename: str
    file_hash: str
    file_size: int


class SnapshotJsonNotFoundError(Exception):
    pass


class SnapshotJsonUnavailableError(Exception):
    pass


class SnapshotJsonIntegrityError(Exception):
    pass


def resolve_snapshot_json_export(
    db: Session,
    *,
    subject_id: int,
    snapshot_id: int,
) -> SnapshotJsonExport:
    snapshot = db.get(SubjectSnapshot, snapshot_id)
    if snapshot is None or snapshot.subject_id != subject_id:
        raise SnapshotJsonNotFoundError("snapshot not found")
    if snapshot.snapshot_type != SUBJECT_SNAPSHOT_RELEASED:
        raise SnapshotJsonUnavailableError("snapshot is not released")
    if snapshot.status != SUBJECT_SNAPSHOT_STATUS_RELEASED:
        raise SnapshotJsonUnavailableError("snapshot is not released")
    if not snapshot.storage_path or not snapshot.file_hash or snapshot.file_size is None:
        raise SnapshotJsonUnavailableError("snapshot json is incomplete")

    try:
        path = ensure_relative_path(settings.file_storage_root, snapshot.storage_path)
    except ValueError as exc:
        raise SnapshotJsonNotFoundError("snapshot json not found") from exc
    if not path.exists() or not path.is_file():
        raise SnapshotJsonNotFoundError("snapshot json not found")

    content = path.read_bytes()
    file_hash = hashlib.sha256(content).hexdigest()
    file_size = len(content)
    if file_hash != snapshot.file_hash or file_size != snapshot.file_size:
        raise SnapshotJsonIntegrityError("snapshot json integrity check failed")

    filename = (
        f"subject_snapshot_{safe_path_part(snapshot.screening_no_snapshot)}"
        f"_v{snapshot.snapshot_version}.json"
    )
    return SnapshotJsonExport(
        snapshot=snapshot,
        path=path,
        filename=filename,
        file_hash=file_hash,
        file_size=file_size,
    )
