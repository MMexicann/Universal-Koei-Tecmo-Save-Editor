"""Read-only research on frozen, natively qualified comparison snapshots.

Offsets always address the parser's decoded payload, never the encrypted file or
container. Numeric interpretations are hypotheses, not field mappings or edits.
"""
from dataclasses import asdict, dataclass
import json
import math
import struct

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared import save_comparison
from koei_editor.shared.copy_storage import atomic_new
from koei_editor.shared.save_safety import safe_path

MAX_WINDOW = 4096
MAX_RESULTS = 1000


@dataclass(frozen=True)
class Annotation:
    offset: int
    length: int
    title: str
    observation: str
    evidence: str = ''


@dataclass(frozen=True)
class CandidateQuery:
    before: int
    after: int
    widths: tuple[int, ...] = (1, 2, 4, 8)
    byteorder: str = 'little'
    signed: bool = False
    start: int = 0
    end: int | None = None
    alignment: int = 1


def _validated(comparison):
    # This recomputes comparison rows/counts against native immutable documents.
    return save_comparison.report(comparison)


def _integer(value, name, minimum=0, maximum=None):
    if type(value) is not int or value < minimum or (maximum is not None and value > maximum):
        raise SaveError(f'{name} must be an integer from {minimum}'
                        + (f' to {maximum}.' if maximum is not None else '.'))


def _range(comparison, offset, length):
    _integer(offset, 'Decoded offset')
    _integer(length, 'Length', 1, MAX_WINDOW)
    size = max(len(comparison.left.payload), len(comparison.right.payload))
    if offset >= size or offset + length > size:
        raise SaveError('The requested span lies outside both qualified decoded payloads.')


def _fields(comparison):
    adapter = save_comparison.adapter_for(comparison.game_id)
    return tuple((side, field) for side, document in
                 (('first', comparison.left), ('second', comparison.right))
                 for field in adapter.field_map(document).values())


def _overlap(fields, offset, length):
    return [{'side': side, 'id': field.id, 'label': field.label,
             'offset': field.offset, 'length': field.size}
            for side, field in fields
            if field.offset < offset + length and field.offset + field.size > offset]


def byte_window(comparison, offset=0, length=256):
    """Bounded hex rows; missing trailing bytes remain distinct from zero bytes."""
    _validated(comparison)
    _range(comparison, offset, length)
    fields, rows = _fields(comparison), []
    first, second = comparison.left.payload, comparison.right.payload
    for start in range(offset, offset + length, 16):
        stop = min(start + 16, offset + length)
        before, after = first[start:stop], second[start:stop]
        changed = [index for index in range(stop - start)
                   if before[index:index + 1] != after[index:index + 1]]
        rows.append({'offset': start, 'first_hex': before.hex(' '),
                     'second_hex': after.hex(' '), 'changed_indexes': changed,
                     'mapped_spans': _overlap(fields, start, stop - start)})
    return rows


def changed_runs(comparison, limit=MAX_RESULTS):
    """Contiguous decoded changes with a bounded preview, without guessing roles."""
    _validated(comparison)
    _integer(limit, 'Result limit', 1, MAX_RESULTS)
    first, second = comparison.left.payload, comparison.right.payload
    fields, rows, count, opened = _fields(comparison), [], 0, None
    size = max(len(first), len(second))
    for offset in range(size + 1):
        differs = offset < size and first[offset:offset + 1] != second[offset:offset + 1]
        if differs and opened is None:
            opened = offset
        if not differs and opened is not None:
            count += 1
            if len(rows) < limit:
                length = offset - opened
                preview_stop = opened + min(length, 32)
                rows.append({'offset': opened, 'length': length,
                             'first_hex': first[opened:preview_stop].hex(' '),
                             'second_hex': second[opened:preview_stop].hex(' '),
                             'preview_truncated': length > 32,
                             'mapped_spans': _overlap(fields, opened, length)})
            opened = None
    return {'total_runs': count, 'truncated': count > len(rows), 'runs': rows}


def inspect_offset(comparison, offset, length=8):
    """Both endian integer/float interpretations and bit differences at an offset."""
    _validated(comparison)
    _range(comparison, offset, length)
    result = {'offset': offset, 'length': length,
              'mapped_spans': _overlap(_fields(comparison), offset, length), 'interpretations': []}
    for side, document in (('first', comparison.left), ('second', comparison.right)):
        raw = document.payload[offset:offset + length]
        result[side + '_hex'] = raw.hex(' ')
        for width in (1, 2, 4, 8):
            if width > len(raw):
                continue
            for order in ('little', 'big'):
                row = {'side': side, 'width': width, 'byteorder': order,
                       'unsigned': int.from_bytes(raw[:width], order),
                       'signed': int.from_bytes(raw[:width], order, signed=True)}
                if width in (4, 8):
                    value = struct.unpack(('<' if order == 'little' else '>')
                                          + ('f' if width == 4 else 'd'), raw[:width])[0]
                    row['float'] = value if math.isfinite(value) else str(value)
                result['interpretations'].append(row)
    before, after = comparison.left.payload[offset:offset + length], comparison.right.payload[offset:offset + length]
    result['xor_hex'] = bytes(a ^ b for a, b in zip(before, after)).hex(' ')
    result['xor_common_bytes'] = min(len(before), len(after))
    result['changed_bits'] = sum((a ^ b).bit_count() for a, b in zip(before, after))
    return result


