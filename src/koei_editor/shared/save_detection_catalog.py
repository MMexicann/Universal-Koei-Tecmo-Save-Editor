"""Small reviewed Steam identity/location hints, never a parser autodetector.

Paths are factual public references, independently followed by native qualification
of each captured copy. Unsupported locations/editions are deliberately absent.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class DetectionProfile:
    game_id: str
    app_id: int
    documents_folder: tuple[str, ...] = ()
    filenames: tuple[str, ...] = ()
    depth: int = 0
    context: tuple[str, ...] = ()
    evidence: str = ''


REFERENCE = 'https://github.com/mtkennerly/ludusavi-manifest/blob/a6d44cb992e7b737f5cd3fbeadcee186c028a3df/data/manifest.yaml'
# Only these curated facts are used, rather than importing an external catalogue.
# Origins' conflicting Documents references are intentionally not enabled.
PROFILES = (
    DetectionProfile('dw8xl', 278080, ('TecmoKoei', 'Dynasty Warriors 8', 'Savedata'), ('save.dat',), evidence=REFERENCE),
    DetectionProfile('dw7xl', 968790, ('KoeiTecmo', 'Dynasty Warriors 7 DX', 'Savedata'), ('save.dat',), evidence=REFERENCE),
    DetectionProfile('wo3u', 1879330, ('KoeiTecmo', 'WARRIORS OROCHI 3 Ultimate', 'SAVEDATA'), ('SAVEDATA.BIN',), evidence=REFERENCE),
    DetectionProfile('origins', 2384580, filenames=('SLOT000[0-8].dat',), evidence=REFERENCE),
    DetectionProfile('samurai4dx', 2719200, ('KoeiTecmo', 'SAMURAI WARRIORS 4 DX', 'Savedata'), ('*.dat',), evidence=REFERENCE),
    DetectionProfile('sw4ii', 348470, ('KoeiTecmo', 'SAMURAI WARRIORS 4-II', 'Savedata'), ('save.dat',), evidence=REFERENCE),
    DetectionProfile('atelier_sophie2', 1621310, ('KoeiTecmo', 'Atelier Sophie 2'), ('data.dat',), depth=2, evidence=REFERENCE),
    DetectionProfile('samurai5_pc', 1591530, ('KoeiTecmo', 'SAMURAI WARRIORS 5', 'Savedata'), ('*.bin',),
                     depth=2, context=('steam_autocloud.vdf',), evidence=REFERENCE),
)
