"""Exact Xbox 360 CON context, typed migrations and immutable export checks."""
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.dw6_xbox360 import north_american_export as na, european_export as eu
from koei_editor.games.dw6_xbox360 import regional_export as backend, stfs_context as context


def raw_fixture(seed=0):
    """Procedural bytes only; no native player/account context is included."""
    raw = bytearray((i * 37 + seed * 73) & 255 for i in range(context.SAVE_SIZE))
    for index in range(41):
        at = context.OFFICER_BASE + index * 168 + 136
        raw[at:at + 4] = index.to_bytes(4, 'big')
    raw[context.MARKER_OFFSET:context.MARKER_OFFSET + 4] = context.MARKER
    return bytes(raw)


def _rehash(raw):
    """Rehash this test's generated single-table CON after a controlled mutation."""
    raw = bytearray(raw)
    count = int.from_bytes(raw[0x395:0x399], 'big')
    for index in range(count):
        at = 0xC000 + index * 4096
        digest = hashlib.sha1(raw[at:at + 4096]).digest()
        raw[0xA000 + index * 24:0xA000 + index * 24 + 20] = digest
    raw[0xB000:0xC000] = raw[0xA000:0xB000]
    raw[0x381:0x395] = hashlib.sha1(raw[0xA000:0xB000]).digest()
    raw[0x32C:0x340] = hashlib.sha1(raw[0x344:0xA000]).digest()
    return bytes(raw)


def context_fixture(game_id, payload=None, seed=0):
    title_id, name = context.PROFILES[game_id]
    payload = raw_fixture(seed) if payload is None else payload
    count = 1 + (len(payload) + 4095) // 4096
    raw = bytearray(0xC000 + count * 4096)
    raw[:0xA000] = bytes((i * 19 + seed * 13) & 255 for i in range(0xA000))
    raw[:4] = b'CON '
    raw[0x340:0x344] = (0x971A).to_bytes(4, 'big')
    raw[0x344:0x34C] = bytes.fromhex('0000000100000002')
    raw[0x34C:0x354] = bytes(8)
    raw[0x360:0x364] = title_id.to_bytes(4, 'big')
    raw[0x379:0x381] = b'\x24\x00\x00\x01\x00\x00\x00\x00'
    raw[0x395:0x399] = count.to_bytes(4, 'big')
    raw[0x399:0x39D] = bytes(4)
    entry = 0xC000
    raw[entry:entry + len(name)] = name.encode('ascii')
    raw[entry + 40] = 64 + len(name)
    raw[entry + 41:entry + 44] = (count - 1).to_bytes(3, 'little')
    raw[entry + 44:entry + 47] = (count - 1).to_bytes(3, 'little')
    raw[entry + 47:entry + 50] = (1).to_bytes(3, 'little')
    raw[entry + 50:entry + 52] = b'\xFF\xFF'
    raw[entry + 52:entry + 56] = len(payload).to_bytes(4, 'big')
    raw[0xD000:0xD000 + len(payload)] = payload
    for index in range(count):
        at = 0xA000 + index * 24
        raw[at + 20] = 0x80
        raw[at + 21:at + 24] = (index + 1 if 0 < index < count - 1 else 0xFFFFFF).to_bytes(3, 'big')
    return _rehash(raw)


def _copy(folder, profile, seed=0, raw=None, native_context=None):
    folder.mkdir(parents=True, exist_ok=True)
    raw = raw_fixture(seed) if raw is None else raw
    path = folder / profile.FILENAME
    path.write_bytes(raw)
    (folder / 'ORIGINAL.CON').write_bytes(context_fixture(profile.GAME_ID, raw, seed)
                                         if native_context is None else native_context)
    return path


