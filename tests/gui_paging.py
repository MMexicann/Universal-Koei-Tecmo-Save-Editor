"""Shared real-control assertions for bounded scalar editor field pages."""


def assert_paged_catalog(case, editor, expected_ids):
    """Visit every mapped field exactly once, preserving opened/pending state."""
    expected = tuple(expected_ids)
    opened = editor.document
    pending = dict(editor.changes)
    history = [dict(batch) for batch in editor.history]
    case.assertEqual(set(expected), set(editor.adapter.field_map(opened)))
    case.assertEqual(editor._filtered_field_ids, expected)
    case.assertEqual(editor.field_page_size, 250)
    case.assertEqual(editor._field_page, 0)
    case.assertTrue(editor.previous_field_page.instate(('disabled',)))
    visited = []
    while True:
        visible = editor.fields.get_children()
        case.assertLessEqual(len(visible), editor.field_page_size)
        case.assertEqual(visible, expected[len(visited):len(visited) + editor.field_page_size])
        visited.extend(visible)
        case.assertLessEqual(len(visited), len(expected))
        if editor.next_field_page.instate(('disabled',)):
            break
        editor.next_field_page.invoke()
    case.assertEqual(tuple(visited), expected)
    case.assertEqual(len(visited), len(set(visited)))
    while not editor.previous_field_page.instate(('disabled',)):
        previous_page = editor._field_page
        editor.previous_field_page.invoke()
        case.assertEqual(editor._field_page, previous_page - 1)
    case.assertEqual(editor._field_page, 0)
    case.assertEqual(editor.fields.get_children(), expected[:editor.field_page_size])
    case.assertIs(editor.document, opened)
    case.assertEqual((editor.changes, editor.history), (pending, history))
