"""Interrupted automation metadata never authorizes replay or save overwrites."""

from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.game_registry import get_game
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared import automation_journal as journal
from tests.test_dw4hyper_format import procedural_raw


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


class AutomationJournalTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name).resolve()
        self.path = self.folder / "run"
        self.token = digest(b"reviewed plan")
        self.jobs = (journal.JournalJob("first", "dw4hyper", digest(b"source"),
                                        digest(b"output"), digest(b"profile")),
                     journal.JournalJob("second", "dw4hyper", digest(b"source2"),
                                        digest(b"output2"), digest(b"profile")))

    def create(self):
        return journal.RunJournal.create(self.path, self.token, self.jobs)

    def reopen(self):
        return journal.RunJournal.open(self.path, self.token, self.jobs)

    def rewrite(self, index, mutate):
        path = self.path / f"{index:06d}.json"
        data = json.loads(path.read_bytes())
        mutate(data["event"])
        data["sha256"] = digest(journal._canonical(data["event"]))
        path.write_bytes(journal._canonical(data))

    def test_clean_pending_and_completed_reports_contain_no_paths(self):
        run = self.create()
        initial = run.inspect(lambda _: "absent")
        self.assertTrue(initial.safe_to_resume)
        self.assertEqual(initial.pending, ("first", "second"))
        run.intent("first", self.jobs[0].source_sha256, self.jobs[0].output_sha256)
        run.complete("first", self.jobs[0].output_sha256)
        report = self.reopen().inspect(lambda key: "verified" if key == "first" else "absent")
        self.assertEqual([item.status for item in report.jobs], ["completed", "pending"])
        self.assertNotIn(str(self.folder), json.dumps(report.as_dict()))
        for path in self.path.iterdir():
            self.assertNotIn(str(self.folder).encode(), path.read_bytes())

    def test_interrupted_intent_is_blocked_even_when_output_absent(self):
        run = self.create()
        run.intent("first")
        report = self.reopen().inspect(lambda _: "absent")
        self.assertFalse(report.safe_to_resume)
        self.assertEqual(report.jobs[0].status, "blocked")
        self.assertEqual(report.pending, ("second",))
        with self.assertRaises(SaveError):
            self.reopen().intent("first")

    def test_interruption_after_output_is_recovered_and_never_pending(self):
        run = self.create()
        run.intent("first")
        before = {path.name: path.read_bytes() for path in self.path.iterdir()}
        report = self.reopen().inspect(lambda key: "verified" if key == "first" else "absent")
        self.assertEqual(report.jobs[0].status, "recovered")
        self.assertTrue(report.safe_to_resume)
        self.assertEqual(report.pending, ("second",))
        self.assertEqual(before, {path.name: path.read_bytes() for path in self.path.iterdir()})

    def test_completed_metadata_cannot_override_missing_or_invalid_output(self):
        run = self.create()
        run.intent("first")
        run.complete("first")
        for actual in ("absent", "invalid", None, True, "unexpected"):
            with self.subTest(actual=actual):
                report = run.inspect(lambda _: actual)
                self.assertFalse(report.safe_to_resume)
                self.assertEqual(report.jobs[0].status, "blocked")

    def test_unrecorded_existing_output_is_blocked(self):
        report = self.create().inspect(lambda _: "verified")
        self.assertFalse(report.safe_to_resume)
        self.assertEqual(report.pending, ())

    def test_native_safe_save_readback_reconciles_interruption_without_writing(self):
        adapter = get_game("dw4hyper").get_scalar_adapter()
        source = self.folder / "source.dat"
        destination = self.folder / "edited.dat"
        raw = procedural_raw()
        source.write_bytes(raw)
        document = adapter.read_save(source)
        field = adapter.fields_for(document)[0]
        opened = field.value(document.payload)
        target = field.minimum if opened != field.minimum else field.maximum
        pending = adapter.stage(document, {}, field.id, target)
        expected = digest(adapter.serialize(document, pending))
        self.jobs = (journal.JournalJob("first", adapter.game_id, document.sha256,
                                       expected, digest(b"native-profile")),)
        run = self.create()
        run.intent("first")
        adapter.save_as(document, pending, destination)
        # Simulate shutdown before completion is recorded. The verifier gets
        # its destination from this current plan, never from journal metadata.
        def verify(key):
            self.assertEqual(key, "first")
            if not destination.exists():
                return "absent"
            reopened = adapter.read_save(destination)
            return "verified" if reopened.sha256 == expected else "invalid"
        saved = destination.read_bytes()
        with patch.object(adapter.backend, "save_as", side_effect=AssertionError("No replay")):
            report = self.reopen().inspect(verify)
        self.assertEqual(report.jobs[0].status, "recovered")
        self.assertEqual(report.pending, ())
        self.assertEqual(source.read_bytes(), raw)
        self.assertEqual(destination.read_bytes(), saved)
        # A valid but different native save is not the reviewed output.
        destination.write_bytes(raw)
        self.assertEqual(self.reopen().inspect(verify).jobs[0].status, "blocked")
        # Native integrity failure cannot be accepted by metadata.
        destination.write_bytes(saved[:-1])
        self.assertEqual(self.reopen().inspect(verify).jobs[0].status, "blocked")
        self.assertEqual(source.read_bytes(), raw)

    def test_review_token_and_all_reviewed_job_metadata_must_match(self):
        self.create()
        altered = (
            (digest(b"different plan"), self.jobs),
            (self.token, tuple(reversed(self.jobs))),
            (self.token, (replace(self.jobs[0], game_id="dw8xl"), self.jobs[1])),
            (self.token, (replace(self.jobs[0], source_sha256=digest(b"stale")), self.jobs[1])),
            (self.token, (replace(self.jobs[0], output_sha256=digest(b"other")), self.jobs[1])),
            (self.token, (replace(self.jobs[0], profile_sha256=digest(b"changed")), self.jobs[1])),
        )
        for token, jobs in altered:
            with self.subTest(jobs=jobs, token=token):
                with self.assertRaises(SaveError):
                    journal.RunJournal.open(self.path, token, jobs)

    def test_hash_corruption_and_truncated_events_are_rejected_without_deletion(self):
        run = self.create()
        run.intent("first")
        path = self.path / "000001.json"
        original = path.read_bytes()
        for malformed in (original[:-10], b"{", b"null", b"[]", b"\xff", b"{" * 1100,
                          original.replace(b'"intent"', b'"broken"')):
            with self.subTest(malformed=malformed[:30]):
                path.write_bytes(malformed)
                with self.assertRaises(SaveError):
                    self.reopen()
                self.assertEqual(path.read_bytes(), malformed)
        path.write_bytes(original)
        self.reopen()

    def test_duplicate_json_keys_are_rejected(self):
        self.create()
        path = self.path / "000000.json"
        path.write_bytes(path.read_bytes().replace(b'{"event":', b'{"event":null,"event":', 1))
        with self.assertRaises(SaveError):
            self.reopen()

    def test_tampered_paths_and_unknown_metadata_never_get_followed(self):
        self.create()
        unrelated = self.folder / "private-save.dat"
        unrelated.write_bytes(b"untouched")
        self.rewrite(0, lambda event: event.update(source=str(unrelated)))
        with self.assertRaises(SaveError):
            self.reopen()
        self.assertEqual(unrelated.read_bytes(), b"untouched")

    def test_forged_internally_consistent_completion_still_needs_native_verification(self):
        run = self.create()
        run.intent("first")
        run.complete("first")
        # Even a valid chain supplied by an attacker cannot certify a save or
        # make the journal choose a destination. Only current-plan readback can.
        calls = []
        report = self.reopen().inspect(lambda key: calls.append(key) or "invalid")
        self.assertEqual(calls, ["first", "second"])
        self.assertFalse(report.safe_to_resume)
        self.assertEqual(report.pending, ())

    def test_missing_event_and_broken_chain_are_rejected(self):
        run = self.create()
        run.intent("first")
        run.complete("first")
        path = self.path / "000001.json"
        raw = path.read_bytes()
        path.unlink()
        with self.assertRaises(SaveError):
            self.reopen()
        path.write_bytes(raw)
        self.rewrite(2, lambda event: event.update(previous="f" * 64))
        with self.assertRaises(SaveError):
            self.reopen()

    def test_illegal_transition_and_digest_mismatch_cannot_append(self):
        run = self.create()
        for operation in (lambda: run.complete("first"), lambda: run.intent("unknown"),
                          lambda: run.intent("first", digest(b"wrong")),
                          lambda: run.intent("first", output_sha256=digest(b"wrong"))):
            with self.assertRaises(SaveError):
                operation()
        self.assertEqual(len(list(self.path.iterdir())), 1)
        run.intent("first")
        with self.assertRaises(SaveError):
            run.intent("first")
        run.complete("first")
        with self.assertRaises(SaveError):
            run.complete("first")

    def test_rewritten_complete_without_intent_is_invalid(self):
        run = self.create()
        run.intent("first")
        self.rewrite(1, lambda event: event.update(kind="complete"))
        with self.assertRaises(SaveError):
            self.reopen()

    def test_partial_atomic_event_is_kept_and_requires_inspection(self):
        run = self.create()
        original_atomic = journal.atomic_new
        def persist_then_interrupt(raw, destination):
            original_atomic(raw, destination)
            raise OSError("private/path must not appear")
        with patch.object(journal, "atomic_new", side_effect=persist_then_interrupt):
            with self.assertRaises(SaveError) as error:
                run.intent("first")
        self.assertNotIn("private/path", str(error.exception))
        self.assertEqual(self.reopen().inspect(lambda _: "absent").jobs[0].status, "blocked")
        self.assertTrue((self.path / "000001.json").exists())

    def test_orphan_temporary_and_oversized_event_fail_closed(self):
        self.create()
        temporary = self.path / ".000001.json.interrupted.tmp"
        temporary.write_bytes(b"partial")
        with self.assertRaises(SaveError):
            self.reopen()
        self.assertEqual(temporary.read_bytes(), b"partial")
        temporary.unlink()
        (self.path / "000001.json").write_bytes(b" " * (journal.MAX_EVENT_BYTES + 1))
        with self.assertRaises(SaveError):
            self.reopen()

    def test_existing_folders_are_not_reused_or_cleaned(self):
        self.path.mkdir()
        sentinel = self.path / "notes.txt"
        sentinel.write_bytes(b"keep")
        with self.assertRaises(SaveError):
            self.create()
        self.assertEqual(sentinel.read_bytes(), b"keep")

    def test_symlink_event_and_replaced_directory_are_rejected(self):
        run = self.create()
        first = self.path / "000000.json"
        moved = self.folder / "metadata.json"
        first.rename(moved)
        try:
            first.symlink_to(moved)
        except (NotImplementedError, OSError):
            self.skipTest("Host cannot create symlinks")
        with self.assertRaises(SaveError):
            self.reopen()
        first.unlink()
        moved.rename(first)
        old = self.folder / "old-run"
        self.path.rename(old)
        self.path.mkdir()
        for path in old.iterdir():
            (self.path / path.name).write_bytes(path.read_bytes())
        with self.assertRaises(SaveError):
            run.intent("first")

    @unittest.skipUnless(hasattr(os, 'mkfifo') and hasattr(os, 'O_NONBLOCK'),
                         'POSIX FIFO replacement requires nonblocking descriptor support')
    def test_regular_event_replaced_by_fifo_rejects_before_read_without_waiting_for_writer(self):
        run = self.create()
        path = self.path / '000000.json'
        original_open, original_fdopen = os.open, os.fdopen
        descriptors, reads = [], []

        def replace_before_open(candidate, flags, *args, **kwargs):
            if Path(candidate) == path:
                path.unlink()
                os.mkfifo(path)
                # Fail promptly on a regression instead of hanging the suite
                # while the blocking open waits for a nonexistent FIFO writer.
                self.assertTrue(flags & os.O_NONBLOCK)
            descriptor = original_open(candidate, flags, *args, **kwargs)
            descriptors.append(descriptor)
            return descriptor

        class UnreadableStream:
            def __init__(self, descriptor, mode):
                self.stream = original_fdopen(descriptor, mode)

            def __enter__(self):
                self.stream.__enter__()
                return self

            def __exit__(self, *args):
                return self.stream.__exit__(*args)

            def fileno(self):
                return self.stream.fileno()

            def read(self, *_args):
                reads.append(True)
                raise AssertionError('Nonregular descriptors must be rejected before reading.')

        with (patch.object(journal.os, 'open', side_effect=replace_before_open),
              patch.object(journal.os, 'fdopen', UnreadableStream)):
            with self.assertRaises(SaveError):
                run.inspect(lambda _key: self.fail('Invalid metadata must not reach the native verifier.'))
        self.assertEqual(reads, [])
        self.assertEqual(len(descriptors), 1)
        with self.assertRaises(OSError):
            os.fstat(descriptors[0])
        self.assertTrue(path.exists())  # Interrupted metadata is retained.

    def test_concurrent_append_is_detected_and_original_events_remain(self):
        first = self.create()
        second = self.reopen()
        called = False
        def verify(_):
            nonlocal called
            if not called:
                called = True
                second.intent("first")
            return "absent"
        with self.assertRaises(SaveError):
            first.inspect(verify)
        self.assertTrue((self.path / "000001.json").exists())

    def test_verifier_exceptions_are_redacted(self):
        run = self.create()
        def verify(_):
            raise OSError(str(self.folder / "private-save.dat"))
        report = run.inspect(verify)
        self.assertFalse(report.safe_to_resume)
        self.assertNotIn(str(self.folder), json.dumps(report.as_dict()))

    def test_binding_check_rejects_another_run_before_any_save(self):
        run = self.create()
        run.validate_binding(self.token, self.jobs)
        before = {path.name: path.read_bytes() for path in self.path.iterdir()}
        for token, jobs in ((digest(b"other batch"), self.jobs),
                            (self.token, (self.jobs[0],))):
            with self.assertRaises(SaveError):
                run.validate_binding(token, jobs)
        self.assertEqual(before, {path.name: path.read_bytes() for path in self.path.iterdir()})
        path = self.path / "000000.json"
        path.write_bytes(b"interrupted")
        with self.assertRaises(SaveError):
            run.validate_binding(self.token, self.jobs)

    def test_invalid_job_metadata_is_rejected_before_creating_directory(self):
        for jobs in ((), list(self.jobs), (self.jobs[0], self.jobs[0]),
                     (replace(self.jobs[0], id="../escape"),),
                     (replace(self.jobs[0], source_sha256="bogus"),)):
            with self.subTest(jobs=jobs):
                with self.assertRaises(SaveError):
                    journal.RunJournal.create(self.path, self.token, jobs)
                self.assertFalse(self.path.exists())


if __name__ == "__main__":
    unittest.main()