def _assert_typed_transfer(case, reviewed, actual):
    """Independent numeric/byte checks supplement reversible canonical hashes."""
    source, target = reviewed.source.document.raw, actual.raw
    source_id, target_id, variant = reviewed.route.source_id, reviewed.route.target_id, reviewed.route.variant
    source_order = 'little' if source_id == 'dw6' else 'big'
    target_order = 'little' if target_id == 'dw6' else 'big'
    sb, tb = (0xB58 if source_id == 'dw6' else 0xB18), (0xB58 if target_id == 'dw6' else 0xB18)
    sh, th = (0x2A08 if source_id == 'dw6' else 0x29C8), (0x2A08 if target_id == 'dw6' else 0x29C8)
    spans = [(tb, tb + 41 * 168), (th, th + 8 * 60)]

    def word(a, b, width=4):
        case.assertEqual(int.from_bytes(source[a:a + width], source_order),
                         int.from_bytes(target[b:b + width], target_order))

    for index in range(41):
        a, b = sb + index * 168, tb + index * 168
        word(a, b, 8)
        for relative in range(8, 164, 4):
            word(a + relative, b + relative)
        case.assertEqual(source[a + 164:a + 168], target[b + 164:b + 168])
    for index in range(8):
        for relative in range(0, 60, 4):
            word(sh + index * 60 + relative, th + index * 60 + relative)
    if variant:
        ss, ts = sb + 41 * 168, tb + 41 * 168
        for index in range(45):
            a, b = ss + index * 20, ts + index * 20
            for relative in (0, 4, 8):
                word(a + relative, b + relative)
            case.assertEqual(source[a + 12:a + 20], target[b + 12:b + 20])
        case.assertEqual(source[ss + 900:ss + 968], target[ts + 900:ts + 968])
        spans = [(tb, th + 480)]
    if variant in ('campaigns', 'records'):
        for index in range(20):
            a, b = sb - 2640 + index * 132, tb - 2640 + index * 132
            for relative in range(0, 20, 4):
                word(a + relative, b + relative)
            for result in range(6):
                rel = 20 + result * 16
                for relative in (0, 4, 8):
                    word(a + rel + relative, b + rel + relative)
                case.assertEqual(source[a + rel + 12:a + rel + 16], target[b + rel + 12:b + rel + 16])
            for relative in range(116, 132, 4):
                word(a + relative, b + relative)
        spans = [(tb - 2640, th + 480)]
    if variant == 'records':
        sg, tg = (0xB4 if source_id == 'dw6' else 0xAC), (0xB4 if target_id == 'dw6' else 0xAC)
        sc = 0x2BF6 if source_id == 'dw6' else 0x2BB6 if source_id == 'dw6_ps3_jp' else 0x2BA8
        tc = 0x2BF6 if target_id == 'dw6' else 0x2BB6 if target_id == 'dw6_ps3_jp' else 0x2BA8
        case.assertEqual(source[sg:sg + 26], target[tg:tg + 26])
        case.assertEqual(source[sg + 26] & 3, target[tg + 26] & 3)
        case.assertEqual(target[tg + 26] & 0xFC, reviewed.template.document.raw[tg + 26] & 0xFC)
        for index in range(50):
            a, b = sc + index * 4, tc + index * 4
            word(a, b, 2)
            case.assertEqual(source[a + 2:a + 4], target[b + 2:b + 4])
        spans.extend(((tg, tg + 27), (tc, tc + 200)))
    expected = bytearray(reviewed.template.document.raw)
    for left, right in spans:
        expected[left:right] = target[left:right]
    case.assertEqual(target, bytes(expected))


def _export_and_reverse(case, route, source, template, folder):
    from koei_editor import conversion as c
    before, template_before = source.read_bytes(), template.read_bytes()
    reviewed = c.prepare(route.id, source, template)
    destination, backups, receipt = c.export(reviewed, folder / 'forward')
    actual = c.ENDPOINTS[route.target_id].backend.read_save(destination)
    _assert_typed_transfer(case, reviewed, actual)
    case.assertEqual(receipt['gameplay_bytes'], {'': 7368, 'progress': 8336, 'campaigns': 10976, 'records': 11203}[route.variant])
    case.assertEqual(receipt['gameplay_sha256'], hashlib.sha256(c._gameplay(reviewed.source, route)).hexdigest())
    case.assertEqual(receipt['transfer_scope'], route.transfer_scope)
    case.assertFalse(receipt['game_load_verified'])
    case.assertFalse(receipt['console_signing_performed'])
    case.assertEqual([path.read_bytes() for path in backups], [before, template_before])
    target = c.ENDPOINTS[route.target_id]
    if target.companion:
        case.assertEqual((destination.parent / target.companion).read_bytes(), reviewed.template.companion_raw)
    suffix = '-' + route.variant if route.variant else ''
    reverse = c.prepare(route.target_id + '-to-' + route.source_id + suffix, destination, source)
    restored, _backups, _receipt = c.export(reverse, folder / 'reverse')
    case.assertEqual(restored.read_bytes(), before)
    case.assertEqual(source.read_bytes(), before)
    case.assertEqual(template.read_bytes(), template_before)
    return destination