def discover_candidates(comparison, query, limit=MAX_RESULTS):
    """Find exact controlled before/after integers; every match stays a hypothesis.

    The search uses both snapshots and retains all matching widths/endianness.
    Alignment is relative to decoded offset zero. No write API is provided.
    """
    _validated(comparison)
    _integer(limit, 'Result limit', 1, MAX_RESULTS)
    if type(query) is not CandidateQuery:
        raise SaveError('A numeric candidate query is required.')
    for value in (query.before, query.after):
        if type(value) is not int:
            raise SaveError('Controlled observations must be exact integers.')
    if query.before == query.after:
        raise SaveError('Use a controlled action with different before and after observations.')
    if (type(query.widths) is not tuple or not query.widths
            or any(type(width) is not int or width not in (1, 2, 4, 8) for width in query.widths)
            or len(set(query.widths)) != len(query.widths)
            or type(query.byteorder) is not str or query.byteorder not in ('little', 'big')
            or type(query.signed) is not bool):
        raise SaveError('Choose unique 1/2/4/8-byte widths and explicit byte order and signedness.')
    _integer(query.start, 'Search start')
    _integer(query.alignment, 'Alignment', 1, 4096)
    first, second = comparison.left.payload, comparison.right.payload
    end = min(len(first), len(second)) if query.end is None else query.end
    _integer(end, 'Search end', 1, min(len(first), len(second)))
    if query.start >= end:
        raise SaveError('Search start must precede its exclusive end.')
    rows, count, encodings = [], 0, []
    for width in query.widths:
        try:
            before = query.before.to_bytes(width, query.byteorder, signed=query.signed)
            after = query.after.to_bytes(width, query.byteorder, signed=query.signed)
        except OverflowError:
            continue
        encodings.append((width, before, after))
    if not encodings:
        raise SaveError('Observed values do not fit the selected numeric encodings.')
    fields = _fields(comparison)
    for width, before, after in encodings:
        # Search the rarer observation first so zero-filled/low-valued native
        # regions do not require a Python iteration for every unchanged byte.
        haystack, needle, other, expected = first, before, second, after
        if second.count(after, query.start, end) < first.count(before, query.start, end):
            haystack, needle, other, expected = second, after, first, before
        offset = haystack.find(needle, query.start, end)
        while offset >= 0:
            if offset % query.alignment == 0 and other[offset:offset + width] == expected:
                count += 1
                if len(rows) < limit:
                    rows.append({'offset': offset, 'length': width,
                                 'first_hex': before.hex(' '), 'second_hex': after.hex(' '),
                                 'status': 'unverified_hypothesis',
                                 'mapped_spans': _overlap(fields, offset, width)})
            offset = haystack.find(needle, offset + 1, end)
    rows.sort(key=lambda row: (row['offset'], row['length']))
    return {'query': asdict(query), 'total_candidates': count,
            'truncated': count > len(rows), 'candidates': rows,
            'qualification': 'Exact numeric correlation only. Repeat controlled actions and unchanged controls; '
                             'establish encoding, record identity and dependencies before proposing a mapping.'}


def validate_annotations(comparison, annotations):
    if type(annotations) is not tuple or len(annotations) > 200:
        raise SaveError('Keep at most 200 immutable research annotations.')
    for note in annotations:
        if type(note) is not Annotation:
            raise SaveError('A decoded-span research annotation is required.')
        _range(comparison, note.offset, note.length)
        for key, maximum in (('title', 160), ('observation', 4096), ('evidence', 4096)):
            value = getattr(note, key)
            if type(value) is not str or len(value) > maximum or '\0' in value:
                raise SaveError(f'Annotation {key} must be text of at most {maximum} characters.')
        if not note.title.strip() or not note.observation.strip():
            raise SaveError('Give each annotation a title and observation or hypothesis.')
    return annotations


def report(comparison, *, annotations=(), action='', query=None, offset=None, length=8):
    base = _validated(comparison)
    validate_annotations(comparison, annotations)
    if type(action) is not str or len(action) > 4096 or '\0' in action:
        raise SaveError('Controlled-action notes must be text of at most 4096 characters.')
    return {'schema': 'koei-save-research', 'schema_version': 1, 'read_only': True,
            'offset_space': 'decoded_payload', 'comparison': base,
            'controlled_action': action, 'annotations': [asdict(note) for note in annotations],
            'decoded_changes': changed_runs(comparison),
            'offset_analysis': None if offset is None else inspect_offset(comparison, offset, length),
            'candidate_search': None if query is None else discover_candidates(comparison, query),
            'research_limits': ['Candidate interpretations do not establish field mappings or editable ranges.',
                                'Overlap identifies storage spans only; packed bits and native integrity are not qualified.',
                                'Repeat with independent controlled pairs and unchanged controls; confirm record identities, '
                                'dependencies, native integrity and surgical roundtrips before implementation.',
                                'Private research export includes decoded byte excerpts, scalar values and free-text notes. '
                                'Review it before sharing with Codex or others; no source paths or companion bytes are exported.']}


def export(comparison, destination, **options):
    """Atomic new private JSON report with source/context revalidation and read-back."""
    destination = safe_path(destination)
    if destination.suffix.lower() != '.json':
        raise SaveError('Choose a new .json research report.')
    if destination.exists():
        raise FileExistsError('Choose a new report; existing files are never replaced.')
    raw = (json.dumps(report(comparison, **options), ensure_ascii=False, indent=2,
                      allow_nan=False) + '\n').encode('utf-8')
    save_comparison.validate_sources(comparison)
    atomic_new(raw, destination)
    try:
        save_comparison.validate_sources(comparison)
        with destination.open('rb') as stream:
            if stream.read(len(raw) + 1) != raw:
                raise SaveError('Research report changed during actual destination read-back.')
    except Exception:
        try:
            with destination.open('rb') as stream:
                unchanged = stream.read(len(raw) + 1) == raw
            if unchanged:
                destination.unlink()
        except OSError:
            pass
        raise
    return destination
