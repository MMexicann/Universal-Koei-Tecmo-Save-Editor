# Reviewed edit presets

For selected fixed-resource assignments on a different compatible save, see
[Reusable editing presets](REUSABLE_PRESETS.md). The source-bound format and
workflow described here remain available and unchanged.

**Edit Presets** lets you keep named plans for an original save, such as different
officer builds or resource choices. Export your staged fields once, then import
the plan when you reopen that original copy. Importing a plan stages edits only;
use **Save As...** in the editor to create the edited game save.

Presets are available in the shared scalar editors. DW3's separate editor keeps
its existing tagged-document workflow.

## Make a plan

1. Open a separate save copy and stage the edits you want to reuse.
2. Open **Edit Presets** and choose **Export All Staged Edits...**.
3. Name the plan and choose a new destination. The editor completes the
   `.edits.json` suffix and displays the actual filename. For example,
   `APP.BIN` becomes `APP.BIN.edits.json`.

Export includes **every staged field**, including edits hidden by a search or
category filter. It does not change the pending map or Undo history, invoke Max,
create an edited save, or replace an existing file. A preset can contain editable
names and other scalar values: keep it private when those values are personal.

## Review and apply a plan

1. Open the same original save, or a byte-identical copy at another safe path.
2. Open **Edit Presets** and choose **Import Preset...**.
3. Read the preview. It shows the opened value, your currently staged value, the
   value after import, and the effect for every imported or existing pending
   field. Existing staged fields outside the preset are kept.
4. Choose **Apply Preview to Staged Edits** deliberately. One **Undo** reverses
   the entire import. You can review or continue editing before **Save As...**.

Searching the preview helps find names, field IDs and raw or formatted values.
Filtering does not limit the import: Apply stages the complete preview. A plan
that makes no pending changes does not add an Undo snapshot. An assignment of
the exact opened value removes that field's pending edit, including an unusual
opened value that the editor otherwise preserves.

If you change the pending edits, open a different document, change experimental
mode, or modify the source/context after the preview, import the preset again
for a fresh review. Invalid input, cancellation and failed preflight leave your
pending edits, Undo history and game files intact.

## Scope and limits

Version 1 presets are deliberately **bound to the exact original save bytes and
the selected game/platform profile**. The original SHA-256 is shown in the
preview. A new in-game save, an edited Save As result, or a different player's
save will not match. Keep the original copy to reuse alternative plans. Native
companion metadata must still pass the game's normal checks when the source is
reopened; matching a hash is not console account authentication or signing.

Presets do not transfer inventory, unlock content or qualify cross-save support.
The same slot number in another save can identify a different weapon or item.
A fingerprint of the original field definitions also rejects mapping drift
after an editor update, including changed storage encodings, bit positions,
mirrors, native choices or field classes. Recreate and review the plan in that
case. Source and complete original context are rechecked after preflight and
after applying the pending map; a failed check restores the prior edits and
Undo history without writing a game save.

Every candidate runs through the bound scalar adapter's complete pending-map
validation, native dependency checks, serialization and reparsed value checks
before it can be staged. Imported JSON supplies field IDs and exact integer or
text values only. It cannot provide offsets, byte patches, executable code,
unmapped fields, or a bypass of normal game rules.

Presets never enable **Experimental** mode automatically. A plan containing new
values above supported limits requires the existing acknowledged experimental
session, and the normal experimental Save As confirmation still applies. Max
continues to use supported limits.

The reader accepts UTF-8 JSON up to 4 MiB, at most 20,000 unique field assignments,
and at most 4,096 UTF-8 bytes per text value. It rejects duplicate property names,
unknown schema properties, duplicate field assignments, booleans as numbers,
fractions, nonfinite numbers and unsupported schema versions. Game-specific
encoding and bounds can be stricter. `.changes.json` review reports are separate
read-only reports and cannot be imported as presets.

If a failure occurs after an export file has been created, the completed JSON
is retained and the error says not to use it. Reopen the source and choose a new
destination; a retained file is not proof of a successful export.

Procedural and file-level validation of presets does not establish that an
edited save loads or re-saves in the game. Each game's documented qualifications
and remaining limitations still apply.
