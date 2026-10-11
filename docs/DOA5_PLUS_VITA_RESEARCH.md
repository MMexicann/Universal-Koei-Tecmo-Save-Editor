# Dead or Alive 5 Plus — PS Vita native research

This is an **unregistered investigation**, not a supported editor. The original
PS3 adapter's costume offsets do not qualify the Vita Plus edition.

## Complete native codec qualification

[Bucanero's complete DOA5 codec](https://github.com/bucanero/ps3-save-decrypters/tree/master/doa5-decrypter)
explicitly documents PS Vita as well as PS3/PS4, implements both directions and
updates the encrypted block ADD checksums. Its fixed-size PS4 Python example
is not a Vita layout specification. Independently implemented arithmetic was
checked against public original-title Vita exports without running a downloaded
editor or game binary.

The public Apollo catalogue supplies original US `PCSE00235` and Japanese
`PCSG00167` exports. Three archives contain 51,352-byte native `SAVE_SYS.DAT`
files, but the two US files are identical: they count as one state. The Japanese
native file is distinct. All three native files validate two complete blocks:

| Block | Absolute start | Total size | Native header words |
| --- | --- | --- | --- |
| First | `0x0000` | `0x3278` | Four little-endian u32 words: magic, size, checksum, seed |
| Second | `0x3278` | `0x9620` | Same framing; ends exactly at file size |

Both observed magic words are zero. For each block, the stored checksum is the
sum of **encrypted bytes after its 16-byte header**, modulo 2^32. Each complete
little-endian payload word is XORed with the current block seed; the next seed
is `((seed << 4) + (seed >> 4)) & 0xffffffff`. Encryption uses the same XOR
transformation and recomputes each block's encrypted-byte checksum. Original
seeds, framing and all unedited words are preserved.

Both distinct exports pass both native sums and byte-exact unchanged
re-encryption. Their first 16 decoded body bytes are
`00000100010001000100505050000000`. This is an observed profile fingerprint,
not permission to accept every similarly sized DOA edition.

The other Japanese archive contains a 65,536-byte outer PFS-encrypted file;
it does not pass native framing and was excluded rather than repaired or
interpreted as the same layout. Console extraction/reimport remains external.
Native save files, metadata, downloads and independent proof records stay
outside Git and release assets.

Sources:

- [US catalogue](https://bucanero.github.io/apollo-saves/PSV/PCSE00235/saves.txt)
- [Japanese catalogue](https://bucanero.github.io/apollo-saves/PSV/PCSG00167/saves.txt)
- [US Apollo patch](https://github.com/bucanero/apollo-patches/blob/main/PSV/PCSE00235.savepatch)
- [Japanese Apollo patch](https://github.com/bucanero/apollo-patches/blob/main/PSV/PCSG00167.savepatch)

## Exact remaining blocker

Neither Vita Apollo patch contains a gameplay write: both have only the codec
calls and an empty example section. The available
[VitaCheat entry](https://github.com/r0ah/vitacheat/blob/master/db/PCSE00235.psv)
contains runtime combat HP and points addresses, which do not establish a
persistent save field. No Vita Plus-specific costume/settings/gameplay writer
or controlled action pair was established in this investigation. Original PS3
costume addresses were deliberately not reused: the Vita decoded record bytes
and block geometry differ.

| Mechanic | Status / exact evidence needed |
| --- | --- |
| Native cipher and both block sums | Independently verified on two distinct public native states; no-op is byte exact. |
| Costume ownership | Need a Vita Plus-specific native save write source, or a genuinely locked-to-earned pair identifying fighter/outfit, plus unchanged control. |
| Fighters, titles, story and training/tutorial completion | Need separate identified persistent records, prerequisites and reward dependencies. Story completion must remain separate from costume edits. |
| Settings and collection data | Need controlled one-setting or one-acquisition pairs with displayed values and exact revision. |
| Combat HP/runtime points | Runtime addresses only; no save-backed editor feature established. |
| Other regions/revisions/Ultimate/Last Round | Need their own complete title-labelled native export and field qualification; the shared cipher does not widen support. |
| Console metadata and safe GUI workflow | Before registering an adapter, bind the copied native file to its original bounded `sce_sys/param.sfo`, preserve unknown bytes, and test source/metadata guards, targeted edits, backup/restore, Undo, Review Changes and Save As. |

The useful next input is a **complete decrypted US or Japanese Vita Plus slot**
with original `sce_sys/param.sfo`, exact build, and the labelled before/after
costume or settings action above. More unlabelled completed saves alone cannot
prove which bytes own a particular mechanic. No actual edited game-load/re-save
was performed, and no writable adapter or supported-game entry was created.
