"""Bounded, explicitly reviewed conversion queues with complete preflight."""

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re

from koei_editor import conversion
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.copy_storage import atomic_new
from koei_editor.shared.save_safety import safe_path

MAX_PLAN_BYTES, MAX_JOBS = 1024 * 1024, 32


@dataclass(frozen=True)
class JobSpec:
    id: str
    route: str
    source: Path
    template: Path
    output_dir: Path


@dataclass(frozen=True)
class PreparedJob:
    spec: JobSpec
    review: conversion.Conversion


@dataclass(frozen=True)
class PreparedBatch:
    jobs: tuple[PreparedJob, ...]


@dataclass(frozen=True)
class Outcome:
    id: str
    status: str
    receipt_json: str = ""
    error: str = ""


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise SaveError("A batch plan contains a duplicate JSON key.")
        result[key] = value
    return result


def load_plan(path):
    path = safe_path(path)
    with path.open("rb") as stream:
        raw = stream.read(MAX_PLAN_BYTES + 1)
    if len(raw) > MAX_PLAN_BYTES:
        raise SaveError("Batch plan exceeds its 1 MiB limit.")
    try:
        data = json.loads(raw, object_pairs_hook=_unique_object)
    except (UnicodeError, ValueError) as error:
        raise SaveError(
            "Batch plan is not valid bounded JSON: " + str(error)
        ) from error
    if (
        type(data) is not dict
        or set(data) != {"schema_version", "jobs"}
        or type(data["schema_version"]) is not int
        or data["schema_version"] != 1
        or type(data["jobs"]) is not list
    ):
        raise SaveError("Use batch plan schema 1 with a jobs array.")
    specs = []
    for row in data["jobs"]:
        if (
            type(row) is not dict
            or set(row) != {"id", "route", "source", "template", "output_dir"}
            or any(
                type(value) is not str or not value or len(value) > 4096
                for value in row.values()
            )
        ):
            raise SaveError(
                "Every batch job requires id, route, source, template and output_dir strings."
            )
        specs.append(
            JobSpec(
                row["id"],
                row["route"],
                path.parent / row["source"],
                path.parent / row["template"],
                path.parent / row["output_dir"],
            )
        )
    return tuple(specs)


def _specs(specs):
    if type(specs) is not tuple or not 1 <= len(specs) <= MAX_JOBS:
        raise SaveError(f"Prepare between 1 and {MAX_JOBS} explicit conversion jobs.")
    result = []
    ids = set()
    outputs = []
    for spec in specs:
        if (
            type(spec) is not JobSpec
            or type(spec.id) is not str
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", spec.id) is None
            or spec.id in ids
            or type(spec.route) is not str
        ):
            raise SaveError(
                "Each job needs a unique 1–64 character ID using letters, numbers, dash or underscore."
            )
        conversion.get_route(spec.route)
        if any(
            not isinstance(path, Path)
            for path in (spec.source, spec.template, spec.output_dir)
        ):
            raise SaveError("Batch copy paths must be explicit filesystem paths.")
        source, template, output = (
            safe_path(path) for path in (spec.source, spec.template, spec.output_dir)
        )
        if output.exists():
            raise FileExistsError("Batch output folders must all be new.")
        if any(
            output == other or output in other.parents or other in output.parents
            for other in outputs
        ):
            raise SaveError(
                "Batch output folders must be distinct and cannot contain one another."
            )
        ids.add(spec.id)
        outputs.append(output)
        result.append(JobSpec(spec.id, spec.route, source, template, output))
    for output in outputs:
        if any(
            output == path or output in path.parents
            for spec in result
            for path in (spec.source, spec.template)
        ):
            raise SaveError("An output folder cannot contain a batch input copy.")
    return tuple(result)


def prepare_specs(specs, progress=None):
    specs = _specs(specs)
    jobs = []
    for spec in specs:
        if progress:
            progress(spec.id, "validating")
        review = conversion.prepare(spec.route, spec.source, spec.template)
        jobs.append(PreparedJob(spec, review))
        if progress:
            progress(spec.id, "reviewed")
    batch = PreparedBatch(tuple(jobs))
    validate(batch)
    return batch


def prepare(path, progress=None):
    return prepare_specs(load_plan(path), progress)


