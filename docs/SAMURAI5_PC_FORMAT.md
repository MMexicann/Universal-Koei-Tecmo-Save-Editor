# Samurai Warriors 5 — native Windows PC

Adapter: `samurai5_pc`, package `koei_editor.games.samurai5_pc`.
Opens native `SAVEDATA00.BIN` revision 39 saved at My Castle. Keep the
**original `steam_autocloud.vdf` beside each separate save copy**, including the
Save As and restore destination. The editor reads it privately to derive the
original owner key. It never changes ownership, exports an account value,
tries other owners, or writes into the game/Steam Cloud folders.

The copied-save self-test copies the original companion byte for byte into its
new private output directory. Ordinary Save As requires that same unchanged
companion already beside its destination; the general prohibition on opening
or modifying Steam Cloud metadata remains in force.

## Editing and mechanics

| Mechanic | Editable scope | Native limit / dependencies |
| --- | --- | --- |
| Gold | Current wallet, individual edits and Max | 9,999,999; cumulative spending, achievement/reward records and older checkpoints remain separate |
| Stock EXP | Shared Dojo pool, individual edits and Max | 9,999,999; the game applies officer level, Dojo and castle-rank restrictions |
| Shared skill points | Shared spendable pool, individual edits and Max | 99,999; per-officer allocated points, acquired skills and prerequisite flags remain intact |
| Stock weapon mastery | Shared pool, individual edits and Max | 9,999,999; officer mastery, weapon ranks and equipment restrictions are separate |
| Lumber, mineral, fabric | Three independent building-material quantities, individual edits and Max | 9,999 each; castle rank, facilities and upgrade rewards are preserved |
| Weapons, officers, mounts, gems | Searchable current-copy serialized-record inspection | Native boundaries are proved; unqualified words are displayed as raw prefixes or native indices rather than invented item/character identities |
| Scenarios, Citadel, residence, stables, shop weapons, rewards, corps | Searchable inspection | No story completion or unknown flag writes |

Max preserves existing higher values. Returning a field to its opened value
removes that pending edit, including unusual values outside the normal range.
Max removes a pending reduction of an opened value already above its native
cap, restoring that original higher value. Undo and Review Changes use the shared editing workspace.

