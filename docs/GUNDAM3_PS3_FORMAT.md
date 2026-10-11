# Dynasty Warriors: Gundam 3 — US PS3

This scoped published-format editor reduces spendable money in the exact US
BLUS30703 decrypted `DATA.BIN` layout. It includes searchable read-only Mobile
Suit Laboratory EXP and license-bit storage, staged Undo/Review, automatic
backups, context-bound restore and safe Save As. Open separate decrypted copies
beside the unchanged original `PARAM.SFO`; reimport and resign with Apollo for
console use. It does not edit laboratory EXP, licenses, pilot growth or missions.

## Complete source workflow and native observations

The complete [BLUS30703 Game Genie/Apollo title patch](https://github.com/bucanero/apollo-patches/blob/master/PS3/BLUS30703.savepatch)
explicitly writes the big-endian spendable-money DWORD at `0x5353C`. Its two
other independent operations target laboratory EXP at `0x44154` and five
license-bit bytes starting at `0x53547`. The
[EU title patch](https://github.com/bucanero/apollo-patches/blob/master/PS3/BLES01301.savepatch)
independently publishes the same offsets, but no EU native file was qualified
in this round and EU identity is not admitted.

The actual full [Apollo PS3 source workflow](https://github.com/bucanero/apollo-ps3/blob/master/source/exec_cmd.c)
was read, including `apply_cheat_patches` and `resignSave`: it decrypts the
selected title's protected file using its secure-file key, applies each active
Game Genie/BSD patch, re-encrypts the modified file, then performs
`pfd_util_process(PFD_CMD_UPDATE, 0)`. The complete
[Apollo interpreter](https://github.com/bucanero/apollo-lib/blob/master/source/patches.c)
loads the full file, applies the title operation to its bounded buffer and
writes that full buffer back via `write_buffer`. This confirms an existing
actual disk writer for the title's money field, rather than a runtime trainer
or an isolated offset excerpt. The complete title patch has no internal
checksum-repair action. **This does not establish the absence of a game-internal
checksum or edited-game acceptance.** The adapter deliberately declares
`INTEGRITY_KIND='external'`, `sample_verified=False` and registry
`editing_verified=False`, matching the existing published external-integrity
scope. Its CLI never reports verified native integrity. No foreign GPL
interpreter/source code is imported or distributed; format facts were
independently implemented using this project's storage/scalar contract.

Two genuinely shared US player exports were downloaded from
[GameFAQs 23113](https://gamefaqs.gamespot.com/xbox360/605801-dynasty-warriors-gundam-3/saves/23113)
and [21925](https://gamefaqs.gamespot.com/xbox360/605801-dynasty-warriors-gundam-3/saves/21925).
Both original `PARAM.SFO` files identify `BLUS30703-00`; the cross-platform
listing URL's Xbox360 prefix does not determine the actual file platform.
Their complete decrypted `DATA.BIN` files have `0x110000` bytes and identical
leading eleven big-endian DWORDs:
`(0, 11, 0, 78, 125, 73, 560, 560, 512, 38, 53)`.
These are observed framing/layout identifiers, not invented field names or
array ownership claims. The following DWORD differs and remains opaque.
The opened money values differ (5,057,324 and 34,486), independently
corroborating live spendable resource storage. A Japanese `BLJM60300-00`
export was also acquired and inspected; it is deliberately rejected because
a matching title-specific writer was not established here. No player file,
account context, original icons or assets are included in source or releases.

## Editing and mechanics

[Gundam 3's public title source](https://github.com/bucanero/apollo-patches/blob/master/PS3/BLUS30703.savepatch)
distinguishes money from Mobile Suit Lab EXP. Money is a spendable balance;
laboratory EXP, facility upgrades and licenses have their own dependencies.
The [skill guide](https://gamefaqs.gamespot.com/xbox360/605801-dynasty-warriors-gundam-3/faqs/63831) distinguishes Pilot Points from G earned from missions; several skills require level-5 pilot friendship or memorial-mission prerequisites. The [moves guide](https://gamefaqs.gamespot.com/xbox360/605801-dynasty-warriors-gundam-3/faqs/62736) also documents suit-specific friendship/history/online unlock prerequisites. None of those consequences is inferred from wallet storage. The published money cheat's 99,999,999 target is not treated as a natural cap.
The editor therefore permits only reductions from zero to the opened balance,
keeps unusually higher originals intact and supports unstage by assigning the
opened value. Automatic Max is disabled. Laboratory EXP and raw license-bit
storage are searchable inspection only; no rights, plans or ownership are
manufactured.

Only the four money bytes may change. No internal checksum is invented,
normalization is performed, or unknown header/tail byte is altered. No-op
serialization returns the complete original buffer byte for byte. The exact
frame and required title companion reject other revisions, regions, games,
encrypted input and malformed sizes. Since internal integrity is unresolved,
arbitrary non-header corruption cannot be detected and is never claimed to be.

Original bounded `PARAM.SFO` bytes are frozen by SHA256 without parsing account
fields. Opening rereads the context digest; backups/Save As check source bytes
and unchanged context again before atomic writes. Destination context must
match the complete original digest. Each backup's game-specific manifest binds
that context digest to the full save SHA256, preventing accidentally retitled
or cross-context restore. Private local CLI copies preserve the original
context opaquely; no replacement metadata or console-signing file is generated.

## Coverage and remaining inputs

- [x] Actual complete title-specific disk-writer trace and independently authored money reductions.
- [x] Two genuine US native framing/no-op and one-field full-buffer preservation checks.
- [x] Bound scalar CLI accurately reports external/unverified native integrity.
- [x] Actual Tk search/edit/Review/Undo/no-Max/backup/Save As and full context immutability.
- [x] Malformed framing/size/title, forged documents, unknown fields and higher-value preservation.
- [x] Mid-save source/context changes, paired backup/context mismatch and corrupt-backup rejection.
- [ ] Internal gameplay integrity / edited-game load-and-re-save acceptance: need native
      serializer proof or independently verified edited console reimport/load controls.
- [ ] EU/Japanese and other native revisions: need exact title-specific writer plus
      corresponding original export; no regional layout conversion is attempted.
- [ ] Laboratory level/EXP writes: need growth thresholds and upgrade consequences.
- [ ] Licenses versus owned/equipped parts: need independent field identities and
      prerequisites; the broad all-licenses cheat is not copied into the editor.
- [ ] Pilot stats/EXP, friendship and skills: need individually named persistent
      record maps, legitimate growth and equipped/learned dependencies.
- [ ] Plans/parts ranks, purchased upgrades, collection/gallery and mission results:
      no qualified native maps or consequence-safe writers are available here.

For optional private native tests set `GUNDAM3_PS3_COPIES` to the directory with
the separately extracted native GameFAQs archives. Run `tests.test_gundam3_ps3`
under a display. Procedural tests are not player saves and edited-game loading
has not been performed.
