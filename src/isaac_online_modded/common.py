"""Shared patch model, status helpers and filesystem utilities."""

from __future__ import annotations

import enum
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

DEFAULT_BACKUP_SUFFIX = ".bak"


class PatchError(RuntimeError):
    """Raised when a patch cannot be applied to the current files."""


class ModNotFoundError(PatchError):
    """Raised when an optional mod directory is not installed."""


class EIDNotFoundError(ModNotFoundError):
    pass


class AntibirthMusicNotFoundError(ModNotFoundError):
    pass


class PatchStatus(enum.Enum):
    NOT_PATCHED = "not patched"
    PARTIALLY_PATCHED = "partially patched"
    PATCHED = "patched"
    UNSUPPORTED = "unsupported"


STATUS_LABELS = {
    PatchStatus.PATCHED: "patched",
    PatchStatus.NOT_PATCHED: "not patched",
    PatchStatus.PARTIALLY_PATCHED: "partially patched",
    PatchStatus.UNSUPPORTED: "unsupported",
}


@dataclass(frozen=True)
class BinaryPatch:
    """An equal-length original/patched byte region inside a file."""

    name: str
    original: bytes
    patched: bytes

    def __post_init__(self) -> None:
        if len(self.original) != len(self.patched):
            raise ValueError(
                f"Patch {self.name!r} must have equal-length original and patched bytes"
            )


def eprint(*args: object) -> None:
    print(*args, file=sys.stderr)


def write_file_atomic(path: Path, data: bytes) -> None:
    """Write bytes through a temporary file so a failed run cannot truncate."""

    mode = path.stat().st_mode & 0o7777 if path.exists() else 0o644
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def backup_once(path: Path, suffix: str, dry_run: bool) -> Path:
    if not suffix:
        raise PatchError("Backup suffix must not be empty")

    backup_path = path.with_name(path.name + suffix)
    if backup_path.exists():
        print(f"Using existing backup: {backup_path}")
        return backup_path

    if dry_run:
        print(f"Would create backup: {backup_path}")
    else:
        shutil.copy2(path, backup_path)
        print(f"Created backup: {backup_path}")

    return backup_path


def restore_backup(path: Path, suffix: str, dry_run: bool) -> None:
    backup_path = path.with_name(path.name + suffix)
    if not backup_path.exists():
        raise PatchError(f"Backup not found: {backup_path}")

    if dry_run:
        print(f"Would restore {path} from {backup_path}")
        return

    shutil.copy2(backup_path, path)
    print(f"Restored: {path}")


def binary_patch_status(body: bytes | bytearray, patch: BinaryPatch) -> PatchStatus:
    original_count = body.count(patch.original)
    patched_count = body.count(patch.patched)
    if original_count == 0 and patched_count == 1:
        return PatchStatus.PATCHED
    if original_count == 1 and patched_count == 0:
        return PatchStatus.NOT_PATCHED
    return PatchStatus.UNSUPPORTED


def grouped_patch_status(
    body: bytes | bytearray, patches: Iterable[BinaryPatch]
) -> PatchStatus:
    statuses = [binary_patch_status(body, patch) for patch in patches]
    if all(status is PatchStatus.PATCHED for status in statuses):
        return PatchStatus.PATCHED
    if all(status is PatchStatus.NOT_PATCHED for status in statuses):
        return PatchStatus.NOT_PATCHED
    return PatchStatus.UNSUPPORTED


def combine_status(*statuses: PatchStatus) -> PatchStatus:
    if any(status is PatchStatus.UNSUPPORTED for status in statuses):
        return PatchStatus.UNSUPPORTED
    if all(status is PatchStatus.PATCHED for status in statuses):
        return PatchStatus.PATCHED
    return PatchStatus.NOT_PATCHED


def apply_binary_patch(body: bytearray, patch: BinaryPatch) -> bool:
    status = binary_patch_status(body, patch)
    if status is PatchStatus.PATCHED:
        index = body.find(patch.patched)
        print(f"Already patched: {patch.name} at offset 0x{index:x}")
        return False
    if status is not PatchStatus.NOT_PATCHED:
        raise PatchError(
            f"Pattern for {patch.name!r} is missing or ambiguous. "
            "The game may have updated and this patcher may be outdated."
        )

    index = body.find(patch.original)
    body[index : index + len(patch.patched)] = patch.patched
    print(f"Will patch {patch.name} at offset 0x{index:x}")
    return True
