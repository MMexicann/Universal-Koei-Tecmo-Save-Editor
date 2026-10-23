import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import {
  LIMITS,
  parseManifest,
  normalizeModManifest,
  normalizeFolderPaths,
  sanitizeRelativePath,
  versionSatisfies,
  validateMod,
  detectConflicts,
  buildWorkspacePlan,
  createAuditReport,
  createTroubleshootingCenterReport,
  buildProfileComponentSnapshot,
  createZipBlob,
  createNioh2ManagerPackageBlob,
  nioh2ManagerExportBlockers,
  createImportGate,
  createRequestSequence,
  createWorkshopValidationRecord,
  collectWorkshopValidationIssues,
  isDemoWorkspace,
  isExportableMod,
  serializeBoundedHandoff,
} from "../src/sandbox-core.mjs";

const GAME = "wolong";
const REPO_ROOT = fileURLToPath(new URL("../../..", import.meta.url));

test("static UI selectors, routes, and actions match their rendered controls", async () => {
  const [html, main] = await Promise.all([
    readFile(new URL("../index.html", import.meta.url), "utf8"),
    readFile(new URL("../src/main.mjs", import.meta.url), "utf8"),
  ]);
  const ids = new Set([...html.matchAll(/\bid="([a-z0-9-]+)"/gi)].map((match) => match[1]));
  const queriedIds = new Set([...main.matchAll(/\$\("#([a-z0-9-]+)"/g)].map((match) => match[1]));
  for (const id of queriedIds) assert.ok(ids.has(id), `missing rendered DOM id: ${id}`);

  const actions = new Set([...html.matchAll(/data-action="([a-z0-9-]+)"/g)].map((match) => match[1]));
  for (const action of actions) assert.match(main, new RegExp(`action === ["']${action}["']`), `unhandled DOM action: ${action}`);

  const routes = new Set([...html.matchAll(/data-route="([a-z0-9-]+)"/g)].map((match) => match[1]));
  const views = new Set([...html.matchAll(/data-view="([a-z0-9-]+)"/g)].map((match) => match[1]));
  assert.deepEqual(routes, views, "every navigation route must have one rendered view");
  assert.match(main, /"mod\.json"/, "Workshop project manifests must be recognized by folder import");
  assert.match(main, /koei-mod\.json is Mod Manager package metadata/);
  assert.match(main, /download-manager-package/, "Nioh 2 packages must have a dedicated Mod Manager handoff");
  const messageBridge = main.slice(main.indexOf('window.addEventListener("message"'));
  assert.match(messageBridge, /serializeBoundedHandoff\(payload\)/, "same-origin replies must obey the handoff size limit");
  assert.doesNotMatch(main, /\beval\s*\(|new\s+Function\s*\(/, "untrusted folder content must not be evaluated");
  const inventoryImport = main.slice(main.indexOf("async function importManagerInventory"), main.indexOf("async function newWorkspace"));
  assert.match(inventoryImport, /const gameId = state\.gameId/);
  assert.match(inventoryImport, /state\.gameId !== gameId \|\| state\.gameVersion !== gameVersion/);
  assert.match(main, /async function newWorkspace\(\)[\s\S]{0,500}runWorkspaceMutation/);
  assert.match(main, /async function resetDemoWorkspace\(\)[\s\S]{0,500}runWorkspaceMutation/);
  assert.match(main, /action === "remove-mod"[\s\S]{0,500}runWorkspaceMutation/);
  for (const name of ["newWorkspace", "resetDemoWorkspace"]) {
    const start = main.indexOf(`async function ${name}()`);
    const end = main.indexOf("\nfunction ", start + 1);
    assert.match(main.slice(start, end), /if \(state\.workspaceLoading\)/, `${name} must preserve the explicit confirmation guard while loading`);
  }
});

function validManifest(overrides = {}) {
  return {
    schemaVersion: 1,
    id: "safe-mod",
    name: "Safe mod",
    gameId: GAME,
    version: "1.0.0",
    gameVersion: "1.0",
    files: [{ source: "data/skin.bin", target: "mods/skin.bin" }],
    ...overrides,
  };
}

test("relative path sanitizer rejects traversal and platform escape forms", () => {
  for (const path of [
    "../outside.dll",
    "data/../../outside.dll",
    "/etc/passwd",
    "\\\\server\\share\\mod.bin",
    "C:/Games/title/mod.bin",
    "folder\\..\\outside.bin",
    "folder//mod.bin",
    "folder/./mod.bin",
    "folder/NUL.txt",
    "folder/trailing. ",
    "folder/file.bin:stream",
    "folder/evil\u0000.bin",
    "folder/foo?.dll",
    "folder/foo*.dll",
    "folder/foo<.dll",
    "folder/foo>.dll",
    "folder/foo|.dll",
    "folder/foo\".dll",
    "folder/CONIN$.dds",
    "folder/CONOUT$.ini",
    "folder/COM¹.dds",
    "folder/LPT³.ini",
    "folder/COM1 .dds",
    "folder/NUL .txt",
    "folder/CONOUT$ .ini",
  ]) {
    assert.throws(() => sanitizeRelativePath(path), { name: "Error" }, path);
  }
});

test("relative paths normalize Unicode while retaining safe nested paths", () => {
  assert.equal(sanitizeRelativePath("mods/cafe\u0301.bin"), "mods/café.bin");
  assert.equal(sanitizeRelativePath("mods/skin.bin"), "mods/skin.bin");
});

test("folder inventory lookup uses NFC paths and rejects normalized aliases", () => {
  assert.deepEqual(normalizeFolderPaths(["project/mod.json", "project/replacements/cafe\u0301.bin"]), ["mod.json", "replacements/café.bin"]);
  assert.throws(() => normalizeFolderPaths(["project/mod.json", "project/replacements/cafe\u0301.bin", "project/replacements/café.bin"]), { code: "upload_duplicate_path" });
  assert.throws(() => normalizeFolderPaths(["project/mod.json", "project/../outside.bin"]), { code: "path_traversal" });
});

test("folder imports serialize and release their gate after completion", async () => {
  const gate = createImportGate();
  let release;
  let runs = 0;
  const active = gate(async () => {
    runs++;
    await new Promise((resolve) => { release = resolve; });
  });
  assert.equal(await gate(async () => { runs++; }), false, "overlapping import must be rejected before storage can race");
  assert.equal(runs, 1);
  release();
  assert.equal(await active, true);
  assert.equal(await gate(async () => { runs++; }), true, "a later import may proceed after completion");
  assert.equal(runs, 2);
  await assert.rejects(gate(async () => { throw new Error("controlled failure"); }), /controlled failure/);
  assert.equal(await gate(async () => true), true, "a failed task must release the import gate");
});

test("latest workspace request wins and rejected Workshop validation stays in its matching handoff", () => {
  const requests = createRequestSequence();
  const first = requests.begin();
  const second = requests.begin();
  assert.equal(requests.isCurrent(first), false);
  assert.equal(requests.isCurrent(second), true);

  const rejected = createWorkshopValidationRecord({ mod_id: "sample-workshop" }, [
    { code: "workshop_source_missing", message: "Replacement source is missing." },
  ], "wolong", "1.5.0");
  assert.deepEqual(collectWorkshopValidationIssues([], rejected, "wolong", "1.5.0"), [{
    modId: "sample-workshop", code: "workshop_source_missing", message: "Replacement source is missing.",
  }]);
  assert.deepEqual(collectWorkshopValidationIssues([], rejected, "nioh2_pc", "1.5.0"), []);
  const oversized = createWorkshopValidationRecord({}, Array.from({ length: 60 }, () => ({ code: "x".repeat(100), message: "y".repeat(600) })), "wolong", "1.5.0");
  assert.equal(oversized.issues.length, 50);
  assert.equal(oversized.issues[0].code.length, 80);
  assert.equal(oversized.issues[0].message.length, 500);
  assert.equal(collectWorkshopValidationIssues(Array.from({ length: 300 }, (_, index) => ({ id: `mod-${index}`, validationErrors: [{ code: "x", message: "y" }] })), null, "wolong", "1.5.0").length, 200);
  assert.equal(serializeBoundedHandoff({ message: "x".repeat(100) }, 128) !== null, true);
  assert.equal(serializeBoundedHandoff({ message: "x".repeat(200) }, 128), null);
});

test("demo fixtures retain their label and can never be exported as user packages", () => {
  const first = { id: "demo-a", valid: true, demoFixture: true };
  const second = { id: "demo-b", valid: true, demoFixture: true };
  assert.equal(isDemoWorkspace([first, second]), true);
  assert.equal(isDemoWorkspace([second]), true, "removing one sample must preserve the demo badge");
  assert.equal(isDemoWorkspace([first, { id: "local", valid: true, demoFixture: false }]), false);
  assert.equal(isExportableMod(first), false);
  assert.equal(isExportableMod({ id: "local", valid: true, demoFixture: false }), true);
});

test("manifest parser rejects malformed, non-object, and oversized inputs", () => {
  assert.throws(() => parseManifest("{"), { code: "manifest_json" });
  assert.throws(() => parseManifest("[]"), { code: "manifest_root" });
  assert.throws(() => parseManifest(" ".repeat(LIMITS.manifestBytes + 1)), { code: "manifest_size" });
  assert.deepEqual(parseManifest('{"id":"ok"}'), { id: "ok" });
});

function workshopManifest(overrides = {}) {
  return {
    schema_version: 1,
    mod_id: "safe-mod",
    name: "Safe Workshop mod",
    version: "1.2.0",
    author: "Test author",
    description: "User-authored inert replacement data",
    game_id: GAME,
    game_version: ">=1.0.0,<2.0.0",
    platform: "Windows PC",
    license: "MIT",
    dependencies: [],
    replacements: [{
      source_path: "replacements/skin.bin",
      target_path: "Data/Skin.bin",
      sha256: "a".repeat(64),
      license: "MIT",
      attribution: "Test author",
      rights_status: "permissive-license",
    }],
    ...overrides,
  };
}

test("native Workshop project manifests validate source hashes and selected build ranges", () => {
  const source = { path: "replacements/skin.bin", size: 4, sha256: "a".repeat(64) };
  const raw = workshopManifest();
  const normalized = normalizeModManifest(raw);
  assert.equal(normalized._sandboxManifestFormat, "koei-mod-workshop.v1");
  assert.deepEqual(normalized.files[0], {
    source: "replacements/skin.bin",
    target: "Data/Skin.bin",
    sha256: "a".repeat(64),
    license: "MIT",
    attribution: "Test author",
    rightsStatus: "permissive-license",
  });
  const accepted = validateMod(raw, GAME, [source], "1.5.0");
  assert.equal(accepted.ok, true);
  assert.equal(accepted.mod.manifestFormat, "koei-mod-workshop.v1");
  assert.equal(accepted.mod.gameVersion, "1.5.0", "stage namespace uses the selected exact build");
  assert.equal(accepted.mod.compatibleGameVersion, ">=1.0.0,<2.0.0");
  assert.equal(validateMod(raw, GAME, [source], "2.0.0").errors.some((item) => item.code === "wrong_game_version"), true);
  assert.equal(validateMod(workshopManifest({ game_version: "*" }), GAME, [source], "nightly-build").ok, true);
  const omittedSchemaVersion = workshopManifest();
  delete omittedSchemaVersion.schema_version;
  assert.equal(validateMod(omittedSchemaVersion, GAME, [source], "1.5.0").ok, true, "Workshop model defaults a missing schema_version to 1");
  assert.equal(versionSatisfies("1.5.0", ">=1.2.0,<2.0.0"), true);
  assert.equal(versionSatisfies("1.9007199254740993.0", "<=1.9007199254740992.0"), false, "integer precision must not make an incompatible boundary pass");
  assert.equal(versionSatisfies("1.9007199254740993.0", ">1.9007199254740992.0"), false, "unsafe SemVer components must fail closed");
  assert.equal(versionSatisfies("1.5.0", ">=1.9007199254740993.0"), false, "unsafe requirement components must fail closed");
  assert.equal(versionSatisfies("2.0.0", ">=1.2.0,<2.0.0"), false);
  assert.equal(versionSatisfies("1.5.0", "1.4.0"), false);
  assert.equal(versionSatisfies("1.5.0", ">=1.2.0,malformed"), false);
});

test("Mod Manager metadata is not misclassified as a Workshop project manifest", () => {
  const managerMetadata = { schema_version: 1, game_id: "nioh2_pc", id: "example", name: "Example", version: "1.0.0" };
  assert.equal(normalizeModManifest(managerMetadata), managerMetadata);
  assert.equal(validateMod(managerMetadata, GAME, [], "1.0").errors.some((error) => error.code.startsWith("workshop_")), false);
  const workshopManifest = { schema_version: 1, mod_id: "example", replacements: [] };
  assert.equal(normalizeModManifest(workshopManifest)._sandboxManifestFormat, "koei-mod-workshop.v1");
});

test("Workshop manifest rejects hostile paths, hashes, platform, and malformed declarations", () => {
  const source = { path: "replacements/skin.bin", size: 4, sha256: "a".repeat(64) };
  const unsafePath = validateMod(workshopManifest({ replacements: [{
    ...workshopManifest().replacements[0], source_path: "../../outside.bin", target_path: "C:/game.dll",
  }] }), GAME, [source], "1.5.0");
  assert.equal(unsafePath.ok, false);
  assert.ok(unsafePath.errors.some((item) => item.code === "path_traversal" || item.code === "path_absolute"));

  const mismatch = validateMod(workshopManifest(), GAME, [{ ...source, sha256: "b".repeat(64) }], "1.5.0");
  assert.ok(mismatch.errors.some((item) => item.code === "sha256_mismatch"));
  const malformed = validateMod(workshopManifest({
    schema_version: 2,
    platform: "Linux",
    dependencies: [{ mod_id: "../evil", version: "not-a-range", optional: "yes" }],
    replacements: [{ ...workshopManifest().replacements[0], sha256: "bad", rights_status: "unknown" }],
  }), GAME, [source], "1.5.0");
  for (const code of ["manifest_schema", "workshop_platform", "workshop_dependency_id", "workshop_dependency_version", "workshop_dependency_optional", "invalid_sha256", "workshop_asset_rights"]) {
    assert.ok(malformed.errors.some((item) => item.code === code), `expected hostile Workshop field to fail: ${code}`);
  }
});

test("Workshop dependencies block export until staged versions satisfy requirements", () => {
  const dependent = validateMod(workshopManifest({ dependencies: [{ mod_id: "base-mod", version: ">=1.0.0,<2.0.0", optional: false }] }), GAME, [
    { path: "replacements/skin.bin", size: 4, sha256: "a".repeat(64) },
  ], "1.5.0").mod;
  const missing = buildWorkspacePlan([dependent], [], { gameId: GAME, gameVersion: "1.5.0" });
  assert.equal(missing.ok, false);
  assert.equal(missing.validationIssues.some((item) => item.code === "dependency_missing"), true);

  const base = validateMod(validManifest({ id: "base-mod", version: "1.5.0", gameVersion: "1.5.0", files: [{ source: "base.bin", target: "Data/Base.bin" }] }), GAME, [
    { path: "base.bin", size: 3 },
  ], "1.5.0").mod;
  assert.equal(buildWorkspacePlan([dependent, base], [], { gameId: GAME, gameVersion: "1.5.0" }).ok, true);
  const wrongVersion = { ...base, version: "2.0.0" };
  assert.equal(buildWorkspacePlan([dependent, wrongVersion], [], { gameId: GAME, gameVersion: "1.5.0" }).ok, false);

  const optional = validateMod(workshopManifest({ dependencies: [{ mod_id: "optional-mod", version: "*", optional: true }] }), GAME, [
    { path: "replacements/skin.bin", size: 4, sha256: "a".repeat(64) },
  ], "1.5.0").mod;
  const optionalPlan = buildWorkspacePlan([optional], [], { gameId: GAME, gameVersion: "1.5.0" });
  assert.equal(optionalPlan.ok, true);
  assert.equal(optionalPlan.compatibilityWarnings[0].code, "dependency_missing");
});

test("manifest rejects unsafe destinations, duplicate paths, and wrong-game payloads", () => {
  const accepted = validateMod(validManifest(), GAME, [{ path: "data/skin.bin", size: 4 }], "1.0");
  assert.equal(accepted.ok, true);

  const unsafe = validateMod(validManifest({ files: [{ source: "data/skin.bin", target: "../../game.dll" }] }), GAME, [{ path: "data/skin.bin", size: 4 }]);
  assert.equal(unsafe.ok, false);
  assert.ok(unsafe.errors.some((error) => error.code === "path_traversal"));

  const duplicate = validateMod(validManifest({ files: [
    { source: "data/skin.bin", target: "mods/Skin.bin" },
    { source: "data/skin.bin", target: "mods/skin.bin" },
  ] }), GAME, [{ path: "data/skin.bin", size: 4 }]);
  assert.equal(duplicate.ok, false);
  assert.ok(duplicate.errors.some((error) => error.code === "duplicate_source"));
  assert.ok(duplicate.errors.some((error) => error.code === "duplicate_target"));

  const wrongGame = validateMod(validManifest({ gameId: "not-a-koei-game" }), GAME, [{ path: "data/skin.bin", size: 4 }]);
  assert.equal(wrongGame.ok, false);
  assert.ok(wrongGame.errors.some((error) => error.code === "manifest_game"));

  const reserved = validateMod(validManifest({ files: [{ source: "data/skin.bin", target: ".koei-mod-sandbox/install-manifest.json" }] }), GAME, [{ path: "data/skin.bin", size: 4 }]);
  assert.ok(reserved.errors.some((error) => error.code === "reserved_target"));
});

test("declared content hashes must be well-formed and match an imported digest", () => {
  const digest = "a".repeat(64);
  const manifest = validManifest({ files: [{ source: "data/skin.bin", target: "mods/skin.bin", sha256: digest }] });
  assert.equal(validateMod(manifest, GAME, [{ path: "data/skin.bin", size: 4, sha256: digest }], "1.0").ok, true);
  const mismatch = validateMod(manifest, GAME, [{ path: "data/skin.bin", size: 4, sha256: "b".repeat(64) }], "1.0");
  assert.ok(mismatch.errors.some((error) => error.code === "sha256_mismatch"));
  const unverifiable = validateMod(manifest, GAME, [{ path: "data/skin.bin", size: 4 }], "1.0");
  assert.ok(unverifiable.errors.some((error) => error.code === "unverified_sha256"));
  const malformed = validateMod(validManifest({ files: [{ source: "data/skin.bin", target: "mods/skin.bin", sha256: "xyz" }] }), GAME, [{ path: "data/skin.bin", size: 4 }], "1.0");
  assert.ok(malformed.errors.some((error) => error.code === "invalid_sha256"));
});

test("import inventory rejects traversal, case collisions, and excessive sizes", () => {
  const traversing = validateMod(validManifest(), GAME, [{ path: "../skin.bin", size: 4 }]);
  assert.ok(traversing.errors.some((error) => error.code === "path_traversal"));

  const emptyInventory = validateMod(validManifest(), GAME, []);
  assert.ok(emptyInventory.errors.some((error) => error.code === "missing_source"));

  const symlink = validateMod(validManifest(), GAME, [{ path: "data/skin.bin", size: 4, isSymbolicLink: true }]);
  assert.ok(symlink.errors.some((error) => error.code === "upload_symlink"));

  const colliding = validateMod(validManifest(), GAME, [
    { path: "data/skin.bin", size: 4 },
    { path: "DATA/SKIN.BIN", size: 4 },
  ]);
  assert.ok(colliding.errors.some((error) => error.code === "upload_duplicate_path"));

  const tooLarge = validateMod(validManifest(), GAME, [{ path: "data/skin.bin", size: LIMITS.fileBytes + 1 }]);
  assert.ok(tooLarge.errors.some((error) => error.code === "upload_file_size"));

  const largeManifest = validManifest({ files: [
    { source: "data/a.bin", target: "mods/a.bin" },
    { source: "data/b.bin", target: "mods/b.bin" },
  ] });
  const overTotal = validateMod(largeManifest, GAME, [
    { path: "data/a.bin", size: 140 * 1024 * 1024 },
    { path: "data/b.bin", size: 140 * 1024 * 1024 },
  ]);
  assert.ok(overTotal.errors.some((error) => error.code === "upload_total_size"));

  const tooMany = Array.from({ length: LIMITS.fileCount + 1 }, (_, index) => ({ path: `data/${index}.bin`, size: 1 }));
  const overCount = validateMod(validManifest(), GAME, tooMany);
  assert.ok(overCount.errors.some((error) => error.code === "upload_file_limit"));
});

test("conflict planner detects case-insensitive install collisions and unsafe paths", () => {
  const result = detectConflicts([
    { id: "one", name: "One", files: [{ source: "one.bin", target: "mods/Shared.bin" }] },
    { id: "two", name: "Two", files: [{ source: "two.bin", target: "MODS/shared.BIN" }] },
    { id: "evil", name: "Unsafe", files: [{ source: "x.bin", target: "../game.exe" }] },
  ]);
  assert.ok(result.conflicts.some((item) => item.code === "destination_collision"));
  assert.ok(result.conflicts.some((item) => item.code === "path_traversal"));
  const prefixCollision = detectConflicts([
    { id: "file", name: "File", files: [{ source: "file.bin", target: "mods/catalog" }] },
    { id: "child", name: "Child", files: [{ source: "child.bin", target: "mods/catalog/entry.bin" }] },
  ]);
  assert.ok(prefixCollision.conflicts.some((item) => item.code === "file_directory_collision"));
  const baselineParent = detectConflicts(
    [{ id: "child", name: "Child", files: [{ source: "child.bin", target: "mods/catalog/child.bin" }] }],
    ["mods/catalog"],
  );
  assert.ok(baselineParent.conflicts.some((item) => item.code === "baseline_file_directory_collision"));
  const baselineChild = detectConflicts(
    [{ id: "file", name: "File", files: [{ source: "file.bin", target: "mods/catalog" }] }],
    ["mods/catalog/child.bin"],
  );
  assert.ok(baselineChild.conflicts.some((item) => item.code === "baseline_file_directory_collision"));
  const plan = buildWorkspacePlan([
    { id: "one", name: "One", status: "ready", files: [{ source: "one.bin", target: "mods/Shared.bin" }] },
    { id: "two", name: "Two", status: "ready", files: [{ source: "two.bin", target: "MODS/shared.BIN" }] },
  ]);
  assert.equal(plan.ok, false);
});

test("AI-readable report records safety state without embedding payload contents", () => {
  const mods = [{
    id: "safe-mod",
    name: "Safe mod",
    version: "1.0.0",
    gameId: GAME,
    gameVersion: "1.0",
    valid: true,
    status: "ready",
    files: [{ source: "data/skin.bin", target: "mods/skin.bin" }],
    payloads: new Map([["data/skin.bin", "PRIVATE_PAYLOAD"]]),
  }];
  const plan = buildWorkspacePlan(mods, [], { gameId: GAME, gameVersion: "1.0" });
  const text = createAuditReport(plan, mods, GAME);
  const report = JSON.parse(text);
  assert.equal(report.reportType, "koei-tecmo-mod-sandbox-audit");
  assert.equal(report.safety.codeExecuted, false);
  assert.equal(report.safety.sourceFilesModified, false);
  assert.equal(report.safety.deploymentRequiresExplicitConfirmation, true);
  assert.ok(text.includes("mods/skin.bin"));
  assert.equal(text.includes("PRIVATE_PAYLOAD"), false);
});

test("workspace planner independently blocks duplicate mod IDs", () => {
  const duplicate = buildWorkspacePlan([
    { id: "same-mod", name: "First", version: "1.0.0", gameId: GAME, gameVersion: "1.0", valid: true, files: [] },
    { id: "SAME-MOD", name: "Second", version: "2.0.0", gameId: GAME, gameVersion: "1.0", valid: true, files: [] },
  ], [], { gameId: GAME, gameVersion: "1.0" });
  assert.equal(duplicate.ok, false);
  assert.ok(duplicate.validationIssues.some((item) => item.code === "duplicate_mod_id"));
});

test("Troubleshooting Center handoff follows schema v1 and discloses sandbox-only scope", () => {
  const mods = [{ id: "private-mod", name: "Private mod", version: "1.0.0", gameId: GAME, gameVersion: "1.5.0", valid: true, files: [{ source: "replacement.bin", target: "Data/private.bin", sha256: "a".repeat(64) }] }];
  const plan = buildWorkspacePlan(mods, [], { gameId: GAME, gameVersion: "1.5.0" });
  const report = createTroubleshootingCenterReport(plan, mods, GAME, "1.5.0");
  assert.deepEqual(Object.keys(report), ["schema", "schema_version", "ruleset_version", "read_only", "game_id", "title", "platform", "overall_status", "findings"]);
  assert.equal(report.schema, "koei-game-troubleshooting");
  assert.equal(report.schema_version, 1);
  assert.equal(report.read_only, true);
  assert.equal(report.overall_status, "partial", "clean sandbox checks do not claim an installation-level pass");
  for (const finding of report.findings) {
    assert.deepEqual(Object.keys(finding), ["id", "category", "status", "severity", "title", "summary", "evidence", "recommendation", "source"]);
    assert.equal(finding.category, "mods");
  }
  const serialized = JSON.stringify(report);
  assert.ok(serialized.includes("installation and runtime not checked"));
  assert.equal(serialized.includes("Data/private.bin"), false);
  assert.equal(serialized.includes("replacement.bin"), false);
  assert.equal(serialized.includes("a".repeat(64)), false);
  assert.equal(serialized.includes("PRIVATE_PAYLOAD"), false);
  const empty = createTroubleshootingCenterReport(buildWorkspacePlan([], [], { gameId: GAME, gameVersion: "1.5.0" }), [], GAME, "1.5.0");
  assert.equal(empty.findings[0].status, "not_checked");
  assert.equal(empty.overall_status, "unknown");
});

test("Mod Manager component matches ProfileComponentSnapshot and enforces the 256 KiB JSON bound", () => {
  const payload = {
    schema_version: 1,
    load_order: ["safe-mod"],
    mods: [{ id: "safe-mod", enabled: false, files: [{ source: "data/skin.bin", target: "mods/skin.bin" }] }],
    safety: { code_executed: false, auto_apply: false },
  };
  const snapshot = buildProfileComponentSnapshot(GAME, "1.0", payload);
  assert.deepEqual(Object.keys(snapshot), ["component", "provider", "schema_version", "game_id", "game_version", "payload"]);
  assert.equal(snapshot.component, "mod_configuration");
  assert.equal(snapshot.provider, "mod_manager");
  assert.equal(snapshot.schema_version, 1);
  assert.equal(snapshot.game_id, "wolong");
  assert.equal(snapshot.game_version, "1.0");
  const serialized = JSON.stringify(snapshot, null, 2);
  assert.ok(new TextEncoder().encode(serialized).byteLength <= LIMITS.manifestBytes);
  assert.throws(() => buildProfileComponentSnapshot(GAME, "1.0", { data: "x".repeat(LIMITS.manifestBytes) }), /256 KiB/);
  assert.throws(() => buildProfileComponentSnapshot("unregistered-pc-title", "1.0", payload), /registered/);
  assert.throws(() => buildProfileComponentSnapshot("nioh2_pc", "1.0", payload), /registered/);
  assert.throws(() => buildProfileComponentSnapshot(GAME, "build\n1", payload), /printable/);
  assert.throws(() => buildProfileComponentSnapshot(GAME, "1.0", Array.from({ length: 2_500 }, () => ({ id: "a", files: ["a.bin"] }))), /structural bound/);
  assert.throws(() => buildProfileComponentSnapshot(GAME, "1.0", { value: Number.NaN }), /finite JSON/);
});

function extractStoredZipEntries(blob) {
  return blob.arrayBuffer().then((buffer) => {
    const bytes = new Uint8Array(buffer);
    const view = new DataView(buffer);
    const entries = new Map();
    const eocd = bytes.byteLength - 22;
    assert.equal(view.getUint32(eocd, true), 0x06054b50, "ZIP must end with a valid central-directory record");
    assert.equal(view.getUint16(eocd + 4, true), 0, "ZIP must not span disks");
    assert.equal(view.getUint16(eocd + 6, true), 0, "ZIP must not span disks");
    const entryCount = view.getUint16(eocd + 10, true);
    assert.equal(view.getUint16(eocd + 8, true), entryCount, "EOCD entry counts must match");
    const centralOffset = view.getUint32(eocd + 16, true);
    const centralSize = view.getUint32(eocd + 12, true);
    assert.equal(centralOffset + centralSize, eocd, "central directory must end at the ZIP footer");
    const crc32 = (data) => {
      let crc = 0xffffffff;
      for (const byte of data) {
        crc ^= byte;
        for (let bit = 0; bit < 8; bit++) crc = (crc >>> 1) ^ (0xedb88320 & -(crc & 1));
      }
      return (crc ^ 0xffffffff) >>> 0;
    };
    const localEntries = new Map();
    let offset = 0;
    for (let index = 0; index < entryCount; index++) {
      assert.equal(view.getUint32(offset, true), 0x04034b50, "each local file must have a local header");
      assert.equal(view.getUint16(offset + 6, true), 0x0800, "local flags must be UTF-8 without descriptors");
      assert.equal(view.getUint16(offset + 8, true), 0, "local compression must be stored");
      const expectedCrc = view.getUint32(offset + 14, true);
      const size = view.getUint32(offset + 18, true);
      assert.equal(view.getUint32(offset + 22, true), size, "stored size fields must match");
      const nameLength = view.getUint16(offset + 26, true);
      const extraLength = view.getUint16(offset + 28, true);
      const nameStart = offset + 30;
      const dataStart = nameStart + nameLength + extraLength;
      const name = new TextDecoder().decode(bytes.slice(nameStart, nameStart + nameLength));
      const data = bytes.slice(dataStart, dataStart + size);
      assert.equal(crc32(data), expectedCrc, `local CRC must match payload ${name}`);
      assert.equal(localEntries.has(name), false, `local path must be unique: ${name}`);
      localEntries.set(name, { offset, flags: view.getUint16(offset + 6, true), crc: expectedCrc, size, data });
      offset = dataStart + size;
    }
    assert.equal(offset, centralOffset, "local records must end at the declared central directory");
    let centralPosition = centralOffset;
    for (let index = 0; index < entryCount; index++) {
      assert.equal(view.getUint32(centralPosition, true), 0x02014b50, "central entries must be well formed");
      assert.equal(view.getUint16(centralPosition + 8, true), 0x0800, "central flags must match UTF-8 local headers");
      assert.equal(view.getUint16(centralPosition + 10, true), 0, "central compression must be stored");
      const crc = view.getUint32(centralPosition + 16, true);
      const compressedSize = view.getUint32(centralPosition + 20, true);
      const uncompressedSize = view.getUint32(centralPosition + 24, true);
      const nameLength = view.getUint16(centralPosition + 28, true);
      const extraLength = view.getUint16(centralPosition + 30, true);
      const commentLength = view.getUint16(centralPosition + 32, true);
      assert.equal(view.getUint16(centralPosition + 34, true), 0, "central entry must be on disk zero");
      assert.equal(view.getUint32(centralPosition + 38, true), 0, "entry attributes must not mark a symlink or special file");
      const localOffset = view.getUint32(centralPosition + 42, true);
      const nameStart = centralPosition + 46;
      const name = new TextDecoder().decode(bytes.slice(nameStart, nameStart + nameLength));
      assert.equal(extraLength, 0, "central extras are not expected");
      assert.equal(commentLength, 0, "central comments are not expected");
      const local = localEntries.get(name);
      assert.ok(local, `central path must reference a local entry: ${name}`);
      assert.equal(localOffset, local.offset, `central offset must match local entry: ${name}`);
      assert.equal(crc, local.crc, `central CRC must match local entry: ${name}`);
      assert.equal(compressedSize, local.size, `central compressed size must match local entry: ${name}`);
      assert.equal(uncompressedSize, local.size, `central uncompressed size must match local entry: ${name}`);
      assert.equal(view.getUint16(centralPosition + 8, true), local.flags, `central flags must match local entry: ${name}`);
      entries.set(name, local.data);
      centralPosition = nameStart + nameLength + extraLength + commentLength;
    }
    assert.equal(centralPosition, eocd, "central record count and size must match EOCD");
    assert.equal(entries.size, localEntries.size, "local and central path sets must match");
    return entries;
  });
}

test("Nioh 2 Mod Manager handoff ZIP matches its strict import layout without installing", async () => {
  const mod = {
    id: "nioh2-mod",
    name: "Nioh 2 sample",
    version: "1.0.0",
    gameId: "nioh2_pc",
    gameVersion: "1.0",
    valid: true,
    dependencies: [{ id: "base-mod", version: "*", optional: false }],
    files: [
      { source: "project/config.ini", target: "MyMod/config.ini" },
      { source: "project/model.fmt", target: "MyMod/model.fmt" },
      { source: "project/vertices.vb", target: "MyMod/vertices.vb" },
    ],
    payloads: new Map([
      ["project/config.ini", new Blob(["[mod]\\nenabled=true\\n"])],
      ["project/model.fmt", new Blob(["inert fmt"])],
      ["project/vertices.vb", new Blob(["inert vb"])],
    ]),
  };
  const base = { id: "base-mod", name: "Base", version: "1.2.0", gameId: "nioh2_pc", gameVersion: "1.0", valid: true, files: [] };
  const resolvedPlan = buildWorkspacePlan([mod, base], [], { gameId: "nioh2_pc", gameVersion: "1.0" });
  const entries = await extractStoredZipEntries(await createNioh2ManagerPackageBlob(mod, resolvedPlan));
  assert.deepEqual([...entries.keys()].sort(), ["MyMod/config.ini", "MyMod/model.fmt", "MyMod/vertices.vb", "koei-mod.json"]);
  const metadata = JSON.parse(new TextDecoder().decode(entries.get("koei-mod.json")));
  assert.deepEqual(metadata, {
    schema_version: 1,
    game_id: "nioh2_pc",
    id: "nioh2-mod",
    name: "Nioh 2 sample",
    version: "1.0.0",
    dependencies: ["base-mod"],
    conflicts: [],
  });
  assert.equal(entries.has(".koei-mod-sandbox/install-manifest.json"), false);
  assert.equal(new TextDecoder().decode(entries.get("MyMod/config.ini")), "[mod]\\nenabled=true\\n");
  const rangedMod = { ...mod, dependencies: [{ id: "base-mod", version: ">=1.0.0", optional: false }] };
  await assert.rejects(createNioh2ManagerPackageBlob(rangedMod, resolvedPlan), /cannot preserve/);
  const missingDependencyPlan = buildWorkspacePlan([mod], [], { gameId: "nioh2_pc", gameVersion: "1.0" });
  assert.ok(nioh2ManagerExportBlockers(mod, missingDependencyPlan).some((message) => message.includes("not staged")));
  await assert.rejects(createNioh2ManagerPackageBlob(mod, missingDependencyPlan), /not staged/);
  const resolvedDependency = { ...mod, dependencies: [{ id: "base-mod", version: "*", optional: false }] };
  const consumerResolvedPlan = buildWorkspacePlan([resolvedDependency, base], [], { gameId: "nioh2_pc", gameVersion: "1.0" });
  assert.deepEqual(nioh2ManagerExportBlockers(resolvedDependency, consumerResolvedPlan), []);
  const collisionPlan = buildWorkspacePlan([
    { ...resolvedDependency, name: "Nioh 2 sample" },
    { id: "other-mod", name: "Other mod", version: "1.0.0", gameId: "nioh2_pc", gameVersion: "1.0", valid: true, files: [{ source: "other/model.fmt", target: "MyMod/model.fmt" }] },
  ], [], { gameId: "nioh2_pc", gameVersion: "1.0" });
  assert.ok(nioh2ManagerExportBlockers(resolvedDependency, collisionPlan).some((message) => message.includes("target the same install path")));
  const dependencyCollisionPlan = buildWorkspacePlan([
    resolvedDependency,
    { ...base, files: [{ source: "base/shared.fmt", target: "Shared/shared.fmt" }] },
    { id: "other-mod", name: "Other mod", version: "1.0.0", gameId: "nioh2_pc", gameVersion: "1.0", valid: true, files: [{ source: "other/shared.fmt", target: "Shared/shared.fmt" }] },
  ], [], { gameId: "nioh2_pc", gameVersion: "1.0" });
  assert.ok(nioh2ManagerExportBlockers(resolvedDependency, dependencyCollisionPlan).some((message) => message.includes("target the same install path")));
  const invalidDependencyPlan = buildWorkspacePlan([
    resolvedDependency,
    { id: "base-mod", name: "Base", version: "1.2.0", gameId: "nioh2_pc", gameVersion: "1.0", valid: false, files: [] },
  ], [], { gameId: "nioh2_pc", gameVersion: "1.0" });
  assert.ok(nioh2ManagerExportBlockers(resolvedDependency, invalidDependencyPlan).some((message) => message.includes("has not passed validation")));
  const unresolvedNestedPlan = buildWorkspacePlan([
    resolvedDependency,
    { ...base, dependencies: [{ id: "nested-base", version: "*", optional: false }] },
  ], [], { gameId: "nioh2_pc", gameVersion: "1.0" });
  assert.ok(nioh2ManagerExportBlockers(resolvedDependency, unresolvedNestedPlan).some((message) => message.includes("nested-base")));
  await assert.rejects(createNioh2ManagerPackageBlob({ ...mod, id: "disabled-mod" }, resolvedPlan), /disabled/);
  await assert.rejects(createNioh2ManagerPackageBlob({ ...mod, files: mod.files.slice(1) }, resolvedPlan), /exactly one \.ini/);
  await assert.rejects(createNioh2ManagerPackageBlob({ ...mod, files: [...mod.files, { source: "project/extra.ini", target: "MyMod/extra.ini" }] }, resolvedPlan), /exactly one \.ini/);
  const rootMod = {
    ...mod,
    files: [
      { source: "project/root.ini", target: "root.ini" },
      { source: "project/root.fmt", target: "root.fmt" },
    ],
    payloads: new Map([
      ["project/root.ini", new Blob(["[mod]\\n"])],
      ["project/root.fmt", new Blob(["inert fmt"])],
      ["project/metadata.json", new Blob(["not metadata"])],
    ]),
  };
  await assert.rejects(createNioh2ManagerPackageBlob({ ...rootMod, files: [...rootMod.files, { source: "project/metadata.json", target: "koei-mod.json" }] }, resolvedPlan), /collides with generated/);
  await assert.rejects(createNioh2ManagerPackageBlob({
    ...mod,
    files: [...mod.files, { source: "project/tree.fmt", target: "MyMod/tree.fmt" }, { source: "project/tree-child.dds", target: "MyMod/tree.fmt/child.dds" }],
    payloads: new Map([...mod.payloads, ["project/tree.fmt", new Blob(["parent file"])], ["project/tree-child.dds", new Blob(["nested file"])]]),
  }, resolvedPlan), /nested under another file/);
  await assert.rejects(createNioh2ManagerPackageBlob({ ...mod, files: [...mod.files, { source: "project/escape.dds", target: "Elsewhere/escape.dds" }] }, resolvedPlan), /inside the folder containing/);
  await assert.rejects(createNioh2ManagerPackageBlob({ ...mod, files: [...mod.files, { source: "project/plugin.dll", target: "MyMod/plugin.dll" }] }, resolvedPlan), /Unsupported/);
  await assert.rejects(createNioh2ManagerPackageBlob({ ...mod, payloads: new Map() }, resolvedPlan), /payload is missing/);
});

test("generated Nioh 2 ZIP passes the desktop Mod Manager importer without installation", async (t) => {
  const python = spawnSync("python3", ["--version"], { encoding: "utf8" });
  if (python.error?.code === "ENOENT") return t.skip("Python 3 is unavailable for the Mod Manager interoperability check.");
  assert.equal(python.status, 0, python.stderr);
  const mod = {
    id: "nioh2-interop",
    name: "Nioh 2 interoperability fixture",
    version: "1.0.0",
    gameId: "nioh2_pc",
    gameVersion: "fixture-build",
    valid: true,
    dependencies: [],
    files: [
      { source: "project/mod.ini", target: "Interop/mod.ini" },
      { source: "project/model.fmt", target: "Interop/model.fmt" },
    ],
    payloads: new Map([
      ["project/mod.ini", new Blob(["[Mod]\\nName=Interop\\n"])],
      ["project/model.fmt", new Blob(["synthetic inert payload"])],
    ]),
  };
  const plan = buildWorkspacePlan([mod], [], { gameId: "nioh2_pc", gameVersion: "fixture-build" });
  const archive = await createNioh2ManagerPackageBlob(mod, plan);
  const temporary = await mkdtemp(join(tmpdir(), "koei-nioh2-import-check-"));
  try {
    const archivePath = join(temporary, "sandbox-handoff.zip");
    await writeFile(archivePath, Buffer.from(await archive.arrayBuffer()));
    const script = [
      "import json, sys",
      "from pathlib import Path",
      "from koei_editor.shared.mod_manager import GAME_EXE, LOADER_FILE, ModManager",
      "root = Path(sys.argv[2])",
      "game = root / 'game'",
      "game.mkdir()",
      "(game / GAME_EXE).write_bytes(b'synthetic game fixture')",
      "(game / LOADER_FILE).write_bytes(b'synthetic loader fixture')",
      "manager = ModManager(root / 'manager-state', game)",
      "record = manager.import_archive(Path(sys.argv[1]))",
      "print(json.dumps({'id': record.id, 'installed': record.installed, 'enabled': record.enabled, 'file_count': len(record.files)}))",
    ].join("\n");
    const imported = spawnSync("python3", ["-c", script, archivePath, temporary], {
      cwd: REPO_ROOT,
      env: { ...process.env, PYTHONPATH: join(REPO_ROOT, "src") },
      encoding: "utf8",
    });
    assert.equal(imported.status, 0, imported.stderr);
    assert.deepEqual(JSON.parse(imported.stdout), { id: "nioh2-interop", installed: false, enabled: false, file_count: 2 });
  } finally {
    await rm(temporary, { recursive: true, force: true });
  }
});

test("ZIP writer refuses traversal and case-colliding names without executing content", async () => {
  await assert.rejects(createZipBlob([{ path: "../outside.bin", data: "never run" }]));
  await assert.rejects(createZipBlob([
    { path: "mods/file.bin", data: "first" },
    { path: "MODS/FILE.BIN", data: "second" },
  ]));
  await assert.rejects(createZipBlob([
    { path: "mods/catalog", data: "file" },
    { path: "mods/catalog/entry.bin", data: "child" },
  ]));
  await assert.rejects(createZipBlob([
    { path: "mods/catalog/entry.bin", data: "child" },
    { path: "MODS/CATALOG", data: "file" },
  ]));
  await assert.rejects(createZipBlob([{ path: ".koei-mod-sandbox/install-manifest.json", data: "attacker metadata" }]));
  const trustedArchive = await createZipBlob([
    { path: ".koei-mod-sandbox/install-manifest.json", data: "{}", system: true },
    { path: "mods/payload.bin", data: "payload" },
  ]);
  assert.equal(trustedArchive.type, "application/zip");

  const payload = "globalThis.__sandboxZipPayloadExecuted = true;";
  delete globalThis.__sandboxZipPayloadExecuted;
  const blob = await createZipBlob([{ path: "mods/payload.js", data: payload }]);
  assert.equal(blob.type, "application/zip");
  const entries = await extractStoredZipEntries(blob);
  assert.equal(new TextDecoder().decode(entries.get("mods/payload.js")), payload, "untrusted content should remain inert bytes in a valid ZIP");
  assert.equal(globalThis.__sandboxZipPayloadExecuted, undefined);
  delete globalThis.__sandboxZipPayloadExecuted;
});
