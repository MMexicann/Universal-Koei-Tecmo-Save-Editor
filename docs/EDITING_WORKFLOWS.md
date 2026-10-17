# Bulk editing and field navigation

Bulk Apply, Adjust and Max keep the complete pending map and use the existing
native staging and dependency checks. Scalar validation reports identify each
rejected field, showing up to twelve errors together. If one selected assignment
is invalid, or another assignment's native side effect replaces it, the whole
action is rejected. Pending edits and Undo history are retained. A presentation
refresh failure also rolls back the in-memory action.

**Find fields** accepts a mapped field ID. Press Enter to reveal that exact field
across category, record, pinned and pending filters, or to select a single search
match. **Next pending** cycles through all staged fields, including edits hidden
by filters. Both navigation actions leave pending values and Undo unchanged.

Review Changes still shows the complete pending map. Save As still uses the
original native writer, source protections and reparsed read-back validation to
create a separate copy. These controls do not change game mappings or native
editing limits.