The [official Dojo manual](https://www.koeitecmoamerica.com/manual/sw5/en/4100.html)
distinguishes stock EXP and stock weapon mastery. Dojo level limits officer
level and weapon mastery; castle rank/story progress limits facilities.
That same My Castle manual describes facility functions. Weapon rank must fit the officer's mastery;
Blacksmith level limits weapon skills. Mount levels derive from EXP and
mount fusion consumes a donor. Citadel pair progression supplies friendship
and Hermit's Retreat events. Raising a resource pool does not grant these
progression prerequisites or fabricate transactions.

## Native codec and current-copy proof

All executable inspection was static. No attached game binary or third-party
editor was executed. No binary, player save, account identifier, asset catalog
or third-party implementation is distributed.

* Key derivation at `0x140008160` uses native slot selector zero, the exact
  binary64 iterative calculation and the low owner DWORD from the original
  sidecar. A 16-byte LCG key uses multiplier `0x343FD`, increment `0x269EC3`,
  high output byte. The final LE32 IV seed drives a separate LCG (`0x15A4E35`,
  increment 1, output bits 16–23).
* AES-128-CBC decrypts all 4,493,232 bytes before that seed. The native trailer
  is `01Finger2Print34`. There is no PKCS padding, appended repair, fixed owner
  key, plaintext fallback or trial/other-slot conversion.
* Complete native write/read paths `0x1400086D0`, `0x140008910`, and
  `0x140008F70` copy three native buffers, align, apply the fingerprint and
  CBC. The manager and all 17 class serializers use direct byte-stream
  primitives `0x1400C6C70`/`0x1400C6D00`; no payload checksum rewrite occurs.
  The fingerprint is a format/key gate, **not a cryptographic authentication
  checksum**. Arbitrary corruption outside checked framing cannot generally
  be detected in this unchecksummed native format.
* Native configuration at `0x1412B22A0` fixes counts and constructor bindings.
  Revision 39 manager serialization at `0x140109D20` writes storage copies in
  order **4, 1, 2, 3**. Their Common starts are `0xC8`, `0x63420`, `0xC6827`,
  `0x129C2E`. Class record counts/strides are implemented as explicit schema,
  with a manager end of `0x18CF9B`; two following buffers are `0x15E000` each,
  followed by five native zero alignment bytes and the fingerprint.
* Loader `0x1400C842F` chooses resume bank 1, then its first byte at
  `0x2EAF9B`: zero selects copy 4; one selects copy 2. This adapter admits
  only the **zero / castle-menu case**. A battle/resume or unknown selector
  asks the user to return to My Castle and make a fresh copy. It never
  synchronizes historical copies or patches both battle buffers.

Current Common serialized resource offsets are absolute `0xD4` (gold),
`0xDC` (stock EXP), `0xE0` (shared skill points), `0xE4` (stock mastery),
`0x2A48` (lumber), `0x2A4A` (mineral), `0x2A4C` (fabric). Common serializer
`0x140123730` maps them from runtime members `0x894`, `0x89C`, `0x8A0`,
`0x8A4`, `0x3B04`, `0x3B06`, `0x3B08`. Materials are indices 60–62 in
65 serialized `u16` entries after exactly `0x2908` Common bytes.

Gold grant/spend `0x14014BE30` treats spending history (`0x898`) separately.
Stock-resource routines `0x140235630`, `0x140235750`, `0x140235870` prove
three separate pools and their respective caps. Acquire-Skill UI path
`0x14036E810` checks the entry's cost, spends the Common skill-point pool
through `0x140235750`, and separately updates the selected officer's
allocated-point word `0x67A`. It therefore does not justify labelling the
Common pool as an individual officer's points or learned skills. Material
grant/spend `0x14014C400`/`0x14014C4F0` enforce 9,999 and write the Common
array; `0x14014C6C0` validates static resource metadata, not save acquisition.

Independent corroboration: [aanpsx's SW5 memory-table discussion](https://fearlessrevolution.com/viewtopic.php?p=203355#p203355)
identifies the Dojo pool and three material runtime members; a
[second money table](https://fearlessrevolution.com/viewtopic.php?t=26990)
corroborates the gold member. These were read statically as research references.
Cheat-table target constants were **not** used as limits: its 99,999 material
write overflows a two-byte quantity. The native routines establish the caps.

## Qualification and remaining coverage

`tests/test_samurai5_pc.py` separates generated procedural fixtures from opt-in
private genuine-save checks (`SW5_PC_SAVE_COPY`, `SW5_PC_OWNER_COPY`). A complete
genuine slot decrypts with its supplied original owner context and reconstructs
the original ciphertext exactly using the direct codec. Tests cover all seven
surgical fields, checkpoint and unknown-byte preservation, combined encrypted
edits, invalid values, wrong owners, revision/resume/alignment/fingerprint
rejection, forged snapshots, source/sidecar changes, destination context,
backup hash binding, exact restore, the copied-save self-test and real Tk
open/filter/stage/Undo/Review/inspection/Save As workflows.

An independent second agent checked class sizes, stream order, copy selection,
material offsets/caps and shared skill-pool semantics against the native code.
**Edited game loading has not been performed.** An unchecksummed native format
does not make random corruption detectable or establish every unknown record's
semantics. Tests do not claim either property.

| Remaining mechanic | Exact blocker / next proof |
| --- | --- |
| Officer names, unlocks, levels, EXP, stats, skill trees | Serialized boundaries known; need disk-field/asset identities, growth thresholds, Dojo/castle caps, acquired skill/reward dependencies and controlled progression pairs before writes |
| Weapon types, rank/reinforcement, skills, equipment | 1,680 native 27-byte records inspected; need occupied-record/type map, Blacksmith skill ceilings, rank/mastery prerequisites and ownership/equipped references |
| Mount identities, EXP, levels, fusion/equip | 64 native 32-byte records inspected; need identity/occupancy map, stable capacity, EXP thresholds, donor removal/equip dependencies |
| Skill-gem inventory and learned skills | 1,000 quantity bytes inspected; need valid gem identities, unlock/prerequisite rules and transaction dependencies |
| Facility levels / castle rank | Native residence/stable/shop records available; need exact field enums, story thresholds, costs and reward/event prerequisites |
| Musou/Citadel progress, objectives, friendships | 300 scenario and 256 Citadel records available; need stage/paired-officer dictionaries, prerequisite masks and reward/event transitions |
| Collections, music/movies, biography, customization | Need named content flags and prerequisites; setting unknown bits is unsafe |
| Active battle saves / storage copy 2 | Selector recovered, but battle-resource/rollback dependencies and complete resume semantics remain unqualified; fresh castle-menu copies only |
| Other slots, revisions, trials / regions | Need separately labelled complete genuine copies and owner contexts for each variant |
| Actual game acceptance of edited resources | Requires deliberate loading and resaving of an edited offline copy in the matching game |
