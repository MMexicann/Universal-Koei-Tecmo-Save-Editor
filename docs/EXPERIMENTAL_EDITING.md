# Experimental numeric editing — v2.1

Every registered editor has an explicit experimental editing option. It is off
by default, belongs to the current editor session and resets after opening a
new save. Enabling it requires acknowledging that values above supported limits
can break the save file or game, or be clamped/reset by the game. Saving pending
values above the supported range displays another warning.

The supported editing maximum remains visible. It is not automatically a proven
natural gameplay cap: some mappings have conservative/manual boundaries or only
qualify reductions from an opened value. The encoding limit is separate and
declared by the backend. No arbitrary larger Python integer is written to a
smaller native field and no value is silently truncated or wrapped.

## DW3 Remastered first

Existing verified officer stats, normal item values, Huanglong Elixirs,
Bodyguard Merit, originally owned normal guard items and existing known normal
weapon bonuses can exceed their supported numeric bounds under the warning.
Their native signed IntProperty storage ceiling is **2,147,483,647**. Native
minimums still apply. Saved higher original values remain readable and exact
no-ops without experimental mode.

Growth levels remain native table indices with an earned points budget. Weapon
bonus identities, rare values, bonus positions/counts, equipment ownership,
references, enum values and unlock booleans retain their required rules. Mode
does not invent new records, skills, arbitrary fields or unrelated gameplay
actions. Numeric bonuses require an already saved matching identity/position.

## Shared game/platform editors

The 89 scalar editors use `BoundScalarAdapter(experimental=True)` for an
acknowledged experimental session. A scoped context is active throughout
field discovery, staging, review, serialization, native reparse and actual
destination read-back. Default adapters retain supported limits even when
called from another experimental context. Context state resets after errors
and never changes another open game's session.

Field descriptors declare `experimental_maximum`; absent/None descriptors keep
their normal range. Validators use the shared numeric helper with explicit
native bounds. Backends retain their codec, signing context, checksums, immutable
snapshot and file protections. Experimental serialization still must preserve
the exact requested values and every opaque byte outside qualified edits and
native integrity words. Binary integer limits follow actual signedness/width,
including packed 24-bit values, biased encodings and reserved sentinel values.
Whole-number float32 fields use the exact integer range through **16,777,216**.
Fixed JSON number tokens retain their original available character width.

Choice-only profiles, packed IVs already at their five-bit physical maximum,
boolean flags, equipped references, table selections and enums cannot acquire
arbitrary numeric values through this option. A profile can have no expandable
numeric ranges even though the common option is present. Read-only mappings
stay read-only.

Examples of retained constraints include Three Houses durability's reserved
sentinel, Tecmo playbooks/conditions, Pokémon IV bit widths, Project Zero camera
tier choices, Age of Calamity's preserved lifetime earnings, existing ownership
and title-specific reward/level dependencies. Monster Rancher DS's combined
gameplay stat budget can be exceeded experimentally while native record/replica
and checksum requirements remain. No unrelated game files or signing metadata
are rewritten.

## Review, Max and Undo

The scalar table shows supported and encoding limits. Selected-field guidance,
the active mode banner, Review Changes and exported review JSON identify
experimental pending values. Max actions author supported maxima and preserve
existing higher values and manually staged experimental values. They never fill
fields to their encoding ceiling.

Disabling the option rejects pending experimental edits without dropping them.
Undo validates its next history entry under the current mode before changing
anything. Experimental history can be restored after enabling the mode again.
Canceled activation/save warnings leave the original, pending edits and history
intact. Save As writes a new copy, with backups and source/context-change checks.

## Evidence boundary

Per-family procedural checks cover supported rejection, experimental ceiling
acceptance, overflow/type rejection, surgical serialization, native reparse,
protected choices and mode/cache isolation. Actual Tk flows cover warnings,
canceling, reverting, Undo, limits, session resets and saving. Full-suite and
native Windows build/package checks are required for the release workflow.

These checks verify the editor's file operations. **Loading experimental values
inside games is not verified.** Game behavior, crashes, arithmetic overflow,
progression/reward interactions and resetting remain intentionally experimental
and are the reason for the warning. Original copies and backups are essential.
