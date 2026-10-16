# Save Vault

Development branch only. This work is preserved for a follow-up review and is
not included in the progression-dashboard release. Application integration,
full-suite and Windows qualification remain outstanding; no public support or
release claim is made for this workspace.

Save Vault keeps a private, local history of qualified save **copies**. It adds
named collections, snapshot labels, parent histories and branches. It never edits
an imported original, applies pending editor changes, repairs unknown formats or
restores directly into a live game or Steam Cloud folder.

Choose the exact scalar game/platform profile, import a separate save copy and
keep any required original console/owner companion beside it. The selected
backend validates the input and copies only its own required opaque context.
Vault qualifies the resulting copy again and checks the original again before
recording a successful import. Missing context or an unsupported copy-context
hook causes rejection, rather than guessing an identity. DW3 keeps its existing
bespoke editing and backup workflow; Vault does not import DW3 snapshots.

Use **New collection** to organize saves. Select a parent before importing and
choose a branch label to create a different route from the same historical
snapshot. Labels are metadata, never filesystem paths. Search and collection /
branch filters work across history; the table shows 100 snapshots per page.
**History** follows the selected snapshot back through its actual parents.

**Verify** checks the catalog hash chain, exact gameplay bytes, opaque companion
bytes and the selected native parser. Select two snapshots of the same profile
and choose **Compare two** to view the existing mapped-field comparison. It
also supports **Pin first comparison snapshot**: pin one, navigate/search to a
second on any page, select it and choose **Compare two**. The comparison
distinguishes changed values, conditional field availability and changed field
definitions; bytes outside editable fields can contain checksums or unknown
state. Comparison never transfers values or establishes in-game compatibility.

**Restore / export** creates a brand-new folder under a safe parent you choose.
It preserves the original gameplay filename and required opaque context, then
qualifies the actual output. Existing output directories/files are rejected.
**Export and open** opens this newly verified copy in the ordinary editor.
Move/deploy a finished save using the destination game's established workflow;
Vault does not perform signing, ownership changes or cloud synchronization.

The application can opt into automatic capture for the current session. The
capture API freshly validates the editor's current immutable document source
after a successful open, save or backup action. Opened/saved-copy snapshots are
labelled accordingly. It never reads staged changes or assumes an older native
backup belongs to a newly saved document. Normal native backups remain enabled
independently of this optional feature; a Vault failure does not undo them.

Storage defaults to the application's private local data folder: Local AppData
on Windows, Application Support on macOS and XDG data / `~/.local/share` on Linux.
An explicit location can be injected by integrations/tests. Opening the workspace
alone does not create storage when it is absent. Context remains opaque private
bytes, potentially including account/console data: keep the entire vault local,
outside repositories/shared folders. Nothing is uploaded. Catalogs omit original
paths and decoded account metadata, but labels and original basenames remain
private local metadata. File hashes are integrity checks, not encryption.

Gameplay/context blobs are addressed by SHA-256. Each snapshot also retains a
separately checked working copy. Metadata catalogs are immutable, numbered
revisions linked to the previous revision's hash. Writers take an exclusive
directory lock; another writer fails instead of overwriting an update. A stale
`.writer-lock` is **never automatically broken**. If a process was interrupted,
close all vault applications first, preserve a complete separate copy, then
remove only that empty lock directory before retrying. Never modify catalogs or
blobs as a repair. Corruption is reported; retain the independent original.

Bounds: 5,000 snapshots, 500 collections, 10,000 catalog revisions, 4 MiB per
catalog and 128 MiB for all catalog revisions; gameplay copies up to 32 MiB;
at most eight backend-produced opaque context files totalling 2 MiB. Exhausted
bounds reject further operations. Blobs share identical bytes, but each capture
remains a distinct history entry, including equal gameplay with different
original context. Vault does not silently delete old versions or garbage-collect
failed imports. Completed files/blobs are retained after a later failure because
another program may have changed them. Such uncommitted copies do not appear as
successful snapshots. Keep disk space available and preserve failed output for
manual inspection/recovery.

Procedural tests cover history/branching, immutable content deduplication, exact
native comparison, original context, bounded metadata, corruption, source and
destination races, link/reparse rejection, retained outputs and Tk worker flows.
These checks do not establish loading a restored or edited save in the game.
