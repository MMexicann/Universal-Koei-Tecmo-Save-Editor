# TRINITY: Souls of Zill O'll — US PS3

This independently authored published-format profile supports copied decrypted
US BLUS30503 `PLAY.DAT` files with their unchanged original `PARAM.SFO`. It
reduces spendable money and provides searchable read-only inspection of the
published SP word and individually mapped Areus, Dagda and Selene HP/Attack/
Defense/SPR/MAG words. Shared Undo, Review Changes, automatic backups, safe Save
As and paired-context restore remain available. Console re-encryption and
resigning are an external Apollo workflow.

## Original source and genuine export

TRINITY is an Omega Force action RPG published by Koei Tecmo. The complete
[US Apollo/Game Genie title patch](https://github.com/bucanero/apollo-patches/blob/master/PS3/BLUS30503.savepatch)
and [EU](https://github.com/bucanero/apollo-patches/blob/master/PS3/BLES01184.savepatch)/
[Japanese](https://github.com/bucanero/apollo-patches/blob/master/PS3/BLJM60212.savepatch)
source explicitly target `PLAY.DAT`. The original author identifies all three
regional titles and the published disk money mapping is a big-endian DWORD at
`0x58`. These are factual maps, independently implemented without copying the
GPL patch interpreter, external assets or catalogs.

The complete actual [Apollo PS3 disk workflow](https://github.com/bucanero/apollo-ps3/blob/master/source/exec_cmd.c)
was inspected, not only these offsets: `apply_cheat_patches` decrypts the title
protected file, applies the active Game Genie operation through
`apollo_apply_code`, then re-encrypts the modified file. `resignSave` updates
external `PARAM.PFD` authentication. The full
[interpreter](https://github.com/bucanero/apollo-lib/blob/master/source/patches.c)
reads the entire file, applies its bounded writes and emits the full buffer via
`write_buffer`. The complete TRINITY patch contains no internal-checksum
repair. This confirms an actual published title-specific money writer, but
**does not establish that the game lacks internal integrity or that our edited
file has been loaded in the game**. `INTEGRITY_KIND='external'`,
`sample_verified=False`, `editing_verified=False` and `published_format=True`
make that scope explicit. CLI checks never report verified native integrity.

A genuinely shared player export from
[GameFAQs save 24026](https://gamefaqs.gamespot.com/ps3/960454-trinity-souls-of-zill-oll/saves/24026)
contains original `BLUS30503-PLAY02` metadata and complete protected `PLAY.DAT`.
The uploader describes an early-game save with near-max gold, max SP and edited
equipment. It was decrypted privately using the original console metadata and
published title secure-file key, without executing a game/editor binary. The
complete decrypted file has 699,376 (`0xAABF0`) bytes. Its first big-endian DWORD
is that exact file size; the next DWORD is `0x10111900`, an observed native
layout marker rather than an invented release-version name. The opened money
is 9,963,979 and the published SP word is 99,999. Original player files, account
context, icons and equipment data are not distributed. Modified genuine
progression does not establish clean earned-state limits or natural caps.
Only US BLUS30503 is admitted; regional source statements alone do not create
EU/Japanese support without native qualification.

## Qualified editing and inspection

| System | Explicit published map | Scope |
| --- | --- | --- |
| Spendable money | `0x58`, BE32 | Reduce between zero and the opened balance; preserve original higher values |
| SP storage | `0x6C`, BE32 | Searchable read-only; exact pool ownership and spending consequences need proof |
| Areus stat words | BE16 at `0x72`, `0x76`, `0x7A`, `0x7E`, `0x82` | Named read-only HP/Attack/Defense/SPR/MAG words |
| Dagda stat words | BE16 at `0x24A`, `0x24E`, `0x252`, `0x256`, `0x25A` | Named read-only words; original patch's repeated Areus Defense heading is corrected to its surrounding Dagda record |
| Selene stat words | BE16 at `0x422`, `0x426`, `0x42A`, `0x42E`, `0x432` | Named read-only words |

The associated public
[runtime codelist](https://github.com/aldostools/webMAN-MOD/blob/master/_Projects_/codelists/Trinity%20Souls%20Of%20Zill%20O'll%20BLUS30503%2001.00.ncl)
distinguishes buying with money, exchanging casino coins for prizes, SP items
that grant 100/500/1000/2000 points, and separate EXP/level-on-kill behavior.
Those are separate systems, not interchangeable counters. Runtime facts do
not qualify additional disk offsets or native array ownership. The stat-word
maps similarly do not distinguish permanent bases, current gauges, equipment
bonuses or recalculated values, so no stat writer is exposed. Three individually
named records are inspected without extrapolating a character stride.

The published money target 9,999,999 is not promoted to a natural gameplay
maximum. Max is disabled. Assigning the opened money amount removes a staged
edit, including unusual higher balances. Only the four money bytes may change;
all inventory, stat, learned-skill, story, casino, unknown header and tail bytes
remain intact. No checksum is invented or damaged input normalized.

Exact full length, observed framing and required title/PLAY-slot metadata gate
input; foreign/unsupported title identities, encrypted files and malformed
sizes are rejected. Internal integrity remains unresolved, so arbitrary
non-header corruption cannot be detected and is not claimed. The entire
unchanged raw buffer roundtrips byte for byte.

## Safety and coverage checklist

- [x] Complete title money writer trace, actual US native file and no-op qualification.
- [x] All-money-byte surgical checks and unknown/full-tail preservation on native and procedural files.
- [x] Published SP storage and fifteen named stat-word inspectors, without derived-value writes.
- [x] Strict title/PLAY identity, size/framing, forged documents, field bounds and no-Max preservation.
- [x] Full bounded original-SFO digest checked during opening and before backups/final Save As.
- [x] Backup manifest pairs original context SHA256 with full native save SHA256; context substitution and paired-backup mismatch are rejected.
- [x] Actual Tk open/search/edit/Review/Undo/no-Max/Save As, backup restore and copied-save CLI.
- [ ] SP writes: require demonstrated current spendable pool versus history and exact
      ownership/shared-pool rules; no additional character SP offsets are inferred.
- [ ] Stat/HP writes: require base/current/equipment/derived separation and gauge constraints.
- [ ] Skills/classes: need learned and equipped IDs, purchase prerequisites and upgrade consequences.
- [ ] EXP/levels: need coherent progression thresholds, class growth and level-up rewards.
- [ ] Equipment/basket/storage: need qualified record types, ownership, inventory capacity and equipment references.
- [ ] Casino coins: public runtime lead exists, but no native disk mapping is established.
- [ ] Campaign/quests/collections: need actual stored flags and prerequisite/reward dependencies.
- [ ] EU/Japanese layouts and additional revisions: need original native gameplay exports.
- [ ] Internal integrity and edited-game load/re-save acceptance: no independent proof yet.

Private `TRINITY_PS3_COPIES` selects the extracted genuine export for
`tests.test_trinity_ps3`. Tests distinguish procedural buffers, genuine file
observations and unperformed game-load validation. Local copied-save CLI
privately copies the original bounded `PARAM.SFO` opaquely and never fabricates
console metadata or signs saves.
