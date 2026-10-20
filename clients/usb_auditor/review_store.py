"""Atomic review notes beside immutable raw scans; never a second scan report."""
import json
import os
from pathlib import Path
import tempfile

from session_model import validate_context


def review_path(report):
    report = Path(report)
    folder = report.parent.parent / 'reviews'
    if folder.is_symlink() or folder.is_junction():
        raise OSError('Review storage must not be a link')
    path = folder / (report.name + '.review')
    if path.is_symlink() or path.is_junction():
        raise OSError('Review file must not be a link')
    return path


def save_review(report, context):
    report = Path(report)
    if report.is_symlink() or not report.is_file():
        raise OSError('Original scan report is required')
    payload = validate_context(context)
    path = review_path(report)
    path.parent.mkdir(exist_ok=True)
    encoded = json.dumps(payload, ensure_ascii=False, indent=2).encode('utf-8')
    if len(encoded) > 16 * 1024 * 1024:
        raise ValueError('Review exceeds safe size limit')
    fd, name = tempfile.mkstemp(prefix='.review-', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(encoded); handle.flush(); os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)
    return path


def load_review(report):
    path = review_path(report)
    if not path.exists():
        return {}
    if path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError('Review exceeds safe size limit')
    return validate_context(json.loads(path.read_text('utf-8')))