def validate(batch):
    if type(batch) is not PreparedBatch or type(batch.jobs) is not tuple:
        raise SaveError("Review a frozen conversion batch before exporting.")
    if any(type(job) is not PreparedJob for job in batch.jobs):
        raise SaveError("Batch jobs must retain their exact reviewed snapshots.")
    specs = _specs(tuple(job.spec for job in batch.jobs))
    for spec, job in zip(specs, batch.jobs):
        review = job.review
        if (
            spec != job.spec
            or type(review) is not conversion.Conversion
            or review.route.id != spec.route
            or review.source.document.source != spec.source
            or review.template.document.source != spec.template
        ):
            raise SaveError(
                "A batch job no longer matches its reviewed route and copied inputs."
            )
        conversion.validate_review(review)


def review_report(batch):
    validate(batch)
    return {
        "schema_version": 1,
        "dry_run": True,
        "jobs": [
            {
                "id": job.spec.id,
                "route": job.review.route.id,
                "transfer_scope": job.review.route.transfer_scope,
                "scope_description": job.review.route.scope_description,
                "source_sha256": job.review.source.document.sha256,
                "template_sha256": job.review.template.document.sha256,
                "gameplay_sha256": job.review.gameplay_sha256,
                "gameplay_bytes": job.review.gameplay_bytes,
                "output_folder": job.spec.output_dir.name,
                "notes": job.review.notes,
                "game_load_verified": False,
            }
            for job in batch.jobs
        ],
    }


def execute(batch, progress=None, canceled=None):
    # Validate every reviewed source, template, route and output before any backup/write.
    validate(batch)
    outcomes = []
    stopped = False
    for index, job in enumerate(batch.jobs):
        if stopped or (canceled is not None and canceled()):
            stopped = True
            outcomes.append(Outcome(job.spec.id, "not_started"))
            continue
        if progress:
            progress(job.spec.id, "exporting")
        try:
            _destination, _backups, receipt = conversion.export(
                job.review, job.spec.output_dir
            )
        except Exception as error:
            # OS exceptions can contain escaped paths or private backup filenames.
            # Reports retain a useful category; review again for the local diagnosis.
            if isinstance(error, OSError):
                message = f"File operation failed ({type(error).__name__}). Review this job's copies, metadata and output folder."
            elif isinstance(error, SaveError):
                message = "Conversion validation failed. Review the source and template copies again."
            else:
                message = f"Conversion failed ({type(error).__name__}). Review this job again."
            outcomes.append(Outcome(job.spec.id, "failed", error=message))
            stopped = True
            if progress:
                progress(job.spec.id, "failed")
        else:
            outcomes.append(
                Outcome(job.spec.id, "completed", json.dumps(receipt, sort_keys=True))
            )
            if progress:
                progress(job.spec.id, "completed")
    return tuple(outcomes)


def _completed_receipt(job, outcome):
    review = job.review
    conversion.validate_review_snapshot(review)
    if (
        review.route.id != job.spec.route
        or review.source.document.source != job.spec.source
        or review.template.document.source != job.spec.template
    ):
        raise SaveError("Completed review no longer matches its original job.")
    try:
        receipt = json.loads(outcome.receipt_json)
    except (TypeError, ValueError) as error:
        raise SaveError("Completed-job receipt is damaged.") from error
    target = conversion.ENDPOINTS[review.route.target_id]
    if (
        type(receipt) is not dict
        or set(receipt)
        != {
            "schema_version",
            "route",
            "transfer_scope",
            "scope_description",
            "source_sha256",
            "template_sha256",
            "source_context_sha256",
            "template_context_sha256",
            "output_sha256",
            "gameplay_sha256",
            "gameplay_bytes",
            "output_file",
            "game_load_verified",
            "console_signing_performed",
        }
        or receipt.get("schema_version") != 2
        or receipt.get("route") != job.spec.route
        or receipt.get("source_sha256") != review.source.document.sha256
        or receipt.get("template_sha256") != review.template.document.sha256
        or receipt.get("output_sha256") != hashlib.sha256(review.raw).hexdigest()
        or receipt.get("source_context_sha256")
        != (
            hashlib.sha256(review.source.companion_raw).hexdigest()
            if review.source.companion_raw
            else None
        )
        or receipt.get("template_context_sha256")
        != (
            hashlib.sha256(review.template.companion_raw).hexdigest()
            if review.template.companion_raw
            else None
        )
        or receipt.get("transfer_scope") != review.route.transfer_scope
        or receipt.get("scope_description") != review.route.scope_description
        or receipt.get("gameplay_sha256") != review.gameplay_sha256
        or receipt.get("gameplay_bytes") != review.gameplay_bytes
        or receipt.get("output_file") != target.filename
        or receipt.get("game_load_verified") is not False
        or receipt.get("console_signing_performed") is not False
    ):
        raise SaveError(
            "Completed-job receipt does not match the reviewed native output."
        )
    with safe_path(job.spec.output_dir / target.filename).open("rb") as stream:
        if stream.read(len(review.raw) + 1) != review.raw:
            raise SaveError("A completed output changed before the batch report.")
    if target.companion:
        with safe_path(job.spec.output_dir / target.companion).open("rb") as stream:
            if stream.read(target.companion_limit + 1) != review.template.companion_raw:
                raise SaveError(
                    "Completed output metadata changed before the batch report."
                )
    with safe_path(job.spec.output_dir / "conversion.json").open("rb") as stream:
        raw = stream.read(65537)
    if len(raw) > 65536 or json.loads(raw) != receipt:
        raise SaveError("A completed output receipt changed before the batch report.")
    return receipt


