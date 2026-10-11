"""Supported game/platform inventory, derived from the executable registry.

Add adapters to game_registry.GAMES, then run:
    python -m tools.update_supported_games
This updates the readable index below, docs/SUPPORTED_GAMES.md and README.
Research-only codecs never become supported entries through documentation.
"""
from dataclasses import dataclass

from .game_registry import GAMES


# BEGIN GENERATED SUPPORTED GAME INDEX
# dw3: DYNASTY WARRIORS 3 / Complete Edition Remastered [Windows PC]
# dw8xl: DYNASTY WARRIORS 8 / Xtreme Legends Complete Edition · PC [Windows PC]
# dw7xl: DYNASTY WARRIORS 7 / Xtreme Legends Definitive Edition · PC [Windows PC]
# pw3: ONE PIECE: PIRATE WARRIORS 3 / Windows PC edition [Windows PC]
# pw4: ONE PIECE: PIRATE WARRIORS 4 / Windows PC · WW/JP/EA revision 15 [Windows PC]
# dw4hyper: DYNASTY WARRIORS 4 HYPER / Native Windows PC edition [Windows PC]
# atelier_sophie2: ATELIER SOPHIE 2 / The Alchemist of the Mysterious Dream · PC [Windows PC]
# atelier_sophie: ATELIER SOPHIE / Original Steam PC · GAMEDATA slots [Windows PC]
# atelier_ryza2: ATELIER RYZA 2 / Lost Legends & the Secret Fairy · original Steam PC [Windows PC]
# meruru_plus_vita: ATELIER MERURU PLUS / The Apprentice of Arland · US decrypted PCSE00296 [PlayStation Vita]
# fatal_frame2_remake: FATAL FRAME II / Crimson Butterfly REMAKE · Steam PC [Windows PC]
# dw4xl_ps2: DYNASTY WARRIORS 4 / Xtreme Legends · SLUS-20812 [PlayStation 2]
# origins: DYNASTY WARRIORS: ORIGINS / Steam PC · slot saves [Windows PC]
# wo3u: WARRIORS OROCHI 3 ULTIMATE / Definitive Edition · PC [Windows PC]
# wo1: WARRIORS OROCHI / Original Windows PC · save revision 2 [Windows PC]
# samurai4dx: SAMURAI WARRIORS 4 DX / Windows PC edition [Windows PC]
# sw4ii: SAMURAI WARRIORS 4-II / Windows PC edition [Windows PC]
# sw2: SAMURAI WARRIORS 2 / Original Windows PC · save revision 2 [Windows PC]
# dw6: DYNASTY WARRIORS 6 / Native Windows PC edition [Windows PC]
# dw9emp: DYNASTY WARRIORS 9 EMPIRES / Windows PC · SYSTEMDATA [Windows PC]
# orochiz: WARRIORS OROCHI Z / Native Windows PC edition [Windows PC]
# stars: WARRIORS ALL-STARS / Windows PC · revision F4 [Windows PC]
# hyrule_warriors: HYRULE WARRIORS / Wii U · APP.BIN [Wii U]
# hyrule_definitive: HYRULE WARRIORS / Definitive Edition · zmha.bin [Nintendo Switch]
# age_of_calamity: HYRULE WARRIORS: AGE OF CALAMITY / Switch · svdt [Nintendo Switch]
# fire_emblem_warriors: FIRE EMBLEM WARRIORS / Switch · scenario0/1/2 exports [Nintendo Switch]
# dw7_ps3: DYNASTY WARRIORS 7 / US/EU · decrypted APP.BIN [PlayStation 3]
# dw7e_ps3: DYNASTY WARRIORS 7 EMPIRES / US · decrypted SYSTEM DATA.BIN [PlayStation 3]
# sw4_ps3: SAMURAI WARRIORS 4 / US · decrypted DATA.BIN [PlayStation 3]
# dw8e: DYNASTY WARRIORS 8 EMPIRES / Windows PC · SystemSave.dat [Windows PC]
# wolong: WO LONG: FALLEN DYNASTY / Windows PC · USERDATA [Windows PC]
# p5strikers_pc: PERSONA 5 STRIKERS / Windows PC · SAVEDATA.BIN [Windows PC]
# hyrule_legends: HYRULE WARRIORS LEGENDS / Nintendo 3DS · zmha.bin [Nintendo 3DS]
# ayesha_ps3: ATELIER AYESHA / The Alchemist of Dusk · PS3 US/Japanese export [PlayStation 3]
# dw5special: DYNASTY WARRIORS 5 SPECIAL / Shin Sangokumusou 4 Special · Windows PC [Windows PC]
# three_hopes: FIRE EMBLEM WARRIORS: THREE HOPES / Switch · extracted SlotData exports [Nintendo Switch]
# dw8e_ps3: DYNASTY WARRIORS 8 EMPIRES / US · decrypted SYSTEM APP.BIN [PlayStation 3]
# wo3u_ps3: WARRIORS OROCHI 3 ULTIMATE / US · decrypted APP.BIN · NPUB31505 [PlayStation 3]
# nioh3: NIOH 3 / Windows PC · USER revisions 0x01030001 / 0x01040000 [Windows PC]
# ninjagaiden2_x360: NINJA GAIDEN II / Original Xbox 360 / Xenia · extracted revision-6 story [Xbox 360 / Xenia]
# gundam1_ps3: DYNASTY WARRIORS: GUNDAM / US/EU · decrypted DATA.BIN + PARAM.SFO [PlayStation 3]
# kens_rage1_ps3: FIST OF THE NORTH STAR: KEN'S RAGE / US/EU · decrypted DATA.BIN + PARAM.SFO [PlayStation 3]
# kens_rage2_ps3: FIST OF THE NORTH STAR: KEN'S RAGE 2 / EU · decrypted DATA.BIN + PARAM.SFO [PlayStation 3]
# rotk13_pc: ROMANCE OF THE THREE KINGDOMS XIII / Original PC · revision 14 · TC [Windows PC]
# three_houses: FIRE EMBLEM: THREE HOUSES / Switch · gameplay save-format v13/v23 [Nintendo Switch]
# END GENERATED SUPPORTED GAME INDEX


@dataclass(frozen=True)
class SupportedGame:
    id: str
    title: str
    edition: str
    platform: str
    features: str
    genuine_file_verified: bool


SUPPORTED_GAMES = tuple(
    SupportedGame(game.id, game.title, game.subtitle, game.platform,
                  game.description, game.editing_verified)
    for game in GAMES
)


def markdown_table() -> str:
    """Render the same supported inventory for contributors and the README."""
    lines = [
        '| Game / edition | Platform | Implemented scope |',
        '| --- | --- | --- |',
    ]
    for game in SUPPORTED_GAMES:
        title = f'{game.title} — {game.edition}' if game.edition else game.title
        values = (title, game.platform, game.features)
        lines.append('| ' + ' | '.join(value.replace('|', r'\|') for value in values) + ' |')
    return '\n'.join(lines) + '\n'
