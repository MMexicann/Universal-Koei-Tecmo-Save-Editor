# Pirate Warriors edition and platform scope

This note records officially released editions and separates that product
evidence from native save-format qualification. Store listings establish that a
port exists; they do not establish its save path, layout, checksum, encryption,
or compatibility with another edition. No additional writer is enabled here.

## Current editor boundaries

| Game and edition | Existing editor scope | Other confirmed editions that need their own qualification |
| --- | --- | --- |
| Pirate Warriors 1 | Original US PSN PS3 export `NPUB30836-00`; decrypted `DATA.BIN` and unchanged `PARAM.SFO`. | No other edition is covered by this profile. |
| Pirate Warriors 2 | Original EU PSN PS3 export `NPEB01795-00`; decrypted `DATA.BIN` and unchanged `PARAM.SFO`. | No other edition is covered by this profile. |
| Pirate Warriors 3 | Windows PC `OP3WIN0000.dat`; plus the separately registered original EU PSN PS3 export `NPEB02211-00`. | PlayStation 4, PlayStation Vita and Nintendo Switch require platform-specific save qualification. Other PS3 regions also need exact title IDs and native samples. |
| Pirate Warriors 4 | Windows PC revision 15, one-step WW/JP/EA region family. The `pw4` editor maps spendable Beli and quantities in already obtained coins. | PlayStation 4, Xbox One and Nintendo Switch; the PlayStation 5, Xbox Series X|S and Nintendo Switch 2 upgrades need platform-specific qualification. A separate PC revision-22 profile is also outside the revision-15 editor. |

Bandai Namco's 2015 announcement lists PW3 for PS4, PS3 and Vita; the publisher's
Steam listing and Nintendo's Switch listing establish its PC and Switch editions.
The publisher's PW4 announcement lists the original PS4, Xbox One, Switch and
Steam editions, then the PS5, Xbox Series X|S and Switch 2 upgrades, released
November 21, 2025. Nintendo describes its Switch 2 edition as an upgrade with
no game-content change. Neither source identifies native save bytes or promises
save-format compatibility, so the edition list is a research queue rather than
editor support. Sources: [PlayStation Blog on PW3 platforms](https://blog.playstation.com/archive/2015/03/30/one-piece-pirate-warriors-3-coming-ps4-ps3-ps-vita-summer),
[PW3 on Steam](https://store.steampowered.com/app/331600/OnePiecePirateWarriors3/),
[PW3 Deluxe Edition on Nintendo Switch](https://www.nintendo.com/us/store/products/one-piece-pirate-warriors-3-deluxe-edition-switch/),
[Bandai Namco's PW4 platform announcement](https://www.bandainamcoent.com/news/one-piece-pirate-warriors-4-sets-sail-on-new-gen-platforms-available-now),
and [Nintendo's PW4 Switch 2 Edition description](https://www.nintendo.com/us/store/products/one-piece-pirate-warriors-4-nintendo-switch-2-edition-switch-2/).

## Evidence needed before another writer

For each candidate platform and regional title, retain a complete unmodified
save copy with its original filename and the identifying context the platform
requires. Record title ID or application ID, region, game version, DLC, export
method and any companion metadata. Keep encrypted containers and signing context
outside the editor unless the container layer itself is separately qualified.

Before adding fields, establish a byte-exact unchanged roundtrip and identify
every native integrity check. A controlled before/after pair should change one
displayed value at a time. For PW3, useful pairs include one character stat,
level/EXP, costume selection, coin or medal count, and one stage reward. For
PW4, useful pairs include Beli spend, an already obtained coin quantity, a
Growth or Soul Map purchase, skill/equipment change and a stage reward. Keep
ownership and reward claims separate from quantities and equipped references.

For PW4 revision 22, include complete slots from the exact build and region,
the matching `OP4WINUSER.dat` where applicable, and a revision-15 control if
qualifying a migration path. For each console generation, keep separate copies
from before and after a native action; do not test them with the PC parser. An
upgrade from an older console version is a lead to investigate, not evidence
that the underlying save representation is shared.

An editor addition still needs a qualified parser and serializer, corruption
and boundary checks, surgical-byte-preservation tests, safe copied-save writes,
and a native reopen. Actual in-game loading and re-saving remains a separate
validation result. No player saves, platform account data, executables or
extracted game assets belong in the repository.