def outcome_report(batch, outcomes):
    if (
        type(batch) is not PreparedBatch
        or type(batch.jobs) is not tuple
        or not 1 <= len(batch.jobs) <= MAX_JOBS
        or type(outcomes) is not tuple
        or len(outcomes) != len(batch.jobs)
        or any(
            type(job) is not PreparedJob
            or type(job.spec) is not JobSpec
            or type(row) is not Outcome
            or row.id != job.spec.id
            or type(row.status) is not str
            or type(row.error) is not str
            or type(row.receipt_json) is not str
            or (row.status != "completed" and row.receipt_json != "")
            or row.status not in ("completed", "failed", "not_started")
            for job, row in zip(batch.jobs, outcomes)
        )
    ):
        raise SaveError("Batch outcomes do not match the reviewed queue.")
    return {
        "schema_version": 1,
        "dry_run": False,
        "success": all(row.status == "completed" for row in outcomes),
        "completed": sum(row.status == "completed" for row in outcomes),
        "failed": sum(row.status == "failed" for row in outcomes),
        "not_started": sum(row.status == "not_started" for row in outcomes),
        "game_load_verified": False,
        "jobs": [
            {
                "id": row.id,
                "status": row.status,
                "route": job.spec.route,
                "output_folder": job.spec.output_dir.name,
                "receipt": _completed_receipt(job, row)
                if row.status == "completed"
                else None,
                "error": row.error,
            }
            for job, row in zip(batch.jobs, outcomes)
        ],
    }


def check_report_destination(batch, path):
    path = safe_path(path)
    if path.suffix.lower() != ".json":
        raise SaveError("Choose a new .json batch report.")
    if path.exists():
        raise FileExistsError("Existing batch reports are never replaced.")
    if any(
        job.spec.output_dir == path.parent or job.spec.output_dir in path.parents
        for job in batch.jobs
    ):
        raise SaveError(
            "Keep the combined batch report outside individual converted-save folders."
        )
    return path


def export_plan(specs, path):
    specs = _specs(specs)
    path = safe_path(path)
    if path.suffix.lower() != ".json":
        raise SaveError("Choose a new .json batch plan.")
    if path.exists():
        raise FileExistsError("Existing batch plans are never replaced.")
    if any(
        spec.output_dir == path.parent or spec.output_dir in path.parents
        for spec in specs
    ):
        raise SaveError("Keep plans outside individual converted-save folders.")

    def relative(copy):
        try:
            return os.path.relpath(copy, path.parent)
        except ValueError:
            return str(copy)  # Different Windows drives.

    data = {
        "schema_version": 1,
        "jobs": [
            {
                "id": spec.id,
                "route": spec.route,
                "source": relative(spec.source),
                "template": relative(spec.template),
                "output_dir": relative(spec.output_dir),
            }
            for spec in specs
        ],
    }
    raw = (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    result = atomic_new(raw, path)
    with result.open("rb") as stream:
        if stream.read(len(raw) + 1) != raw:
            raise SaveError("Saved batch plan failed actual read-back.")
    return result


def export_report(report, path):
    path = safe_path(path)
    if path.suffix.lower() != ".json":
        raise SaveError("Choose a new .json batch report.")
    if path.exists():
        raise FileExistsError("Existing batch reports are never replaced.")
    raw = (
        json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    ).encode("utf-8")
    result = atomic_new(raw, path)
    with result.open("rb") as stream:
        if stream.read(len(raw) + 1) != raw:
            raise SaveError("Batch report failed actual read-back.")
    return result
