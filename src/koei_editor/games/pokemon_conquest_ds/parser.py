"""Independent native gallery-IV writer; see POKEMON_CONQUEST_DS_FORMAT.md.

Both physical gallery banks retain their own records and generation counters.
No scenario data, Pokémon identity, link, EXP, ownership or story is rewritten.
"""
from dataclasses import dataclass
from functools import lru_cache
import hashlib
from pathlib import Path
import struct
from types import MappingProxyType

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.copy_storage import atomic_new, restore_snapshot, snapshot_backup
from koei_editor.shared.save_safety import safe_path

GAME_ID = 'pokemon_conquest_ds'
TITLE = 'Pokémon Conquest'
EXTENSION = '.sav'
SAVE_SIZES = (0x40000, 0x80000)
SAVE_SIZE = max(SAVE_SIZES)
HEADER_SIZE = 24
TITLE_MARKER = b'TWL-P-VPYT\0\0'
SECTION_SIZES = (0xA0, 0xA0, 0x30, 0xC76, 0xAB8, 0x1A58, 0xA44,
                 0x2278, 0xF18, 0x504, 0x408, 0xE0, 0x3D08)
BANK_SIZE = sum(SECTION_SIZES)
GALLERY_OFFSETS = (0x78B6, 0x12E74)
WARRIOR_BYTES = 0xE10
RECORD_SIZE = 12
IV_LAYOUT = ((4, 15, 'IV component 1'), (4, 20, 'IV component 2'),
             (4, 25, 'IV component 3'), (8, 0, 'Speed IV'))
# Independently written bare species-ID/name facts. Ransei Gallery order and
# selected native IDs are corroborated by the public references in the format
# document; no foreign enum implementation, article prose or assets are copied.
SPECIES_NAMES = MappingProxyType(dict(enumerate('''
Eevee Vaporeon Jolteon Flareon Espeon Umbreon Leafeon Glaceon
Ralts Kirlia Gardevoir Gallade Magikarp Gyarados Pichu Pikachu Raichu
Wooper Quagsire Igglybuff Jigglypuff Wigglytuff Zubat Golbat Crobat
Starly Staravia Staraptor Bidoof Bibarel Venipede Whirlipede Scolipede
Shinx Luxio Luxray Litwick Lampent Chandelure Roggenrola Boldore Gigalith
Petilil Lilligant Mareep Flaaffy Ampharos Cottonee Whimsicott Riolu Lucario
Chingling Chimecho Ekans Arbok Pineco Forretress Meowth Persian
Spheal Sealeo Walrein Gothita Gothorita Gothitelle Sandile Krokorok Krookodile
Duskull Dusclops Dusknoir Munna Musharna Blitzle Zebstrika
Dratini Dragonair Dragonite Larvitar Pupitar Tyranitar Beldum Metang Metagross
Gible Gabite Garchomp Croagunk Toxicroak Deino Zweilous Hydreigon
Snorunt Glalie Froslass Minccino Cinccino Machop Machoke Machamp
Timburr Gurdurr Conkeldurr Cubchoo Beartic Oshawott Dewott Samurott
Charmander Charmeleon Charizard Gastly Haunter Gengar Chimchar Monferno Infernape
Snivy Servine Serperior Tepig Pignite Emboar Sewaddle Swadloon Leavanny
Abra Kadabra Alakazam Treecko Grovyle Sceptile Piplup Prinplup Empoleon
Pansage Simisage Pansear Simisear Panpour Simipour Darumaka Darmanitan
Axew Fraxure Haxorus Joltik Galvantula Aron Lairon Aggron Drilbur Excadrill
Zorua Zoroark Skorupi Drapion Pawniard Bisharp Rhyhorn Rhydon Rhyperior
Shieldon Bastiodon Scraggy Scrafty Drifloon Drifblim Rufflet Braviary
Anorith Armaldo Larvesta Volcarona Onix Steelix Beedrill Munchlax Snorlax Emolga
Sneasel Weavile Misdreavus Mismagius Audino Carnivine Spiritomb Scyther Scizor Lapras
Terrakion Articuno Registeel Groudon Dialga Mewtwo Reshiram Zekrom Arceus Rayquaza
'''.split())))


@dataclass(frozen=True)
class Field:
    id: str
    label: str
    offset: int
    shift: int
    group: str
    slot: int
    size: int = 4
    minimum: int = 0
    maximum: int = 31
    maxable: bool = True
    kind: str = 'integer'

    def value(self, payload):
        return (int.from_bytes(payload[self.offset:self.offset + 4], 'little') >> self.shift) & 31

    def validate(self, value):
        if type(value) is not int or not 0 <= value <= 31:
            raise SaveError(f'{self.label} requires a whole number from 0 to 31.')


@dataclass(frozen=True)
class Format:
    id: str = GAME_ID
    title: str = TITLE
    size: int = SAVE_SIZE
    fields: tuple = ()
    sample_verified: bool = True
    game_load_verified: bool = False
    note: str = ('North American vanilla-layout DS raw .sav, 256/512 KiB. '
                 'Gallery IV components and Speed IV; each bank retains its own records. '
                 'HP/attack/defense component ordering remains unnamed. '
                 'Scenario Pokémon, warrior links, EXP and story are preserved.')


