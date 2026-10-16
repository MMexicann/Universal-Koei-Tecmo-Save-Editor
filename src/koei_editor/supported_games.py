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
# dw7xl_ps3: DYNASTY WARRIORS 7 / Xtreme Legends · original US/EU PS3 [PlayStation 3]
# pw3: ONE PIECE: PIRATE WARRIORS 3 / Windows PC edition [Windows PC]
# pw4: ONE PIECE: PIRATE WARRIORS 4 / Windows PC · WW/JP/EA revision 15 [Windows PC]
# dw4hyper: DYNASTY WARRIORS 4 HYPER / Native Windows PC edition [Windows PC]
# atelier_sophie2: ATELIER SOPHIE 2 / The Alchemist of the Mysterious Dream · PC [Windows PC]
# atelier_sophie2_ps4: ATELIER SOPHIE 2 / The Alchemist of the Mysterious Dream · PS4 CUSA28451 app 1.0 [PlayStation 4]
# totori_ps3: ATELIER TOTORI / The Adventurer of Arland · original PS3 US/EU [PlayStation 3]
# meruru_ps3: ATELIER MERURU / The Apprentice of Arland · original US PS3 [PlayStation 3]
# rorona_ps3: ATELIER RORONA / The Alchemist of Arland · original US PS3 [PlayStation 3]
# atelier_sophie: ATELIER SOPHIE / Original Steam PC · GAMEDATA slots [Windows PC]
# atelier_ryza2: ATELIER RYZA 2 / Lost Legends & the Secret Fairy · original Steam PC [Windows PC]
# nights_azure2_switch: NIGHTS OF AZURE 2 / Bride of the New Moon · original Switch English Chapter 1/7/Clear profiles [Nintendo Switch]
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
# dw6_ps3: DYNASTY WARRIORS 6 / Original US PS3 · BLUS30110 · APP.BIN + PARAM.SFO [PlayStation 3]
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
# deception4_ps3: DECEPTION IV: BLOOD TIES / Original US PS3 PSN · NPUB31442 [PlayStation 3]
# escha_logy_ps3: ATELIER ESCHA & LOGY / Original EU PS3 PSN · NPEB01945 [PlayStation 3]
# ar_tonelico_qoga_ps3: AR TONELICO QOGA / Knell of Ar Ciel · original US PS3 · BLUS30639 [PlayStation 3]
# ayesha_ps3: ATELIER AYESHA / The Alchemist of Dusk · PS3 US/Japanese export [PlayStation 3]
# dw5special: DYNASTY WARRIORS 5 SPECIAL / Shin Sangokumusou 4 Special · Windows PC [Windows PC]
# three_hopes: FIRE EMBLEM WARRIORS: THREE HOPES / Switch · extracted SlotData exports [Nintendo Switch]
# dw8e_ps3: DYNASTY WARRIORS 8 EMPIRES / US · decrypted SYSTEM APP.BIN [PlayStation 3]
# wo3u_ps3: WARRIORS OROCHI 3 ULTIMATE / US · decrypted APP.BIN · NPUB31505 [PlayStation 3]
# nioh3: NIOH 3 / Windows PC · USER revisions 0x01030001 / 0x01040000 [Windows PC]
# ninjagaiden2_x360: NINJA GAIDEN II / Original Xbox 360 / Xenia · extracted revision-6 story [Xbox 360 / Xenia]
# gundam1_ps3: DYNASTY WARRIORS: GUNDAM / US/EU · decrypted DATA.BIN + PARAM.SFO [PlayStation 3]
# gundam_reborn_ps3: DYNASTY WARRIORS: GUNDAM REBORN / EU/Japan · decrypted DATA.BIN + original PARAM.SFO [PlayStation 3]
# gundam3_ps3: DYNASTY WARRIORS: GUNDAM 3 / US · decrypted DATA.BIN + original PARAM.SFO [PlayStation 3]
# trinity_ps3: TRINITY: SOULS OF ZILL O'LL / US · decrypted PLAY.DAT + original PARAM.SFO [PlayStation 3]
# ninja_gaiden_black_xbox: NINJA GAIDEN BLACK / Original Xbox · SYSTEM.dat + original console EEPROM [Original Xbox]
# kens_rage1_ps3: FIST OF THE NORTH STAR: KEN'S RAGE / US/EU · decrypted DATA.BIN + PARAM.SFO [PlayStation 3]
# kens_rage2_ps3: FIST OF THE NORTH STAR: KEN'S RAGE 2 / EU · decrypted DATA.BIN + PARAM.SFO [PlayStation 3]
# rotk13_pc: ROMANCE OF THE THREE KINGDOMS XIII / Original PC · revision 14 · TC [Windows PC]
# three_houses: FIRE EMBLEM: THREE HOUSES / Switch · gameplay save-format v13/v23 [Nintendo Switch]
# berserk_vita: BERSERK AND THE BAND OF THE HAWK / EU PS Vita · decrypted PCSB01085 [PlayStation Vita]
# doa5_ps3: DEAD OR ALIVE 5 / Original US/EU PS3 PSN · SAVE_SYS.DAT + PARAM.SFO [PlayStation 3]
# pokemon_conquest_ds: POKÉMON CONQUEST / US Nintendo DS · raw native save [Nintendo DS]
# atelier_ryza_switch: ATELIER RYZA / Ever Darkness & the Secret Hideout · original Switch main game [Nintendo Switch]
# dw8xl_ps3: DYNASTY WARRIORS 8 / Xtreme Legends · US PS3 PSN NPUB31449 · APP.BIN + PARAM.SFO [PlayStation 3]
# dqb2_pc: DRAGON QUEST BUILDERS 2 / Original Steam PC · CMNDAT.BIN [Windows PC]
# atelier_ryza2_switch: ATELIER RYZA 2 / Lost Legends & the Secret Fairy · original Switch [Nintendo Switch]
# dqb2_switch: DRAGON QUEST BUILDERS 2 / Original Nintendo Switch · CMNDAT.BIN [Nintendo Switch]
# p5strikers_switch: PERSONA 5 STRIKERS / English Nintendo Switch · savedata export [Nintendo Switch]
# rotk2_dos: ROMANCE OF THE THREE KINGDOMS II / Original Chinese DOS · raw save copies [DOS PC]
# p5strikers_ps4: PERSONA 5 STRIKERS / English PS4 · decrypted APP.BIN + original sce_sys/param.sfo [PlayStation 4]
# uncharted_waters2_dos: UNCHARTED WATERS: NEW HORIZONS / Original English DOS · KOUKAI2.DAT [DOS PC]
# reko3_dos: ROMANCE OF THE THREE KINGDOMS: LEGEND OF LIU BEI / Original Traditional Chinese DOS · MSAVE0–4.R3S [DOS PC]
# rotk3_dos: ROMANCE OF THE THREE KINGDOMS III / Original Traditional Chinese DOS · SANGOKU3.SAV [DOS PC]
# nobu6_pk_pc: NOBUNAGA'S AMBITION: TENSHOUKI / Original Japanese Windows Power-Up Kit · SAVEDAT.n6p [Windows PC]
# project_zero_ps2: PROJECT ZERO / FATAL FRAME / Original European PS2 · SLES-50821 PSU export [PlayStation 2]
# atelier_ryza3_dx_pc: ATELIER RYZA 3 DX / Alchemist of the End & the Secret Key · Steam PC revision 4 [Windows PC]
# monster_rancher_ds: MONSTER RANCHER DS / US Nintendo DS · raw 32/64 KiB export [Nintendo DS]
# tecmo_super_bowl_nes: TECMO SUPER BOWL / NES · compatible original 28-team battery SRAM [NES]
# wo4_pc: WARRIORS OROCHI 4 / Original Windows PC · revision 20180720 [Windows PC]
# wo4_ultimate: WARRIORS OROCHI 4 ULTIMATE / Windows PC · revision 20200101 [Windows PC]
# samurai5_pc: SAMURAI WARRIORS 5 / Windows PC · revision 39 castle/menu slot zero [Windows PC]
# abyss_pc: WARRIORS: ABYSS / Windows PC · revision A4 gameplay slots [Windows PC]
# bandit_kings_mac: BANDIT KINGS OF ANCIENT CHINA / Original English Macintosh · SUI0/SUI1 data forks [Macintosh]
# nobunaga_ambition_nes: NOBUNAGA'S AMBITION / Original English NES · 17-fief battery profile [NES]
# gemfire_nes: GEMFIRE / NES · native structurally qualified battery records [NES]
# gemfire_snes: GEMFIRE / SNES · native structurally qualified battery records [SNES]
# bladestorm_ps3: BLADESTORM: THE HUNDRED YEARS’ WAR / Original EU BLES00113 · decrypted PLAYDATA + PARAM.SFO [PlayStation 3]
# atelier_firis_pc: ATELIER FIRIS / The Alchemist and the Mysterious Journey · original Steam PC [Windows PC]
# blue_reflection_second_light_pc: BLUE REFLECTION: SECOND LIGHT / Original Steam PC · native tagged gameplay profile [Windows PC]
# atelier_ryza_pc: ATELIER RYZA / Ever Darkness & the Secret Hideout · original Steam PC [Windows PC]
# dw8xl_vita: DYNASTY WARRIORS 8 / Xtreme Legends Complete Edition · plaintext Vita revision 0x131002F0 [PlayStation Vita]
# pw1_ps3: ONE PIECE: PIRATE WARRIORS / Original US PSN NPUB30836 · DATA.BIN + PARAM.SFO [PlayStation 3]
# pw2_ps3: ONE PIECE: PIRATE WARRIORS 2 / Original EU PSN NPEB01795 · DATA.BIN + PARAM.SFO [PlayStation 3]
# pw3_ps3: ONE PIECE: PIRATE WARRIORS 3 / Original EU PSN NPEB02211 · DATA.BIN + PARAM.SFO [PlayStation 3]
# dw8_ps3: DYNASTY WARRIORS 8 / Original US PSN NPUB31234 · plaintext APP.BIN + PARAM.SFO [PlayStation 3]
# aot1_vita: ATTACK ON TITAN / A.O.T. WINGS OF FREEDOM / Original EU PCSB00898 · app0000.dat + sce_sys/param.sfo [PlayStation Vita]
# troy_ps3: WARRIORS: LEGENDS OF TROY / Original EU PS3 · revision-38 populated PROFILE [PlayStation 3]
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


def markdown_table(games=None) -> str:
    """Render the supported inventory, optionally restricted to one platform."""
    lines = [
        '| Game / edition | Platform | Implemented scope |',
        '| --- | --- | --- |',
    ]
    for game in SUPPORTED_GAMES if games is None else games:
        title = f'{game.title} — {game.edition}' if game.edition else game.title
        values = (title, game.platform, game.features)
        lines.append('| ' + ' | '.join(value.replace('|', r'\|') for value in values) + ' |')
    return '\n'.join(lines) + '\n'
