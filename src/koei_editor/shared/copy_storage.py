"""Immutable copy tools. No operation here overwrites an existing file."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import uuid
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.save_safety import safe_path


def atomic_new(data, destination):
    destination = safe_path(destination)
    if destination.exists():
        raise FileExistsError('Choose a new file; existing files are never replaced.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name('.' + destination.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('xb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if temporary.read_bytes() != data:
            raise SaveError('Temporary copy verification failed.')
        if os.name == 'nt':
            os.rename(temporary, destination)
        else:
            os.link(temporary, destination)
            temporary.unlink()
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def snapshot_backup(raw, source, game_id, folder=None):
    source = safe_path(source)
    folder = safe_path(folder if folder is not None else source.parent / 'OriginsEditorBackups')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    separator = '.' if source.suffix else '-'
    destination = folder / (source.stem + separator + stamp + separator + uuid.uuid4().hex[:8] + source.suffix)
    manifest = {'game_id': game_id, 'sha256': hashlib.sha256(raw).hexdigest(), 'size_bytes': len(raw),
                'kind': 'opaque-copy', 'created_utc': stamp}
    result = atomic_new(raw, destination)
    # If manifest creation fails, keep the completed snapshot. Another app may
    # have replaced either path; failure must never delete its bytes. Restore
    # still requires a matching manifest before accepting this backup.
    atomic_new(json.dumps(manifest, indent=2).encode('utf-8'), destination.with_suffix('.json'))
    return result


def restore_snapshot(backup, destination, game_id, suffix, max_size, validate_raw=None):
    backup, destination = safe_path(backup), safe_path(destination)
    if backup.suffix.lower() != suffix or destination.suffix.lower() != suffix:
        raise SaveError(f'Choose a {suffix} backup and a new {suffix} destination.')
    manifest_path = safe_path(backup.with_suffix('.json'))
    with manifest_path.open('rb') as stream:
        metadata = stream.read(4097)
    with backup.open('rb') as stream:
        raw = stream.read(max_size + 1)
    if len(metadata) > 4096 or not 0 < len(raw) <= max_size:
        raise SaveError('Backup or manifest size is invalid.')
    try:
        manifest = json.loads(metadata)
    except (ValueError, UnicodeError) as error:
        raise SaveError('Backup manifest is damaged.') from error
    if (not isinstance(manifest, dict) or manifest.get('game_id') != game_id or
            manifest.get('kind') != 'opaque-copy' or manifest.get('size_bytes') != len(raw) or
            manifest.get('sha256') != hashlib.sha256(raw).hexdigest()):
        raise SaveError('Backup game, hash, or size does not match its manifest.')
    if validate_raw is not None:
        # Qualify the same bounded bytes that will be written, rather than a
        # separate earlier read whose backup or manifest could change.
        validate_raw(raw)
    return atomic_new(raw, destination)
