"""Append-only automation metadata; save bytes always use the existing adapters.

A journal is evidence, not permission to write. Its paths are never recorded or
followed. Recovery needs the *current reviewed plan*, source-freshness checks,
and a verifier that reads the explicit destination through its native adapter.
An intent is durable before Save As begins. Ambiguous jobs are never replayed.
"""

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.copy_storage import atomic_new
from koei_editor.shared.save_safety import safe_path

MAX_JOBS = 128
MAX_EVENTS = 1 + 2 * MAX_JOBS
MAX_EVENT_BYTES = 128 * 1024
_ZERO = "0" * 64
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_ERROR = "Automation journal is incomplete, changed or invalid; review copies before continuing."


@dataclass(frozen=True)
class JournalJob:
    id: str
    game_id: str
    source_sha256: str
    output_sha256: str
    profile_sha256: str


@dataclass(frozen=True)
class RecoveryItem:
    id: str
    status: str


@dataclass(frozen=True)
class RecoveryReport:
    jobs: tuple[RecoveryItem, ...]

    @property
    def pending(self):
        return tuple(job.id for job in self.jobs if job.status == "pending")

    @property
    def safe_to_resume(self):
        return all(job.status != "blocked" for job in self.jobs)

    def as_dict(self):
        return {
            "schema_version": 1,
            "safe_to_resume": self.safe_to_resume,
            "jobs": [{"id": job.id, "status": job.status} for job in self.jobs],
        }


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise SaveError(_ERROR)
        result[key] = value
    return result


def _jobs(jobs):
    if type(jobs) is not tuple or not 1 <= len(jobs) <= MAX_JOBS:
        raise SaveError("Review a bounded tuple of automation journal jobs first.")
    seen = set()
    rows = []
    for job in jobs:
        if (type(job) is not JournalJob
                or any(type(value) is not str or _ID.fullmatch(value) is None
                       for value in (job.id, job.game_id))
                or job.id in seen
                or any(type(value) is not str or _HASH.fullmatch(value) is None
                       for value in (job.source_sha256, job.output_sha256, job.profile_sha256))):
            raise SaveError("Journal jobs need unique IDs and reviewed SHA-256 digests.")
        seen.add(job.id)
        rows.append(dict(vars(job)))
    return rows


def _token(review_token):
    if type(review_token) is not str or _HASH.fullmatch(review_token) is None:
        raise SaveError("A journal requires the current reviewed SHA-256 token.")
    return review_token


def _identity(info):
    return info.st_dev, info.st_ino


def _sync_directory(path):
    # Windows' atomic_new uses its existing native rename semantics. POSIX
    # needs the directory entry flushed independently from event contents.
    if os.name != "nt":
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


