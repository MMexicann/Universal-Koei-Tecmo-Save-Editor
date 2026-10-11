# Original Monster Rancher — PS1 native-save follow-up

The original US Monster Rancher and Monster Rancher 2 remain unregistered.
This round acquired genuine publicly shared DexDrive exports privately and
resolved Monster Rancher 2's complete native byte checksum. A checksum alone
does not provide a usable gameplay editor: exact US save-backed field mappings
and record dependencies are still missing. No player files, card descriptions,
names, save hashes, game assets or external implementations are distributed.

## Acquired native evidence

[LegendCup's public game-save listing](https://legendcup.com/gamesaves.php)
provides the original [Monster Rancher save](https://legendcup.com/dex/monster_rancher.zip),
Monster Rancher 2 [Fenrick save](https://legendcup.com/dex/Fent1.zip), and
[Cocoon save](https://legendcup.com/dex/Cocoon.zip). Only native save members
were extracted; downloaded game or editor executables were never run. These
include community-modified saves, not controlled unmodified action pairs.

The inspected DexDrive files have the `123-456-STD` header, followed by a PS1
card image at offset 3,904. The first allocated directory entry identifies
`BASLUS-00568` for Monster Rancher and `BASLUS-00917` for Monster Rancher 2.
Its native file-size word is 8,192; its allocation-chain terminator is `FFFF`.
The directory's XOR check matches in all three files. Native file data begins
at card offset 8,192 and has the PS1 `SC` icon/title header. Independently
decoded title text distinguishes the original game from Monster Rancher 2.
The larger DexDrive exports are 134,976 bytes; the single-file Cocoon export
is 20,288 bytes. These observations qualify the inspected exports only, not
every arbitrary memory card, region or revision.

## Monster Rancher 2 checksum closure

[Richard Ryley's September 2001 native-save research discussion](https://www.tapatalk.com/groups/monsterrancher4520/anyone-dissected-save-game-files-t2379.html)
explicitly describes editing DexDrive save files, distinguishes them from
GameShark memory edits, and describes his working checksum-updater program.
The checksum is the sum of file bytes, stored as four little-endian bytes at
the end of the file. This is a public native-writer description rather than
an inferred algorithm chosen because one value happens to match.

Both independently acquired US Monster Rancher 2 native files corroborate the
same complete framing and integrity:

```text
native file length: 0x2000
checksum coverage: [0x0000, 0x1FFC)
checksum storage:  little-endian unsigned DWORD at 0x1FFC
algorithm:         unsigned sum of every byte in the covered range
```

Both unchanged checksums match without repairing either input. Independent
private full-buffer checks also changed one arbitrary covered byte and updated
only that byte and the checksum word, then verified the new sum. This proves
the checksum operation and byte preservation; it does not prove that the
arbitrary byte represents money, a stat or any editable gameplay mechanic.
Edited-game load/re-save validation was not performed.

The original Monster Rancher file does **not** satisfy this Monster Rancher 2
checksum. No algorithm, offsets or record geometry are transplanted between
the games. The public [PS1 checksum tool](https://web.save-editor.com/tool/wse_checksum_fix_ps1.html)
lists Japanese Monster Farm as checksum-free and Monster Farm 2 as requiring
a checksum fix. Its processing is an opaque server CGI, with no local client
algorithm. The Japanese title listing does not establish US Monster Rancher
integrity. No player file was uploaded to that service.

## Precise remaining blockers

| Game/platform | Established | Required next |
| --- | --- | --- |
| Monster Rancher 2, US PS1 | Two real title-identified native files; complete native checksum independently corroborated against an actual disk-writer author's description | Recover the author's US native save map or a complete equivalent save writer, proving money and occupied active/frozen monster records separately. The author explicitly says native ordering differs from GameShark addresses. Controlled action pairs can provide equivalent proof. |
| Monster Rancher, US PS1 | Real native card/file framing and US title identity | Complete US native save writer/integrity evidence and persistent gameplay maps. Japanese checksum-free documentation cannot qualify the US file by itself. |

The [historical MR Manager lead](https://www.tapatalk.com/groups/monsterrancher4520/mr2dx-mods-t4017.html)
describes a DOS freezer-copy utility. No usable archived source or complete
US field map was recovered in this pass. Current Advanced Viewer and
Reloaded-II sources operate on running-game memory or their own mod sidecars;
they do not supply an original PS1 native disk serializer. Unavailable source
and opaque online checksum services are recorded as specific blockers rather
than converted into speculative writable controls.

For rich editing, the next proof must distinguish current money, six monster
stats, active/frozen ownership, age versus remaining lifespan, fatigue versus
stress, learned techniques, item stacks and progression/reward prerequisites.
These are investigation categories, not confirmed disk fields. See the
[mechanics checklist](MONSTER_RANCHER_DX_RESEARCH.md) for the underlying
distinctions; DX capacities and offsets remain separate from original PS1.

There is no registered adapter or advertised GUI support for either PS1 title.
Validation here consists of private container/title inspection and the two
Monster Rancher 2 checksum checks, not procedural playable-save generation,
gameplay-field qualification, or edited-game acceptance.