FORMAT = Format()


@dataclass(frozen=True)
class Document:
    format: Format
    source: Path
    raw: bytes
    payload: bytes

    @property
    def sha256(self):
        return hashlib.sha256(self.raw).hexdigest()


def get_format(game_id=GAME_ID):
    if game_id != GAME_ID:
        raise SaveError('Choose the explicit North American Nintendo DS Pokémon Conquest editor.')
    return FORMAT


def _sections(payload):
    offset = 0
    for index, size in enumerate(SECTION_SIZES * 2):
        checksum, descriptor, generation = struct.unpack_from('<III', payload, offset)
        if index % 13 in (7, 12):
            if descriptor & 511:
                raise SaveError('Unsupported variable-section flags or expanded save layout.')
            length = descriptor >> 9
            if not 0 < length <= size - HEADER_SIZE:
                raise SaveError('Variable-section length exceeds the original DS save layout.')
            if index % 13 == 12 and (length < WARRIOR_BYTES or (length - WARRIOR_BYTES) % RECORD_SIZE):
                raise SaveError('The gallery record count does not fit the qualified native layout.')
        else:
            if descriptor != 0:
                raise SaveError('Unsupported fixed-section descriptor or expanded save layout.')
            length = size - HEADER_SIZE
        yield index, offset, size, length, checksum, generation
        offset += size


def decode(raw, game_id=GAME_ID, source=Path('conquest-copy.sav')):
    get_format(game_id)
    if type(raw) is not bytes or len(raw) not in SAVE_SIZES:
        raise SaveError('Use a complete 256 or 512 KiB North American raw .sav export; DUC/DSV containers are excluded.')
    _validate_native(raw)
    return Document(FORMAT, Path(source), raw, raw)


@lru_cache(maxsize=4)
def _validate_native(raw):
    """Cache exact immutable bytes, never a pathname, size or mutable snapshot."""
    for _index, offset, _size, length, checksum, _generation in _sections(raw):
        if raw[offset + 12:offset + HEADER_SIZE] != TITLE_MARKER:
            raise SaveError('Save section does not identify the North American Pokémon Conquest title.')
        if sum(raw[offset + HEADER_SIZE:offset + HEADER_SIZE + length]) != checksum:
            raise SaveError('A native section checksum is invalid; damaged saves are not repaired.')
    # Each independently shared native copy has erased outer padding. Enlarged
    # record layouts and foreign tails are not silently trimmed or normalized.
    if raw[BANK_SIZE * 2:] != b'\xFF' * (len(raw) - BANK_SIZE * 2):
        raise SaveError('Unsupported non-erased tail or expanded-ROM save layout.')


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = safe_path(path)
    _extension(path)
    with path.open('rb') as stream:
        return decode(stream.read(SAVE_SIZE + 1), game_id, path)


def _extension(path):
    if Path(path).suffix.casefold() != EXTENSION:
        raise SaveError('Choose a separate raw DS .sav copy.')


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or type(document.raw) is not bytes or type(document.payload) is not bytes
            or document.payload != document.raw):
        raise SaveError('Invalid or changed immutable Pokémon Conquest snapshot.')
    decode(document.raw, GAME_ID, document.source)


def _gallery(payload):
    for bank, base in enumerate(GALLERY_OFFSETS, 1):
        length = struct.unpack_from('<I', payload, base + 4)[0] >> 9
        count = (length - WARRIOR_BYTES) // RECORD_SIZE
        generation = struct.unpack_from('<I', payload, base + 8)[0]
        for slot in range(count):
            offset = base + HEADER_SIZE + WARRIOR_BYTES + slot * RECORD_SIZE
            species = struct.unpack_from('<I', payload, offset)[0]
            # The source patches low-byte identity; the independent native
            # references use exact vanilla 0–199 words. Unknown records remain
            # inspectable, never candidates for mutable or invented ownership.
            name = SPECIES_NAMES.get(species, f'Pokémon ID {species}') if species < 200 else f'Unknown record ID {species}'
            values = tuple((struct.unpack_from('<I', payload, offset + delta)[0] >> shift) & 31
                           for delta, shift, _label in IV_LAYOUT)
            yield bank, slot + 1, offset, species, name, generation, values


@lru_cache(maxsize=4)
def _field_index(payload):
    result = {}
    for bank, slot, offset, species, name, _generation, _values in _gallery(payload):
        if not 0 <= species < 200:
            continue
        for component, (delta, shift, label) in enumerate(IV_LAYOUT, 1):
            key = f'bank_{bank}_pokemon_{slot}_iv_{component}'
            result[key] = Field(key, f'{name} (record {slot}): {label}', offset + delta,
                                shift, f'Gallery bank {bank} IVs', (bank - 1) * 1000 + slot,
                                maxable=not (species == 56 and component == 4))
    return MappingProxyType(result)


