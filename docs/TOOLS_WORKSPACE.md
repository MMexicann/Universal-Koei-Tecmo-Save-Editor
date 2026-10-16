# Tools and retained workspaces

Use **Tools** beside **Game Library** to open the application's save utilities.
The compact palette keeps navigation reachable without squeezing the selected
game, author credit or appearance selector. It supports both Light and Dark
themes. Use Tab or the arrow keys to choose a tool, Escape to dismiss the palette,
or click outside it.

| Tool | Purpose |
| --- | --- |
| Save Library | Browse and validate separate copies for one explicit game/platform. |
| Find Steam Saves | Discover supported locations, then explicitly import a working copy. |
| Save Doctor | Diagnose a copied save and review its validation result. |
| Save Vault | Organize validated snapshots and export a separate copy. |
| Reusable Edit Presets | Preview supported resource assignments against a compatible opened save. |
| Compare Saves | Compare verified mapped values in two copies of the same profile. |
| Save Converter | Review one explicitly supported conversion route. |
| Batch Converter | Keep reviewed conversion jobs and inspect completed results. |

Each workspace remains open when you switch to another tool or game. Its
selections and results stay available. The **Open editors** selector resumes the
same editor with its pending changes and Undo history. Switching tools never
saves, applies a preset, runs a scan or creates a Vault snapshot automatically.

**Ctrl+F** searches the visible editor or utility when that workspace offers a
search. It does not change Game Library filters while another tool is open.
Editor save, Undo and review shortcuts apply only to the visible game editor.

Opening a utility result uses its explicitly selected registered game/platform
and the normal guarded open workflow. A rejected file or a cancelled pending-edit
prompt leaves the current tool and editor state in place. Research tools are not
eligible for these open actions.

Automatic Vault capture is **off on each application start**. To enable it for
the current session, select **Capture opened and saved copies in Save Vault this
session**. A successful editor open, Save As or backup action can then capture
the freshly validated current source snapshot. Pending edits are never captured
as if they had already been saved, and an older editor backup is never relabeled
as the current source. A failed optional Vault capture does not invalidate the
editor's original backup or change a successful save operation. Turn the option
off to stop further automatic captures; existing snapshots remain in the Vault.

Closing the application waits for active exports and other protected writes.
For tools that support cancellation on close, read-only scans are cancelled only
after all open editors accept closing their pending work. Cancelling an editor's
close prompt keeps the application and its workspaces open.

See the individual tool guides for exact supported profiles and operations.
