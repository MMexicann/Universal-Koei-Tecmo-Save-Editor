# Additional title qualification

The v2.2 release adds three qualified editing title families documented in
[PS3_NEW_FAMILIES.md](PS3_NEW_FAMILIES.md). The additional candidates below remain
**unregistered, read-only research**. They do not add to the 94 supported editor
profiles. No published cheat target, plausible stride or neighbouring edition
is promoted into a safe write without its own evidence.

## Source-only inspection tools

```text
python -m tools.inspect_candidate --profile gundam2_ps3 copied/DATA.BIN
python -m tools.inspect_candidate --profile totori_plus_vita copied/USR-DATA0000
python -m tools.inspect_candidate --profile rorona_plus_vita copied/USR-DATA0000
python -m tools.inspect_candidate --profile ayesha_plus_vita copied/USR-DATA0000
```

The same explicit inspectors are available in the Windows app through
[Research Import](RESEARCH_IMPORT.md), and these development commands remain in
the Source ZIP. They do not add Windows library editors or alternate launchers. Each selects its
exact profile, requires original metadata, reads bounded copies, preserves all
bytes and prints JSON without paths, raw payloads or owner/signing metadata.
They provide no gameplay writer, repair, Max, conversion or file-save operation.

| Candidate | Independently acquired complete evidence | Implemented inspection | Remaining write blocker |
| --- | --- | --- | --- |
| Dynasty Warriors: Gundam 2, US BLUS30288 / EU BLES00528 PS3 | Two US and one EU PFD-decrypted exports; 671,744 bytes; observed revision 13. Japanese revision-12 exports are separately rejected. | Original title/slot metadata; known BE32 byte sum at 0x10 over bytes 0x20 through EOF; four individually published named pilot level-index/point records. | Pilot-specific EXP/level curves, stored/derived growth and reward dependencies; additional record identities; game-load/re-save checks. |
| Atelier Totori Plus, US PCSE00231 Vita | Seven gameplay files from one original decrypted export; 282,624 bytes. | Exact 32-byte prefix, 22 sequential TLV sections and bounded tag-1024 trailer; original PARENT_DIRECTORY context. | Own-title complete disk writer/integrity proof and controlled resource/item actions. |
| Atelier Rorona Plus, US PCSE00466 Vita | Two gameplay files from one original decrypted export; 380,928 bytes. | Exact prefix, 32 sequential TLV sections and bounded trailer; original context. | Own-title writer/integrity proof, Overtime/assignment/calendar and resource/record dependencies. |
| Atelier Ayesha Plus, US PCSE00584 Vita | Two gameplay files from one original decrypted export; 813,056 bytes. | Distinct own-title prefix, 29 sequential TLV sections and bounded trailer; original context. | Own-title Vita writer/integrity proof and resource/inventory action pairs. PS3 addresses are excluded. |

The Vita tag-three four-byte word is reported as **uninterpreted**, without
claiming that its semantic meaning or write dependencies are proved. Exact
framing and unchanged copies do not establish a missing internal checksum.
Complete original metadata is bound and rechecked at report time, without
interpreting ownership. Unknown bytes, seeds, flags and unusual values remain
unchanged. Header/trailer corruption, wrong editions, mutable/forged snapshots,
foreign metadata and source/context changes are tested separately from in-game
acceptance. No source save, key, extracted asset or owner context is redistributed.

Primary sources:

- [Gundam 2 native catalog](https://gamefaqs.gamespot.com/ps3/952640-dynasty-warriors-gundam-2/saves),
  [US writer facts](https://github.com/bucanero/apollo-patches/blob/main/PS3/BLUS30288.savepatch),
  [EU writer facts](https://github.com/bucanero/apollo-patches/blob/main/PS3/BLES00528.savepatch),
  and [BlackKite's mechanics guide](https://www.neoseeker.com/dynasty-warriors-gundam-2/faqs/187590-walkthrough.html).
  Its increased level cap of 50 demonstrates why the patch's “Level 30” target
  must not be treated as a natural cap. Pilot points are progression data.
- Apollo native Vita exports:
  [Totori Plus](https://github.com/bucanero/apollo-saves/tree/master/PSV/PCSE00231),
  [Rorona Plus](https://github.com/bucanero/apollo-saves/tree/master/PSV/PCSE00466),
  [Ayesha Plus](https://github.com/bucanero/apollo-saves/tree/master/PSV/PCSE00584).
- The [Remumu author/user discussion](https://gbatemp.net/threads/release-remumu-atelier-meruru-save-editor.443645/)
  qualifies Meruru's own Vita writer, not every Atelier title. It does not settle
  these three candidates' integrity models.

## Other investigations

Original PS3 Ar nosurge US/EU exports and a Shallie US PSN export were independently
PFD-decrypted. Their remaining bodies retain an unresolved inner encoding layer;
plain address recipes are not applied to that layer. The existing strict Gust
codec is not widened by disabling marker or integrity checks. Original editions
also do not qualify their DX/Plus ports. See [Dusk DX research](DUSK_DX_RESEARCH.md).

Aerobiz Supersonic's published
[Genesis disassembly](https://github.com/matiaszanolli/aerobiz-disasm)
contains a packed-state writer and byte-sum routines. Static instruction review
also found misleading function annotations. Native SRAM geometry/slot boundaries,
own-title identity and independent complete saves remain necessary before an
editor. The published NES Bandit Kings/L'Empereur and SNES ROTK II research
repositories were also reviewed; unresolved native save helpers and incomplete
public writer coverage are not replaced with inferred offsets.

Published Xbox 360 Bladestorm editor source was reviewed as a distinct extracted
STFS payload lead. Original-container identity, native complete inputs and integrity
qualification remain separate from the already supported PS3 edition. A console
wrapper or another edition's payload does not supply those facts.

These are concrete qualification tracks for future releases. The current releases
ship the verified editors, comparison and reviewed conversion queue without
advertising these unresolved candidates as editing support.