class Xbox360DW6ProfileTests(unittest.TestCase):
    def test_exact_raw_framing_and_frozen_region_identity(self):
        raw = raw_fixture()
        document = na.decode(raw)
        self.assertEqual(na.serialize(document, {}), raw)
        for invalid in (raw[:-1], raw + b'\0', bytes(len(raw)), bytearray(raw)):
            with self.assertRaises(SaveError):
                na.decode(invalid)
        for game_id in (None, eu.GAME_ID, 'dw6_ps3', 'dw6_empires'):
            with self.assertRaises(SaveError):
                na.decode(raw, game_id)
        broken = bytearray(raw)
        at = context.OFFICER_BASE + 168 + 136
        broken[at:at + 4] = (1).to_bytes(4, 'little')
        with self.assertRaises(SaveError):
            na.decode(bytes(broken))
        for forged in (replace(document, format=na.Format(na.GAME_ID)),
                       replace(document, format=eu.FORMAT),
                       replace(document, payload=bytearray(raw)),
                       replace(document, context_digest=None)):
            with self.assertRaises(SaveError):
                na.validate_document(forged)
        with self.assertRaises(SaveError):
            na.serialize(document, {'officer_0_level': 50})

    def test_stfs_header_root_every_payload_block_and_chain_are_checked(self):
        raw, original = raw_fixture(), context_fixture(na.GAME_ID)
        self.assertEqual(context.extract_payload(original, na.GAME_ID), raw)
        with self.assertRaises(SaveError):
            context.extract_payload(original, eu.GAME_ID)
        for offset in (0x1000, 0xC000, 0xD000, len(original) - 1):
            damaged = bytearray(original)
            damaged[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(SaveError):
                context.extract_payload(bytes(damaged), na.GAME_ID)
        damaged = bytearray(original)
        damaged[0xA000] ^= 1
        damaged[0xB000] ^= 1
        with self.assertRaises(SaveError):
            context.extract_payload(bytes(damaged), na.GAME_ID)
        # A self-consistent header cannot claim allocation blocks absent from
        # the actual file, even when its selected gameplay chain fits inside.
        damaged = bytearray(original)
        damaged[0x395:0x399] = (170).to_bytes(4, 'big')
        damaged[0x32C:0x340] = hashlib.sha1(damaged[0x344:0xA000]).digest()
        with self.assertRaises(SaveError):
            context.extract_payload(bytes(damaged), na.GAME_ID)
        mutations = ((0xC000 + 47, (0).to_bytes(3, 'little')),
                     (0xC000 + 64, b'X'),
                     (0xC000, b'DW6_EU.dat'),
                     (0xA000 + 24 + 21, (1).to_bytes(3, 'big')),
                     (0xA000 + 24 + 21, (169).to_bytes(3, 'big')),
                     (0xA000 + 52 * 24 + 21, (1).to_bytes(3, 'big')))
        for offset, value in mutations:
            damaged = bytearray(original)
            damaged[offset:offset + len(value)] = value
            with self.subTest(offset=offset, value=value), self.assertRaises(SaveError):
                context.extract_payload(_rehash(damaged), na.GAME_ID)
        for invalid in (original[:-1], original + bytes(context.MAX_CONTEXT_SIZE), b'LIVE' + original[4:]):
            with self.assertRaises(SaveError):
                context.extract_payload(invalid, na.GAME_ID)

    def test_open_requires_original_bounded_regional_context_and_detects_replacement(self):
        for profile in (na, eu):
            with self.subTest(profile=profile.GAME_ID), tempfile.TemporaryDirectory() as temporary:
                path = _copy(Path(temporary), profile)
                document = profile.read_save(path)
                original_context = (path.parent / 'ORIGINAL.CON').read_bytes()
                self.assertEqual(document.context_digest, hashlib.sha256(original_context).hexdigest())
                other = eu if profile is na else na
                with self.assertRaises(SaveError):
                    other.read_save(path)
                # A converted raw file reopens under unchanged original context.
                path.write_bytes(raw_fixture(1))
                self.assertEqual(profile.read_save(path).raw, raw_fixture(1))
                with self.assertRaises(SaveError):
                    profile.backup(document)
                path.write_bytes(document.raw)
                (path.parent / 'ORIGINAL.CON').write_bytes(context_fixture(profile.GAME_ID, seed=1))
                with self.assertRaises(SaveError):
                    profile.backup(document)
                (path.parent / 'ORIGINAL.CON').unlink()
                with self.assertRaises(SaveError):
                    profile.read_save(path)
                (path.parent / 'ORIGINAL.CON').write_bytes(bytes(context.MAX_CONTEXT_SIZE + 1))
                with self.assertRaises(SaveError):
                    profile.read_save(path)

    def test_original_context_and_source_races_retain_completed_frozen_backups(self):
        for target in ('context', 'gameplay'):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as temporary:
                path = _copy(Path(temporary), na)
                document = na.read_save(path)
                original_backup = backend.snapshot_backup

                def replace_after_backup(*args, **kwargs):
                    result = original_backup(*args, **kwargs)
                    if target == 'context':
                        (path.parent / 'ORIGINAL.CON').write_bytes(context_fixture(na.GAME_ID, seed=1))
                    else:
                        path.write_bytes(raw_fixture(1))
                    return result

                with mock.patch.object(backend, 'snapshot_backup', side_effect=replace_after_backup):
                    with self.assertRaises(SaveError):
                        na.backup(document)
                backups = list((path.parent / 'UniversalEditorBackups').glob('*.dat'))
                self.assertEqual(len(backups), 1)
                self.assertEqual(backups[0].read_bytes(), document.raw)
                self.assertEqual(json.loads(backups[0].with_suffix('.json').read_bytes())['sha256'], document.sha256)

    def test_foreign_context_collision_and_changed_backup_files_are_never_deleted(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = _copy(Path(temporary), na)
            document = na.read_save(path)
            foreign = b'Another application created this context file.'

            def collide(_data, destination):
                destination.write_bytes(foreign)
                raise FileExistsError('The context path was occupied during backup creation.')

            with mock.patch.object(backend, 'atomic_new', side_effect=collide):
                with self.assertRaises(FileExistsError):
                    na.backup(document)
            backups = list((path.parent / 'UniversalEditorBackups').glob('*.dat'))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_bytes(), document.raw)
            self.assertEqual(backups[0].with_name(backups[0].name + '.context.json').read_bytes(), foreign)
        for target in ('gameplay', 'manifest'):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as temporary:
                path = _copy(Path(temporary), na)
                document = na.read_save(path)
                original_backup, changed_path = backend.snapshot_backup, []
                foreign = b'Another application replaced this completed backup.'

                def replace_created(*args, **kwargs):
                    result = original_backup(*args, **kwargs)
                    destination = result if target == 'gameplay' else result.with_suffix('.json')
                    destination.write_bytes(foreign)
                    changed_path.append(destination)
                    return result

                with mock.patch.object(backend, 'snapshot_backup', side_effect=replace_created):
                    with self.assertRaises(SaveError):
                        na.backup(document)
                self.assertEqual(len(changed_path), 1)
                self.assertEqual(changed_path[0].read_bytes(), foreign)


class Xbox360DW6NativeTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('DW6_XBOX360_SAVE_COPIES'), 'Native extracted Xbox 360 copies with ORIGINAL.CON not supplied.')
    def test_original_native_context_hashes_payloads_and_complete_noop_snapshots(self):
        paths = [Path(value) for value in os.environ['DW6_XBOX360_SAVE_COPIES'].split(os.pathsep)]
        for path in paths:
            profile = na if path.name == na.FILENAME else eu
            with self.subTest(reference=path.parent.name):
                before = hashlib.sha256(path.read_bytes()).hexdigest()
                document = profile.read_save(path)
                self.assertEqual(context.extract_payload(profile.context_raw(path), profile.GAME_ID), document.raw)
                self.assertEqual(profile.serialize(document, {}), document.raw)
                self.assertEqual(document.sha256, before)
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)

    @unittest.skipUnless(os.environ.get('DW6_XBOX360_SAVE_COPIES') and os.environ.get('DW6_SAVE')
                         and os.environ.get('DW6_PS3_SAVE_COPIES') and os.environ.get('DW6_PS3_JP_SAVE')
                         and os.environ.get('DW6_PS3_EU_SAVE_COPIES'), 'Native PC/US/European/Japanese PS3 and original Xbox 360 copies not all supplied.')
    def test_all_native_xbox_states_to_pc_and_all_new_regional_directions(self):
        from koei_editor import conversion as c
        xbox = [Path(value) for value in os.environ['DW6_XBOX360_SAVE_COPIES'].split(os.pathsep)]
        original_paths = {'dw6': Path(os.environ['DW6_SAVE']),
                          'dw6_ps3': Path(os.environ['DW6_PS3_SAVE_COPIES'].split(os.pathsep)[0]),
                          'dw6_ps3_jp': Path(os.environ['DW6_PS3_JP_SAVE']),
                          'dw6_ps3_eu': Path(os.environ['DW6_PS3_EU_SAVE_COPIES'].split(os.pathsep)[0])}
        for profile in (na, eu):
            original_paths[profile.GAME_ID] = next(path for path in xbox if path.name == profile.FILENAME)
        originals = set(xbox) | set(original_paths.values())
        before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in originals}

        def copy_native(path, game_id, folder):
            endpoint = c.ENDPOINTS[game_id]
            folder.mkdir(parents=True)
            destination = folder / endpoint.filename
            destination.write_bytes(path.read_bytes())
            if endpoint.companion:
                (folder / endpoint.companion).write_bytes((path.parent / endpoint.companion).read_bytes())
            return destination

        # Every original extracted state is exercised in all four scopes. The
        # 81 packages include 40 distinct gameplay states, not 81 independent players.
        for index, path in enumerate(xbox):
            game_id = na.GAME_ID if path.name == na.FILENAME else eu.GAME_ID
            with self.subTest(reference=index), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                source = copy_native(path, game_id, root / 'source')
                template = copy_native(original_paths['dw6'], 'dw6', root / 'template')
                for variant in ('', 'progress', 'campaigns', 'records'):
                    suffix = '-' + variant if variant else ''
                    route = c.get_route(game_id + '-to-dw6' + suffix)
                    _export_and_reverse(self, route, source, template, root / (variant or 'roster'))
        # Both Xbox regions and all four PC/PS3 templates, including every
        # directed region pair, have actual native read-back and exact reverses.
        routes = [route for route in c.ROUTES if na.GAME_ID in (route.source_id, route.target_id)
                  or eu.GAME_ID in (route.source_id, route.target_id)]
        self.assertEqual(len(routes), 72)
        for route in routes:
            with self.subTest(route=route.id), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                source = copy_native(original_paths[route.source_id], route.source_id, root / 'source')
                template = copy_native(original_paths[route.target_id], route.target_id, root / 'template')
                _export_and_reverse(self, route, source, template, root)
        self.assertEqual(before, {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in originals})


