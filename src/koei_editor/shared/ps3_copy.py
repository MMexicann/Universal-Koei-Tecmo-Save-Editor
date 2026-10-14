"""Copy storage for adapters binding the entire original PS3 metadata snapshot."""
import hashlib
import json
from pathlib import Path

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.copy_storage import atomic_new, snapshot_backup, restore_snapshot
from koei_editor.shared.save_safety import safe_path


class PS3CopyStorage:
    def __init__(self, game_id, size, validate_document, context_raw, decode, read_save, serialize):
        self.game_id, self.size = game_id, size
        self.validate_document, self.context_raw = validate_document, context_raw
        self.decode, self.read_save, self.serialize = decode, read_save, serialize

    def check_context(self, document, destination=None):
        self.validate_document(document)
        raw = self.context_raw(document.source)
        if not document.context_digest or hashlib.sha256(raw).hexdigest() != document.context_digest:
            raise SaveError('The original PS3 metadata changed. Reopen the copied export.')
        if destination is not None and self.context_raw(destination) != raw:
            raise SaveError('Keep the exact original PARAM.SFO beside the new destination.')
        return raw

    def check_source(self, document):
        self.check_context(document)
        source = safe_path(document.source)
        with source.open('rb') as stream:
            if stream.read(self.size + 1) != document.raw:
                raise SaveError('The opened PS3 copy changed. Reopen before saving or backing up.')
        return source

    def prepare_copy_context(self, document, output_dir):
        self.check_source(document)
        metadata = self.check_context(document)
        return atomic_new(metadata, safe_path(Path(output_dir) / 'PARAM.SFO'))

    def prepare_self_test_copy(self, document, destination):
        self.check_source(document)
        self.check_context(document, destination)

    def backup(self, document):
        source = self.check_source(document)
        result = snapshot_backup(document.raw, source, self.game_id, source.parent / 'UniversalEditorBackups')
        metadata = {'game_id': self.game_id, 'kind': 'ps3-export-context',
                    'context_sha256': document.context_digest, 'save_sha256': document.sha256}
        try:
            atomic_new(json.dumps(metadata).encode('utf-8'), result.with_name(result.name + '.context.json'))
            self.check_source(document)
        except Exception:
            result.unlink(missing_ok=True)
            result.with_suffix('.json').unlink(missing_ok=True)
            result.with_name(result.name + '.context.json').unlink(missing_ok=True)
            raise
        return result

    def save_as(self, document, changes, destination):
        destination = safe_path(destination)
        if destination.suffix.lower() != '.bin':
            raise SaveError('Choose a new decrypted PS3 .bin destination.')
        if destination.exists():
            raise FileExistsError('Choose a new file; existing copies are never replaced.')
        self.check_context(document, destination)
        self.check_source(document)
        raw = self.serialize(document, changes)
        self.backup(document)
        self.check_context(document, destination)
        self.check_source(document)
        atomic_new(raw, destination)
        actual = self.read_save(destination, self.game_id)
        self.check_source(document)
        self.check_context(document, destination)
        if actual.raw != raw or actual.context_digest != document.context_digest:
            raise SaveError('The saved PS3 copy or original metadata changed during read-back.')
        return actual

    def restore(self, backup_path, destination, game_id=None):
        if game_id is not None and game_id != self.game_id:
            raise SaveError('Select the exact PS3 backup game profile.')
        backup_path, destination = safe_path(backup_path), safe_path(destination)
        metadata = self.context_raw(destination)
        digest = hashlib.sha256(metadata).hexdigest()
        path = safe_path(backup_path.with_name(backup_path.name + '.context.json'))
        try:
            with path.open('rb') as stream:
                raw = stream.read(1025)
            if len(raw) > 1024:
                raise SaveError('PS3 backup context manifest exceeds its bounded size.')
            manifest = json.loads(raw)
        except (OSError, ValueError, UnicodeError) as error:
            raise SaveError('PS3 backup context manifest is missing or damaged.') from error
        if (type(manifest) is not dict or manifest.get('game_id') != self.game_id
                or manifest.get('kind') != 'ps3-export-context'
                or manifest.get('context_sha256') != digest):
            raise SaveError('Restore requires the exact original PS3 metadata from the backup.')
        def validate(raw):
            self.decode(raw, self.game_id)
            if hashlib.sha256(raw).hexdigest() != manifest.get('save_sha256'):
                raise SaveError('The PS3 backup context belongs to a different gameplay snapshot.')
            if self.context_raw(destination) != metadata:
                raise SaveError('The PS3 destination metadata changed during restore.')
        result = restore_snapshot(backup_path, destination, self.game_id, '.bin', self.size, validate_raw=validate)
        reopened = self.read_save(result, self.game_id)
        if reopened.sha256 != manifest.get('save_sha256') or self.context_raw(result) != metadata:
            raise SaveError('Restored gameplay or PS3 metadata changed during actual read-back.')
        return result
