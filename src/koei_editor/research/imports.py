"""Explicit read-only candidate imports, separate from supported editing games."""
from dataclasses import dataclass
from functools import partial
import hashlib
import json
import stat
from types import MappingProxyType

from koei_editor.games.dw3.models import SaveError
from koei_editor.research.arland_plus_vita import inspector as vita
from koei_editor.research.gundam2_ps3 import inspector as gundam
from koei_editor.research.dk4pk_pc import inspector as dk4
from koei_editor.shared.save_safety import safe_path

WARNING = 'Research only — no editing or game-load qualification.'
MAX_REPORT_BYTES = 65536


@dataclass(frozen=True)
class Candidate:
    id: str
    title: str
    platform: str
    filename: str
    companion: str
    maximum_size: int
    backend: object
    loader: object
    guidance: str

    @property
    def label(self):
        return self.title + ' · ' + self.platform


PROFILES = MappingProxyType({profile.id: profile for profile in (
    Candidate('gundam2_ps3', 'Dynasty Warriors: Gundam 2', 'US/EU PlayStation 3',
              'DATA.BIN', 'PARAM.SFO', gundam.SAVE_SIZE, gundam, gundam.read_save,
              'Revision-13 decrypted BLUS30288/BLES00528 export. Native byte sum and four published pilot records are inspected. Growth/reward dependencies and gameplay writes are unqualified.'),
    *(Candidate(profile.id, profile.title, 'US PlayStation Vita', 'USR-DATA0000',
                'sce_sys/param.sfo', profile.size, vita,
                partial(vita.read_save, profile_id=profile.id),
                'Decrypted ' + profile.title_id + ' export. Exact own-title TLV sections and the uninterpreted tag-3 word are inspected. Native integrity and gameplay meanings remain unqualified.')
      for profile in vita.PROFILES.values()),
    Candidate('dk4pk_pc', 'Uncharted Waters IV with Power-Up Kit', 'Original Windows PC',
              'SaveDat0.DK4', '', dk4.MAX_SIZE, dk4, dk4.read_save,
              'Original-PK observed header/length profiles only. Header word +24 and all gameplay fields remain unclassified. Body corruption may pass framing; no checksum or gameplay qualification is claimed.'),
)})


@dataclass(frozen=True)
class Inspection:
    profile_id: str
    size_bytes: int
    sha256: str
    report_json: str


def get_profile(profile_id):
    if type(profile_id) is not str or profile_id not in PROFILES:
        raise SaveError('Choose an explicit research candidate; no alternate parser will be tried.')
    return PROFILES[profile_id]


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _snapshot(path, maximum_size):
    path = safe_path(path)
    before = path.stat()
    if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= maximum_size:
        raise SaveError('The copied research input exceeds its exact profile bound or is not an ordinary file.')
    with path.open('rb') as stream:
        raw = stream.read(maximum_size + 1)
    after = path.stat()
    if _identity(before) != _identity(after) or not 0 < len(raw) <= maximum_size or len(raw) != after.st_size:
        raise SaveError('The research copy changed during its bounded read. Inspect it again.')
    return raw, _identity(after)


def inspect_copy(profile_id, source):
    """Read an exact candidate without writes, backups, repairs or game probing."""
    profile = get_profile(profile_id)
    source = safe_path(source)
    original, identity = _snapshot(source, profile.maximum_size)
    document = profile.loader(source)
    report = profile.backend.inspect(document)
    current, current_identity = _snapshot(source, profile.maximum_size)
    # Reopening also checks the original console context after report creation.
    if (current != original or current_identity != identity
            or profile.loader(source) != document):
        raise SaveError('The copied gameplay or original metadata changed. Inspect the selected copy again.')
    digest = hashlib.sha256(original).hexdigest()
    if (type(report) is not dict or report.get('profile') != profile_id
            or report.get('read_only') is not True or report.get('registered_editor') is not False
            or report.get('game_load_verified') is not False or report.get('source_sha256') != digest):
        raise SaveError('The candidate did not return its explicit read-only research contract.')
    report = dict(report, research_warning=WARNING)
    encoded = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False)
    if len(encoded.encode('utf-8')) > MAX_REPORT_BYTES:
        raise SaveError('The bounded candidate report is too large to display.')
    return Inspection(profile_id, len(original), digest, encoded)