def field_map(document):
    validate_document(document)
    return _field_index(document.payload)


def fields_for(document):
    return tuple(field_map(document).values())


def changed_payload(document, changes):
    if type(changes) is not dict:
        raise SaveError('Pending changes must be a dictionary.')
    fields = field_map(document)
    output = bytearray(document.payload)
    touched = set()
    for key, value in changes.items():
        if type(key) is not str or key not in fields:
            raise SaveError('Select a qualified existing gallery IV component.')
        field = fields[key]
        field.validate(value)
        if value == field.value(document.payload):
            continue
        word = struct.unpack_from('<I', output, field.offset)[0]
        struct.pack_into('<I', output, field.offset,
                         (word & ~(31 << field.shift)) | (value << field.shift))
        touched.add(0 if field.slot <= 1000 else 1)
    for bank in touched:
        base = GALLERY_OFFSETS[bank]
        length = struct.unpack_from('<I', output, base + 4)[0] >> 9
        struct.pack_into('<I', output, base, sum(output[base + HEADER_SIZE:base + HEADER_SIZE + length]))
    return bytes(output)


def serialize(document, changes):
    result = changed_payload(document, changes)
    decode(result, GAME_ID, document.source)
    return result


def stage(document, changes, key, value):
    changed_payload(document, changes)
    fields = field_map(document)
    if type(key) is not str or key not in fields:
        raise SaveError('Select a qualified existing gallery IV component.')
    fields[key].validate(value)
    result = dict(changes)
    if value == fields[key].value(document.payload):
        result.pop(key, None)
    else:
        result[key] = value
    return result


def limit_values(document, changes, keys):
    changed_payload(document, changes)
    fields = field_map(document)
    result = {}
    for key in keys:
        if type(key) is not str or key not in fields:
            raise SaveError('Select a qualified existing gallery IV component.')
        if fields[key].maxable:
            result[key] = 31
    return result


def maximums(document, changes, group=None):
    changed_payload(document, changes)
    result = dict(changes)
    for field in fields_for(document):
        if not field.maxable or (group is not None and field.group != group):
            continue
        if field.value(document.payload) == field.maximum:
            result.pop(field.id, None)
        else:
            result[field.id] = field.maximum
    changed_payload(document, result)
    return result


def review(document, changes):
    changed_payload(document, changes)
    return [(field, field.value(document.payload), changes[field.id])
            for field in fields_for(document) if field.id in changes]


def backup(document):
    _validate_source(document)
    source = safe_path(document.source)
    return snapshot_backup(document.raw, source, GAME_ID, source.parent / 'WarriorsEditorBackups')


def _validate_source(document):
    validate_document(document)
    source = safe_path(document.source)
    _extension(source)
    with source.open('rb') as stream:
        if stream.read(SAVE_SIZE + 1) != document.raw:
            raise SaveError('The opened copy changed on disk. Reopen it before saving.')


def save_as(document, changes, destination):
    destination = safe_path(destination)
    _extension(destination)
    if destination.exists():
        raise FileExistsError('Choose a new destination; existing files are never replaced.')
    _validate_source(document)
    raw = serialize(document, changes)
    backup(document)
    _validate_source(document)
    atomic_new(raw, destination)
    return decode(raw, GAME_ID, destination)


def restore(backup_path, destination, game_id=GAME_ID):
    get_format(game_id)
    return restore_snapshot(safe_path(backup_path), safe_path(destination), GAME_ID,
                            EXTENSION, SAVE_SIZE, validate_raw=lambda raw: decode(raw, game_id))


def record_label(slot, group='Gallery'):
    bank, record = divmod(slot - 1, 1000)
    return f'Gallery bank {bank + 1}, Pokémon record {record + 1}'


def field_hint(document, key):
    field = field_map(document).get(key)
    if field is None:
        raise SaveError('Select a qualified existing gallery IV component.')
    extra = ('Forretress Speed is manual only; bulk Max preserves it because lower '
             'Speed can improve its Gyro Ball damage. ') if not field.maxable else ''
    return (extra + 'Gallery individual value, 0–31; Max sets eligible selected components to 31. '
            'The three numbered components are the HP/attack/defense IVs in native order; '
            'their individual stat correspondence has not been established. The fourth is Speed IV. '
            'Both gallery banks are separate records; select both groups to apply the same bulk action. '
            'This edits gallery persistence only; current scenario Pokémon, link/EXP, species, '
            'abilities, warrior ownership and story remain unchanged.')


def gallery_records(document):
    validate_document(document)
    return tuple((bank, generation, slot, name, species, *values,
                  'Editable' if species < 200 else 'Preserved unknown record')
                 for bank, slot, _offset, species, name, generation, values in _gallery(document.payload))


def inspection_rows(document):
    return tuple({'group': f'Gallery bank {row[0]}',
                  'label': f'{row[3]} record {row[2]}: IV components / Speed',
                  'value': ', '.join(str(value) for value in row[5:9])}
                 for row in gallery_records(document))


INTEGRITY_KIND = 'checksum'