class RunJournal:
    """One reviewed run, with bounded atomic new-file events and no overwrite.

    ``complete`` is called ONLY after adapter Save As and native destination
    readback verified the expected digest and profile. The journal itself cannot
    certify a save. ``inspect`` repeats those checks through a caller-supplied
    verifier; even a forged, internally consistent journal cannot select paths.
    """

    def __init__(self, folder, review_token, jobs):
        self._folder = safe_path(folder)
        self._token = _token(review_token)
        self._jobs = jobs
        self._rows = _jobs(jobs)
        self._directory_identity = None

    @classmethod
    def create(cls, folder, review_token, jobs):
        """Create a new journal folder. Existing folders are never reused."""
        result = cls(folder, review_token, jobs)
        try:
            # Require an existing explicit parent; a single new directory can be
            # made durable before any adapter is allowed to begin its save.
            result._folder.mkdir(exist_ok=False)
            _sync_directory(result._folder.parent)
            result._check_directory()
            result._write({"schema_version": 1, "sequence": 0, "previous": _ZERO,
                           "review_token": result._token, "jobs": result._rows})
            result._load()
        except SaveError:
            raise
        except OSError as error:
            raise SaveError(_ERROR) from error
        return result

    @classmethod
    def open(cls, folder, review_token, jobs):
        """Open metadata only when it matches the explicit current review."""
        result = cls(folder, review_token, jobs)
        result._load()
        return result

    def _check_directory(self):
        info = self._folder.lstat()
        identity = _identity(info)
        if (not stat.S_ISDIR(info.st_mode) or safe_path(self._folder) != self._folder
                or self._directory_identity not in (None, identity)):
            raise SaveError(_ERROR)
        self._directory_identity = identity

    def _read(self, path):
        # Reject aliases, nonregular files, replacement during reads and bounds
        # before JSON parsing. Never follow a filename supplied inside metadata.
        before = path.lstat()
        if (not stat.S_ISREG(before.st_mode) or before.st_size > MAX_EVENT_BYTES
                or safe_path(path) != path):
            raise SaveError(_ERROR)
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                             | getattr(os, "O_BINARY", 0))
        with os.fdopen(descriptor, "rb") as stream:
            opened = os.fstat(stream.fileno())
            raw = stream.read(MAX_EVENT_BYTES + 1)
            after = os.fstat(stream.fileno())
        final = path.lstat()
        if (len(raw) > MAX_EVENT_BYTES or not stat.S_ISREG(opened.st_mode)
                or any(_identity(info) != _identity(before) for info in (opened, after, final))
                or (before.st_size, before.st_mtime_ns) != (final.st_size, final.st_mtime_ns)
                or safe_path(path) != path):
            raise SaveError(_ERROR)
        data = json.loads(raw, object_pairs_hook=_unique)
        if type(data) is not dict or set(data) != {"event", "sha256"}:
            raise SaveError(_ERROR)
        event, digest = data["event"], data["sha256"]
        if (type(event) is not dict or type(digest) is not str
                or _HASH.fullmatch(digest) is None
                or hashlib.sha256(_canonical(event)).hexdigest() != digest):
            raise SaveError(_ERROR)
        return event, digest

    def _load(self):
        try:
            self._check_directory()
            paths = []
            with os.scandir(self._folder) as entries:
                for entry in entries:
                    paths.append(self._folder / entry.name)
                    if (len(paths) > MAX_EVENTS
                            or re.fullmatch(r"[0-9]{6}\.json", entry.name) is None):
                        raise SaveError(_ERROR)
            paths.sort()
            if not paths:
                raise SaveError(_ERROR)
            states = {job.id: "pending" for job in self._jobs}
            previous = _ZERO
            for index, path in enumerate(paths):
                if path.name != f"{index:06d}.json":
                    raise SaveError(_ERROR)
                event, digest = self._read(path)
                if (type(event.get("sequence")) is not int or event["sequence"] != index
                        or event.get("previous") != previous):
                    raise SaveError(_ERROR)
                if index == 0:
                    expected = {"schema_version": 1, "sequence": 0, "previous": _ZERO,
                                "review_token": self._token, "jobs": self._rows}
                    # Exact canonical types also reject true in place of 1.
                    if _canonical(event) != _canonical(expected):
                        raise SaveError(_ERROR)
                else:
                    if (set(event) != {"sequence", "previous", "kind", "job_id"}
                            or type(event["job_id"]) is not str
                            or event["job_id"] not in states):
                        raise SaveError(_ERROR)
                    current = states[event["job_id"]]
                    if event["kind"] == "intent" and current == "pending":
                        states[event["job_id"]] = "intent"
                    elif event["kind"] == "complete" and current == "intent":
                        states[event["job_id"]] = "complete"
                    else:
                        raise SaveError(_ERROR)
                previous = digest
            self._check_directory()
            return states, len(paths), previous
        except SaveError:
            raise
        except (OSError, ValueError, UnicodeError, RecursionError, TypeError) as error:
            raise SaveError(_ERROR) from error

    def _write(self, event):
        self._check_directory()
        digest = hashlib.sha256(_canonical(event)).hexdigest()
        raw = _canonical({"event": event, "sha256": digest}) + b"\n"
        if len(raw) > MAX_EVENT_BYTES:
            raise SaveError(_ERROR)
        destination = self._folder / f"{event['sequence']:06d}.json"
        atomic_new(raw, destination)
        # atomic_new fsyncs contents; persist the new directory entry as well
        # where directory fsync is available. A lost completion stays ambiguous.
        _sync_directory(self._folder)
        self._check_directory()
        if self._read(destination) != (event, digest):
            raise SaveError(_ERROR)

    def _append(self, kind, job_id, source_sha256=None, output_sha256=None):
        states, sequence, previous = self._load()
        job = next((job for job in self._jobs if job.id == job_id), None)
        expected = "pending" if kind == "intent" else "intent"
        if (job is None or states[job_id] != expected or sequence >= MAX_EVENTS
                or source_sha256 not in (None, job.source_sha256)
                or output_sha256 not in (None, job.output_sha256)):
            raise SaveError("Journal transition does not match the current reviewed job.")
        try:
            self._write({"sequence": sequence, "previous": previous,
                         "kind": kind, "job_id": job_id})
            self._load()
        except SaveError:
            raise
        except OSError as error:
            raise SaveError(_ERROR) from error

    def validate_binding(self, review_token, jobs):
        """Check this journal belongs to the exact batch before any save begins."""
        rows = _jobs(jobs)
        if _token(review_token) != self._token or rows != self._rows:
            raise SaveError("The automation journal belongs to a different reviewed batch.")
        self._load()

    def intent(self, job_id, source_sha256=None, output_sha256=None):
        """Durably record intent BEFORE invoking the adapter's safe save."""
        self._append("intent", job_id, source_sha256, output_sha256)

    def complete(self, job_id, output_sha256=None):
        """Record completion AFTER safe save and verified native readback."""
        self._append("complete", job_id, output_sha256=output_sha256)

    def inspect(self, verifier):
        """Return path-free recovery states; never write, delete or replay saves.

        ``verifier(id)`` returns ``absent``, ``verified`` or ``invalid`` using
        ONLY paths and expected hashes/profiles from the current reviewed plan.
        Verified means native adapter readback, not just a matching file hash.
        A pending result is eligible only after the executor revalidates source
        freshness, dependencies, destinations and the review token. Any blocked
        item makes the entire run unsafe to resume. Interrupted verified outputs
        are recovered results, never pending work.
        """
        states, _, _ = self._load()
        items = []
        for job in self._jobs:
            try:
                actual = verifier(job.id)
            except Exception:
                actual = "invalid"  # Exceptions can contain private paths.
            state = states[job.id]
            if state == "pending" and actual == "absent":
                status = "pending"
            elif state in ("intent", "complete") and actual == "verified":
                status = "completed" if state == "complete" else "recovered"
            else:
                status = "blocked"
            items.append(RecoveryItem(job.id, status))
        # Detect concurrent changes during native verification. The caller must
        # still revalidate immediately before applying pending jobs.
        if self._load()[0] != states:
            raise SaveError(_ERROR)
        return RecoveryReport(tuple(items))