class Xbox360DW6ConversionTests(unittest.TestCase):
    def test_all_new_routes_actual_exports_semantic_values_and_preserved_remainder(self):
        from koei_editor import conversion as c
        from tests.test_conversion import write_copy
        routes = [route for route in c.ROUTES if na.GAME_ID in (route.source_id, route.target_id)
                  or eu.GAME_ID in (route.source_id, route.target_id)]
        self.assertEqual(len(routes), 72)
        for route in routes:
            with self.subTest(route=route.id), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                source = write_copy(root / 'source', route.source_id)
                template = write_copy(root / 'template', route.target_id, 1)
                _export_and_reverse(self, route, source, template, root)

    def test_changed_original_context_and_destination_readback_are_refused(self):
        from koei_editor import conversion as c
        from tests.test_conversion import write_copy
        for during in ('source-context', 'destination-readback'):
            with self.subTest(during=during), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                source = write_copy(root / 'source', 'dw6')
                template = write_copy(root / 'template', na.GAME_ID, 1)
                reviewed = c.prepare('dw6-to-' + na.GAME_ID + '-records', source, template)
                original_read, touched = na.read_save, []

                def raced_read(path, *args, **kwargs):
                    if Path(path).parent == root / 'output' and not touched:
                        touched.append(True)
                        if during == 'source-context':
                            (template.parent / 'ORIGINAL.CON').write_bytes(context_fixture(na.GAME_ID, seed=2))
                        else:
                            (Path(path).parent / 'ORIGINAL.CON').write_bytes(context_fixture(na.GAME_ID, seed=3))
                    return original_read(path, *args, **kwargs)

                with mock.patch.object(na, 'read_save', side_effect=raced_read):
                    with self.assertRaises(SaveError):
                        c.export(reviewed, root / 'output')
                self.assertTrue(touched)
                self.assertFalse((root / 'output' / 'conversion.json').exists())
                if during == 'destination-readback':
                    # Failed export rollback must preserve the foreign context.
                    self.assertEqual((root / 'output' / 'ORIGINAL.CON').read_bytes(), context_fixture(na.GAME_ID, seed=3))


if __name__ == '__main__':
    unittest.main()
