export const SUPPORTED_GAMES = [
  { id: "dw8xl", label: "Dynasty Warriors 8 Xtreme Legends CE" },
  { id: "wolong", label: "Wo Long: Fallen Dynasty" },
  { id: "nioh2_pc", label: "Nioh 2 (Mod Manager package support)" },
  { id: "nioh3", label: "Nioh 3" },
  { id: "samurai5_pc", label: "Samurai Warriors 5" },
  { id: "wo4_ultimate", label: "Warriors Orochi 4 Ultimate" },
  { id: "atelier_ryza3_dx_pc", label: "Atelier Ryza 3 DX" },
];

const PROFILE_COMPONENT_GAME_IDS = new Set(["dw8xl", "wolong", "nioh3", "samurai5_pc", "wo4_ultimate", "atelier_ryza3_dx_pc"]);

export const LIMITS = Object.freeze({
  manifestBytes: 256 * 1024,
  fileCount: 5000,
  fileBytes: 256 * 1024 * 1024,
  hashBytes: 64 * 1024 * 1024,
  pathLength: 1024,
  filesPerManifest: 5000,
});

/** Reject overlapping folder imports until the active validation/storage task completes. */
export function createImportGate() {
  let active = false;
  return async (task) => {
    if (active) return false;
    active = true;
    try {
      await task();
      return true;
    } finally {
      active = false;
    }
  };
}

const encoder = new TextEncoder();

function issue(code, message, extra = {}) {
  return { code, message, ...extra };
}

/** Return a safe normalized relative path or throw a coded validation error. */
export function sanitizeRelativePath(value) {
  if (typeof value !== "string") throw Object.assign(new Error("Path must be text."), { code: "path_type" });
  const path = value.normalize("NFC");
  if (!path || path.length > LIMITS.pathLength) throw Object.assign(new Error("Path is empty or too long."), { code: "path_length" });
  if (path.startsWith("/") || path.startsWith("\\") || /^[a-z]:/i.test(path) || path.includes("\\")) {
    throw Object.assign(new Error("Use a relative path with forward slashes."), { code: "path_absolute" });
  }
  if (/[\u0000-\u001f\u007f\u202a-\u202e\u2066-\u2069]/.test(path) || path.includes(":")) {
    throw Object.assign(new Error("Path contains a control character or alternate stream marker."), { code: "path_characters" });
  }
  const parts = path.split("/");
  if (parts.some((part) => !part || part === "." || part === "..")) {
    throw Object.assign(new Error("Path contains an empty or traversal segment."), { code: "path_traversal" });
  }
  if (parts.some((part) => /[. ]$/.test(part) || /^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)/i.test(part))) {
    throw Object.assign(new Error("Path contains a reserved or ambiguous Windows name."), { code: "path_reserved" });
  }
  return parts.join("/");
}

/** Normalize folder-picker paths and reject Unicode/case aliases before lookup. */
export function normalizeFolderPaths(sourcePaths) {
  if (!Array.isArray(sourcePaths)) throw new Error("Folder paths must be a list.");
  const firstComponents = sourcePaths.map((path) => typeof path === "string" ? path.split("/")[0] : "");
  const oneRoot = sourcePaths.length > 0 && sourcePaths.every((path, index) => typeof path === "string" && path.includes("/") && firstComponents[index] === firstComponents[0]);
  const seen = new Set();
  return sourcePaths.map((path) => {
    if (typeof path !== "string") throw new Error("Folder paths must be text.");
    const relative = sanitizeRelativePath(oneRoot ? path.split("/").slice(1).join("/") : path);
    const key = relative.toLocaleLowerCase("en-US");
    if (seen.has(key)) throw Object.assign(new Error("Folder contains duplicate paths after Unicode and case normalization."), { code: "upload_duplicate_path" });
    seen.add(key);
    return relative;
  });
}

export function parseManifest(text) {
  if (typeof text !== "string") throw Object.assign(new Error("Manifest must be text."), { code: "manifest_type" });
  if (encoder.encode(text).byteLength > LIMITS.manifestBytes) {
    throw Object.assign(new Error("Manifest is larger than 256 KiB."), { code: "manifest_size" });
  }
  let parsed;
  try {
    parsed = JSON.parse(text);
  } catch {
    throw Object.assign(new Error("Manifest is not valid JSON."), { code: "manifest_json" });
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw Object.assign(new Error("Manifest root must be a JSON object."), { code: "manifest_root" });
  }
  return parsed;
}

/** Normalize the native Mod Creation Workshop manifest without trusting its report. */
export function normalizeModManifest(manifest) {
  if (!manifest || typeof manifest !== "object" || Array.isArray(manifest)) return manifest;
  if (!("schema_version" in manifest || "mod_id" in manifest || "replacements" in manifest)) return manifest;
  const replacements = Array.isArray(manifest.replacements)
    ? manifest.replacements.map((replacement) => {
      if (!replacement || typeof replacement !== "object" || Array.isArray(replacement)) return replacement;
      return {
        source: replacement.source_path,
        target: replacement.target_path,
        sha256: replacement.sha256,
        license: replacement.license,
        attribution: replacement.attribution,
        rightsStatus: replacement.rights_status,
      };
    })
    : manifest.replacements;
  return {
    ...manifest,
    schemaVersion: manifest.schema_version === undefined ? 1 : manifest.schema_version,
    id: manifest.mod_id,
    gameId: manifest.game_id,
    gameVersion: manifest.game_version,
    files: replacements,
    _sandboxManifestFormat: "koei-mod-workshop.v1",
  };
}

function semverParts(value) {
  if (typeof value !== "string") return null;
  const match = /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/.exec(value.trim());
  if (!match) return null;
  const parts = match.slice(1).map(Number);
  return parts.every(Number.isSafeInteger) ? parts : null;
}

function compareSemver(left, right) {
  for (let index = 0; index < 3; index++) {
    if (left[index] !== right[index]) return left[index] < right[index] ? -1 : 1;
  }
  return 0;
}

/** Match the Workshop's `*`, exact label, or comma-separated SemVer ranges. */
export function versionSatisfies(actual, requirement) {
  if (typeof actual !== "string" || typeof requirement !== "string") return false;
  const cleanActual = actual.trim();
  const cleanRequirement = requirement.trim();
  if (cleanRequirement === "*") return true;
  if (!/[<>=]/.test(cleanRequirement)) return cleanActual.toLocaleLowerCase("en-US") === cleanRequirement.toLocaleLowerCase("en-US");
  const actualParts = semverParts(cleanActual);
  if (!actualParts) return false;
  const terms = cleanRequirement.split(",");
  if (!terms.length) return false;
  return terms.every((term) => {
    const match = /^(>=|<=|>|<|==|=)?\s*(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/.exec(term.trim());
    if (!match) return false;
    const operator = match[1] || "==";
    const expected = match.slice(2).map(Number);
    if (!expected.every(Number.isSafeInteger)) return false;
    const comparison = compareSemver(actualParts, expected);
    return operator === ">" ? comparison > 0
      : operator === ">=" ? comparison >= 0
        : operator === "<" ? comparison < 0
          : operator === "<=" ? comparison <= 0
            : comparison === 0;
  });
}

function validVersionRequirement(requirement) {
  if (typeof requirement !== "string") return false;
  const clean = requirement.trim();
  if (clean === "*") return true;
  if (!/[<>=]/.test(clean)) return semverParts(clean) !== null;
  return clean.split(",").every((term) => {
    const match = /^(>=|<=|>|<|==|=)?\s*(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/.exec(term.trim());
    return Boolean(match && match.slice(2).every((part) => Number.isSafeInteger(Number(part))));
  });
}

function manifestGame(manifest) {
  return typeof manifest.gameId === "string" ? manifest.gameId : manifest.game;
}

function normalizeDescriptor(descriptor, index) {
  const record = typeof descriptor === "string" ? { source: descriptor, target: descriptor } : descriptor;
  if (!record || typeof record !== "object" || Array.isArray(record)) {
    throw Object.assign(new Error(`File entry ${index + 1} must be a path or object.`), { code: "manifest_file_entry" });
  }
  const source = sanitizeRelativePath(record.source ?? record.path ?? "");
  const target = sanitizeRelativePath(record.target ?? record.installPath ?? source);
  return {
    source,
    target,
    sha256: record.sha256 === undefined ? null : typeof record.sha256 === "string" ? record.sha256.toLowerCase() : "__invalid__",
    license: record.license,
    attribution: record.attribution,
    rightsStatus: record.rightsStatus ?? record.rights_status,
  };
}

/**
 * Validate a manifest against the currently selected title and imported folder.
 * uploadedFiles are { path, size, type } records; no file contents are read here.
 */
export function validateMod(manifest, selectedGameId, uploadedFiles, selectedGameVersion) {
  const errors = [];
  const warnings = [];
  if (!manifest || typeof manifest !== "object" || Array.isArray(manifest)) {
    return { ok: false, errors: [issue("manifest_root", "Manifest root must be a JSON object.")] };
  }
  manifest = normalizeModManifest(manifest);
  const workshopManifest = manifest._sandboxManifestFormat === "koei-mod-workshop.v1";
  const id = manifest.id;
  const name = manifest.name;
  const gameId = manifestGame(manifest);
  const version = manifest.version;
  const gameVersion = manifest.gameVersion;
  if (manifest.schemaVersion !== 1) errors.push(issue("manifest_schema", workshopManifest ? "Workshop schema_version must be 1 when provided." : "Manifest must declare schemaVersion 1."));
  if (typeof id !== "string" || !/^[a-z0-9][a-z0-9._-]{0,62}$/i.test(id)) errors.push(issue("manifest_id", "Add a short mod ID using letters, numbers, dots, underscores, or dashes."));
  if (workshopManifest && (typeof id !== "string" || !/^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$/.test(id))) errors.push(issue("workshop_mod_id", "Workshop mod IDs must use lowercase letters, digits, dots, underscores, or hyphens."));
  if (typeof name !== "string" || !name.trim() || name.length > 120) errors.push(issue("manifest_name", "Add a display name between 1 and 120 characters."));
  if (typeof gameId !== "string" || !SUPPORTED_GAMES.some((game) => game.id === gameId)) errors.push(issue("manifest_game", "This manifest does not identify an initial title profile in the sandbox list."));
  if (typeof version !== "string" || !/^[0-9][a-z0-9.+_-]{0,63}$/i.test(version)) errors.push(issue("manifest_version", "Add a version string such as 1.2.0."));
  if (workshopManifest && !semverParts(version)) errors.push(issue("workshop_mod_version", "Workshop mod versions must use three numeric semantic-version parts, such as 1.0.0."));
  if (gameId && selectedGameId && gameId !== selectedGameId) errors.push(issue("wrong_game", "The manifest targets a different game than the selected workspace."));
  if (typeof gameVersion !== "string" || !gameVersion.trim() || gameVersion.length > 80 || /[\u0000-\u001f\u007f]/.test(gameVersion)) errors.push(issue("manifest_game_version", "Manifest must declare a printable game build/profile version."));
  if (selectedGameVersion !== undefined) {
    if (typeof selectedGameVersion !== "string" || !selectedGameVersion.trim() || selectedGameVersion.length > 80 || /[\u0000-\u001f\u007f]/.test(selectedGameVersion)) errors.push(issue("workspace_game_version", "Select or enter a printable exact game build/profile for this workspace."));
    else if (workshopManifest ? !versionSatisfies(selectedGameVersion, gameVersion) : gameVersion !== selectedGameVersion) errors.push(issue("wrong_game_version", workshopManifest ? "The selected game build/profile is outside the Workshop manifest's declared compatible version." : "The manifest game build/profile must exactly match the selected workspace profile."));
  }
  if (workshopManifest) {
    if (typeof manifest.platform !== "string" || manifest.platform.trim().toLocaleLowerCase("en-US") !== "windows pc") errors.push(issue("workshop_platform", "This sandbox supports Workshop manifests that declare the Windows PC platform."));
    if (typeof manifest.license !== "string" || !manifest.license.trim()) errors.push(issue("workshop_license", "Workshop manifest must declare a mod license."));
    if (typeof manifest.author !== "string" || !manifest.author.trim()) errors.push(issue("workshop_author", "Workshop manifest must declare an author."));
  }

  let dependencies = [];
  if (workshopManifest) {
    if (!Array.isArray(manifest.dependencies) || manifest.dependencies.length > 500) {
      errors.push(issue("workshop_dependencies", "Workshop dependencies must be an array of at most 500 entries."));
    } else {
      const seenDependencies = new Set();
      dependencies = manifest.dependencies.map((dependency, index) => {
        if (!dependency || typeof dependency !== "object" || Array.isArray(dependency)) {
          errors.push(issue("workshop_dependency_entry", `Workshop dependency ${index + 1} must be an object.`));
          return null;
        }
        const dependencyId = dependency.mod_id;
        const range = dependency.version === undefined ? "*" : dependency.version;
        const optional = dependency.optional === undefined ? false : dependency.optional;
        if (typeof dependencyId !== "string" || !/^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$/.test(dependencyId)) errors.push(issue("workshop_dependency_id", `Workshop dependency ${index + 1} has an invalid lowercase mod ID.`));
        if (!validVersionRequirement(range)) errors.push(issue("workshop_dependency_version", `Workshop dependency ${index + 1} has an invalid version requirement.`));
        if (typeof optional !== "boolean") errors.push(issue("workshop_dependency_optional", `Workshop dependency ${index + 1} optional must be a boolean.`));
        const key = typeof dependencyId === "string" ? dependencyId.toLocaleLowerCase("en-US") : "";
        if (key && key === String(id).toLocaleLowerCase("en-US")) errors.push(issue("workshop_dependency_self", `Mod ${id} cannot depend on itself.`));
        if (key && seenDependencies.has(key)) errors.push(issue("workshop_dependency_duplicate", `Workshop dependency ${dependencyId} is listed more than once.`));
        if (key) seenDependencies.add(key);
        return { id: dependencyId, version: range, optional };
      }).filter(Boolean);
    }
  }

  const descriptors = manifest.files;
  if (!Array.isArray(descriptors) || descriptors.length === 0) {
    errors.push(issue("manifest_files", "Manifest must list at least one staged file."));
  } else if (descriptors.length > LIMITS.filesPerManifest) {
    errors.push(issue("manifest_file_limit", `Manifest exceeds the ${LIMITS.filesPerManifest.toLocaleString()} file limit.`));
  }

  const files = [];
  const sources = new Set();
  const targets = new Set();
  if (Array.isArray(descriptors) && descriptors.length <= LIMITS.filesPerManifest) {
    descriptors.forEach((descriptor, index) => {
      try {
        const file = normalizeDescriptor(descriptor, index);
        const sourceKey = file.source.toLocaleLowerCase("en-US");
        const targetKey = file.target.toLocaleLowerCase("en-US");
        if (sources.has(sourceKey)) errors.push(issue("duplicate_source", `Source path is listed more than once: ${file.source}`, { path: file.source }));
        if (targets.has(targetKey)) errors.push(issue("duplicate_target", `Install path is listed more than once: ${file.target}`, { path: file.target }));
        if (targetKey === ".koei-mod-sandbox" || targetKey.startsWith(".koei-mod-sandbox/")) errors.push(issue("reserved_target", "The .koei-mod-sandbox ZIP metadata namespace is reserved.", { path: file.target }));
        if (workshopManifest) {
          if (!file.sha256) errors.push(issue("workshop_hash_required", `Workshop replacement ${file.source} must declare SHA-256.`, { path: file.source }));
          if (typeof file.license !== "string" || !file.license.trim()) errors.push(issue("workshop_asset_license", `Workshop replacement ${file.source} must declare a license.`, { path: file.source }));
          if (!["creator-owned", "permissive-license", "public-domain"].includes(file.rightsStatus)) errors.push(issue("workshop_asset_rights", `Workshop replacement ${file.source} has an unsupported rights declaration.`, { path: file.source }));
          if (file.rightsStatus === "permissive-license" && (typeof file.attribution !== "string" || !file.attribution.trim())) errors.push(issue("workshop_attribution", `Permissively licensed replacement ${file.source} needs attribution.`, { path: file.source }));
        }
        sources.add(sourceKey);
        targets.add(targetKey);
        files.push(file);
      } catch (error) {
        errors.push(issue(error.code || "manifest_file_path", `File entry ${index + 1}: ${error.message}`));
      }
    });
  }

  const strictInventory = Array.isArray(uploadedFiles);
  if (uploadedFiles !== undefined && !strictInventory) errors.push(issue("upload_inventory", "Imported file inventory is invalid."));
  const inventory = new Map();
  let totalBytes = 0;
  if (Array.isArray(uploadedFiles)) {
    if (uploadedFiles.length > LIMITS.fileCount) errors.push(issue("upload_file_limit", `Import exceeds the ${LIMITS.fileCount.toLocaleString()} file limit.`));
    for (const entry of uploadedFiles.slice(0, LIMITS.fileCount)) {
      try {
        if (entry.isSymbolicLink || entry.symlink || entry.type === "symlink") {
          errors.push(issue("upload_symlink", "Symbolic-link entries are not accepted."));
          continue;
        }
        const path = sanitizeRelativePath(entry.path);
        const key = path.toLocaleLowerCase("en-US");
        if (inventory.has(key)) errors.push(issue("upload_duplicate_path", `Imported files collide at ${path}.`, { path }));
        const size = Number(entry.size ?? entry.file?.size ?? 0);
        if (!Number.isFinite(size) || size < 0 || size > LIMITS.fileBytes) errors.push(issue("upload_file_size", `File exceeds the 256 MiB per-file limit: ${path}`, { path }));
        else totalBytes += size;
        inventory.set(key, { ...entry, path, size });
      } catch (error) {
        errors.push(issue(error.code || "upload_path", `Imported file path: ${error.message}`));
      }
    }
    if (totalBytes > LIMITS.fileBytes) errors.push(issue("upload_total_size", "Import exceeds the 256 MiB total size limit."));
  }

  for (const file of files) {
    if (strictInventory && !inventory.has(file.source.toLocaleLowerCase("en-US"))) {
      errors.push(issue("missing_source", `Manifest source file is missing from the imported folder: ${file.source}`, { path: file.source }));
    }
    const sourceRecord = inventory.get(file.source.toLocaleLowerCase("en-US"));
    if (file.sha256 !== null && !/^[a-f0-9]{64}$/.test(file.sha256)) errors.push(issue("invalid_sha256", `SHA-256 must be 64 hexadecimal characters: ${file.source}`, { path: file.source }));
    else if (file.sha256 !== null && strictInventory && !sourceRecord?.sha256) errors.push(issue("unverified_sha256", `Could not verify the declared SHA-256 for ${file.source}.`, { path: file.source }));
    else if (file.sha256 !== null && sourceRecord?.sha256 && sourceRecord.sha256.toLowerCase() !== file.sha256) errors.push(issue("sha256_mismatch", `File content does not match the manifest SHA-256: ${file.source}`, { path: file.source }));
    if (sourceRecord?.file?.size === 0 && file.sha256 === null) warnings.push(issue("empty_file", `Empty file: ${file.source}`, { path: file.source }));
  }

  // Imported directories can lack a manifest-linked inventory in demo mode; a real
  // import always supplies uploadedFiles and therefore receives strict source checks.
  return {
    ok: errors.length === 0,
    errors,
    warnings,
    mod: errors.length === 0 ? {
      id,
      name: name.trim(),
      gameId,
      version,
      gameVersion: typeof selectedGameVersion === "string" && selectedGameVersion.trim() ? selectedGameVersion : gameVersion,
      compatibleGameVersion: gameVersion,
      manifestFormat: workshopManifest ? "koei-mod-workshop.v1" : "koei-mod-sandbox.v1",
      author: typeof manifest.author === "string" ? manifest.author.slice(0, 120) : "Unknown",
      description: typeof manifest.description === "string" ? manifest.description.slice(0, 500) : "",
      platform: workshopManifest ? manifest.platform : "Windows PC",
      dependencies,
      files,
      status: "ready",
    } : null,
  };
}

/** Compare planned destinations; collisions are case-insensitive for Windows installs. */
export function detectConflicts(mods, baselinePaths = []) {
  const groups = new Map();
  const conflicts = [];
  const baseline = new Map();
  const baselineDirectories = new Set();
  for (const item of baselinePaths) {
    const path = typeof item === "string" ? item : item.path;
    try {
      const safePath = sanitizeRelativePath(path);
      const key = safePath.toLocaleLowerCase("en-US");
      baseline.set(key, safePath);
      const segments = key.split("/");
      for (let i = 1; i < segments.length; i++) baselineDirectories.add(segments.slice(0, i).join("/"));
    } catch { /* invalid baseline rows are ignored and reported by baseline validation */ }
  }
  for (const mod of mods) {
    for (const file of mod.files || []) {
      try {
        const path = sanitizeRelativePath(file.target ?? file.installPath ?? file.source ?? file.path);
        const key = path.toLocaleLowerCase("en-US");
        const item = groups.get(key) || { path, mods: [] };
        item.mods.push(mod.name || mod.id || "Unnamed mod");
        groups.set(key, item);
      } catch (error) {
        conflicts.push(issue(error.code || "unsafe_target", `Unsafe destination in ${mod.name || mod.id}: ${error.message}`));
      }
    }
  }
  const targetGroups = Array.from(groups.entries());
  for (const [key, group] of targetGroups) {
    const segments = key.split("/");
    for (let i = 1; i < segments.length; i++) {
      const parent = segments.slice(0, i).join("/");
      const parentGroup = groups.get(parent);
      if (parentGroup) conflicts.push(issue("file_directory_collision", `A mod writes a file where another destination needs a directory.`, { path: group.path, otherPath: parentGroup.path, mods: [...new Set([...group.mods, ...parentGroup.mods])] }));
    }
  }
  const changes = [];
  for (const [key, group] of groups) {
    const existing = baseline.get(key);
    changes.push({ path: group.path, action: existing ? "replace" : "add", existingPath: existing || null, mods: group.mods });
    const segments = key.split("/");
    for (let i = 1; i < segments.length; i++) {
      const parent = segments.slice(0, i).join("/");
      if (baseline.has(parent)) conflicts.push(issue("baseline_file_directory_collision", "A staged destination is nested beneath an existing baseline file.", { path: group.path, otherPath: baseline.get(parent), mods: group.mods }));
    }
    if (!existing && baselineDirectories.has(key)) conflicts.push(issue("baseline_file_directory_collision", "A staged file destination collides with a directory that contains baseline files.", { path: group.path, mods: group.mods }));
    if (group.mods.length > 1) {
      conflicts.push(issue("destination_collision", `${group.mods.length} mods target the same install path.`, { path: group.path, mods: group.mods }));
    }
  }
  return { conflicts, changes };
}

export function buildWorkspacePlan(mods, baselinePaths = [], workspace = {}) {
  const validationIssues = [];
  const compatibilityWarnings = [];
  const expectedGameId = workspace.gameId ?? mods[0]?.gameId ?? null;
  const expectedGameVersion = workspace.gameVersion ?? mods[0]?.gameVersion ?? null;
  if (!expectedGameId || !expectedGameVersion) validationIssues.push(issue("workspace_profile", "Select a game and exact game build/profile."));
  for (const mod of mods) {
    if (mod.valid === false || mod.status === "blocked") {
      validationIssues.push(issue("mod_not_valid", `${mod.name || mod.id || "A mod"} has not passed manifest validation.`, { modId: mod.id }));
    }
    if (mod.gameId !== expectedGameId || mod.gameVersion !== expectedGameVersion) validationIssues.push(issue("profile_mismatch", `${mod.name || mod.id || "A mod"} does not exactly match the selected game and build/profile.`, { modId: mod.id }));
  }
  const byId = new Map(mods.map((mod) => [String(mod.id || "").toLocaleLowerCase("en-US"), mod]));
  const duplicateIds = new Set();
  for (const mod of mods) {
    const key = String(mod.id || "").toLocaleLowerCase("en-US");
    if (!key || duplicateIds.has(key)) {
      validationIssues.push(issue("duplicate_mod_id", `Mod ID ${mod.id || "(empty)"} appears more than once in this workspace.`, { modId: mod.id || null }));
    } else duplicateIds.add(key);
  }
  for (const mod of mods) {
    for (const dependency of mod.dependencies || []) {
      const found = byId.get(String(dependency.id || "").toLocaleLowerCase("en-US"));
      const row = !found
        ? issue("dependency_missing", `${mod.name || mod.id} requires ${dependency.id} ${dependency.version}, which is not staged in this workspace.`, { modId: mod.id, dependencyId: dependency.id })
        : !versionSatisfies(found.version, dependency.version)
          ? issue("dependency_version", `${mod.name || mod.id} requires ${dependency.id} ${dependency.version}; staged version ${found.version} does not satisfy it.`, { modId: mod.id, dependencyId: dependency.id })
          : null;
      if (row) (dependency.optional ? compatibilityWarnings : validationIssues).push(row);
    }
  }
  const { conflicts, changes } = detectConflicts(mods, baselinePaths);
  return {
    ok: validationIssues.length === 0 && conflicts.length === 0 && mods.length > 0,
    gameId: expectedGameId,
    gameVersion: expectedGameVersion,
    modCount: mods.length,
    fileCount: changes.length,
    validationIssues,
    compatibilityWarnings,
    conflicts,
    changes,
    createdAt: new Date().toISOString(),
  };
}

/** Emit the Troubleshooting Center's report shape for sandbox-only findings. */
export function createTroubleshootingCenterReport(plan, mods, gameId, gameVersion = plan.gameVersion) {
  const game = SUPPORTED_GAMES.find((entry) => entry.id === gameId);
  const hasFindings = mods.length > 0;
  const failed = plan.validationIssues.length > 0 || plan.conflicts.length > 0;
  const status = !hasFindings ? "not_checked" : failed ? "failed" : (plan.compatibilityWarnings || []).length ? "warning" : "passed";
  const evidence = [
    `Sandbox-selected build/profile: ${String(gameVersion || "unknown").replace(/[\u0000-\u001f\u007f]/g, " ").slice(0, 80)}.`,
    `Staged mod packages: ${plan.modCount}.`,
    `Planned destination changes: ${plan.fileCount}.`,
    `Manifest validation issues: ${plan.validationIssues.length}.`,
    `Destination conflicts: ${plan.conflicts.length}.`,
    `Compatibility warnings: ${(plan.compatibilityWarnings || []).length}.`,
  ];
  const findings = [{
    id: "sandbox.preflight",
    category: "mods",
    status,
    severity: failed ? "error" : status === "warning" ? "warning" : "info",
    title: "Mod Testing Sandbox preflight",
    summary: !hasFindings
      ? "No mod package was staged, so sandbox manifest and destination checks were not performed."
      : failed
        ? "The sandbox preflight found manifest validation issues or destination conflicts that need review before export."
        : status === "warning"
          ? "The sandbox preflight passed its blocking checks and found compatibility warnings for review."
          : "The staged manifests and planned destinations passed the sandbox's bounded preflight checks.",
    evidence,
    recommendation: failed
      ? "Resolve the listed sandbox validation issues and destination conflicts, then run the preflight again."
      : status === "warning"
        ? "Review compatibility warnings and confirm the selected game/build profile before any separate deployment action."
        : "Review the sandbox report and use the game's own validation process before applying staged files.",
    source: "Mod Testing Sandbox",
  }, {
    id: "sandbox.installation_not_checked",
    category: "mods",
    status: "not_checked",
    severity: "info",
    title: "Game installation and runtime not checked",
    summary: "This report covers browser-staged manifest data only; it does not inspect an installed game, loaded mods, or game behavior.",
    evidence: ["No game installation or runtime files were read.", "No mod code or game executable was run."],
    recommendation: "Use the Troubleshooting Center's read-only selected-folder checks and the game's normal validation process for installation-level evidence.",
    source: "Mod Testing Sandbox",
  }];
  const overallStatus = status === "failed" ? "failed" : status === "warning" ? "warning" : "partial";
  return {
    schema: "koei-game-troubleshooting",
    schema_version: 1,
    ruleset_version: "mod-testing-sandbox-1",
    read_only: true,
    game_id: gameId || "unknown",
    title: game?.label || "Unknown game",
    platform: "Windows PC",
    overall_status: overallStatus,
    findings,
  };
}

export function createAuditReport(plan, mods, selectedGameId, selectedGameVersion = plan.gameVersion) {
  const game = SUPPORTED_GAMES.find((entry) => entry.id === selectedGameId);
  return JSON.stringify({
    reportType: "koei-tecmo-mod-sandbox-audit",
    reportVersion: 1,
    generatedAt: new Date().toISOString(),
    selectedGame: game ? { id: game.id, name: game.label, gameVersion: selectedGameVersion || "unknown" } : { id: selectedGameId || "unknown", name: "Unknown game", gameVersion: selectedGameVersion || "unknown" },
    safety: {
      codeExecuted: false,
      sourceFilesModified: false,
      gameInstallationRead: false,
      deploymentRequiresExplicitConfirmation: true,
      stagedFilesRemainInBrowserWorkspace: true,
    },
    compatibility: { source: "manifest declarations checked against the selected game/build; Workshop version ranges are supported", gameId: selectedGameId, gameVersion: selectedGameVersion || "unknown", independentlyVerified: false, nativeFormatDetection: false, modManagerValidated: false },
    summary: { ready: plan.ok, modCount: plan.modCount, fileCount: plan.fileCount, conflictCount: plan.conflicts.length },
    mods: mods.map((mod) => ({ id: mod.id, name: mod.name, version: mod.version, gameId: mod.gameId, gameVersion: mod.gameVersion, compatibleGameVersion: mod.compatibleGameVersion || mod.gameVersion, platform: mod.platform || "Windows PC", manifestFormat: mod.manifestFormat || "koei-mod-sandbox.v1", dependencies: mod.dependencies || [], valid: mod.valid !== false && mod.status !== "blocked", files: (mod.files || []).map((file) => ({ source: file.source, target: file.target })) })),
    validationIssues: plan.validationIssues,
    compatibilityWarnings: plan.compatibilityWarnings || [],
    conflicts: plan.conflicts,
    changes: plan.changes,
  }, null, 2);
}

/** Build the inert ProfileComponentSnapshot contract consumed by Mod Manager. */
export function buildProfileComponentSnapshot(gameId, gameVersion, payload) {
  if (!PROFILE_COMPONENT_GAME_IDS.has(gameId)) throw new Error("Component snapshot requires a registered initial title profile ID.");
  if (typeof gameVersion !== "string" || !gameVersion.trim() || gameVersion.length > 80 || /[\u0000-\u001f\u007f]/.test(gameVersion)) throw new Error("Component snapshot requires a printable, exact game build/profile string.");
  const pending = [[payload, 0]];
  let nodeCount = 0;
  while (pending.length) {
    const [value, depth] = pending.pop();
    nodeCount++;
    if (nodeCount > 10_000 || depth > 32) throw new Error("Mod Manager component payload exceeds its 10,000-node or 32-level structural bound.");
    if (value === null || typeof value === "string" || typeof value === "boolean") continue;
    if (typeof value === "number") {
      if (!Number.isFinite(value)) throw new Error("Mod Manager component payload must contain only finite JSON numbers.");
      continue;
    }
    if (Array.isArray(value)) {
      for (const item of value) pending.push([item, depth + 1]);
      continue;
    }
    if (!value || typeof value !== "object" || Object.getPrototypeOf(value) !== Object.prototype) throw new Error("Mod Manager component payload must contain plain JSON data only.");
    for (const [key, item] of Object.entries(value)) {
      if (typeof key !== "string") throw new Error("Mod Manager component payload fields must be strings.");
      pending.push([item, depth + 1]);
    }
  }
  const snapshot = {
    component: "mod_configuration",
    provider: "mod_manager",
    schema_version: 1,
    game_id: gameId,
    game_version: gameVersion,
    payload,
  };
  const serialized = JSON.stringify(snapshot, null, 2);
  if (encoder.encode(serialized).byteLength > LIMITS.manifestBytes) throw new Error("Mod Manager component snapshot exceeds the 256 KiB limit.");
  return snapshot;
}

const crcTable = (() => {
  const table = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = (c & 1) ? (0xedb88320 ^ (c >>> 1)) : (c >>> 1);
    table[n] = c >>> 0;
  }
  return table;
})();

function crc32(data) {
  let c = 0xffffffff;
  for (const byte of data) c = crcTable[(c ^ byte) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

function bytesOf(value) {
  if (value instanceof Uint8Array) return value;
  if (value instanceof ArrayBuffer) return new Uint8Array(value);
  if (ArrayBuffer.isView(value)) return new Uint8Array(value.buffer, value.byteOffset, value.byteLength);
  if (typeof value === "string") return encoder.encode(value);
  throw new TypeError("ZIP entries must contain bytes, text, or a Blob/File.");
}

/** Build a plain ZIP (store method); accepts only safe relative paths and never evaluates content. */
export async function createZipBlob(entries) {
  if (!Array.isArray(entries) || !entries.length || entries.length > LIMITS.fileCount) throw new Error("ZIP entry count is outside the supported range.");
  const prepared = [];
  const names = new Set();
  const directories = new Set();
  let totalBytes = 0;
  for (const entry of entries) {
    const name = sanitizeRelativePath(entry.path);
    const key = name.toLocaleLowerCase("en-US");
    if ((key === ".koei-mod-sandbox" || key.startsWith(".koei-mod-sandbox/")) && entry.system !== true) throw new Error("The .koei-mod-sandbox ZIP metadata namespace is reserved.");
    if (names.has(key)) throw new Error(`ZIP contains colliding paths: ${name}`);
    if (directories.has(key)) throw new Error(`ZIP file path collides with a directory path: ${name}`);
    const segments = key.split("/");
    for (let i = 1; i < segments.length; i++) {
      const parent = segments.slice(0, i).join("/");
      if (names.has(parent)) throw new Error(`ZIP file path is nested under another file: ${name}`);
      directories.add(parent);
    }
    names.add(key);
    if (entry.data instanceof Blob && (entry.data.size > LIMITS.fileBytes || totalBytes + entry.data.size > LIMITS.fileBytes)) throw new Error("ZIP payload exceeds the 256 MiB size limit.");
    if (!(entry.data instanceof Blob)) {
      const candidate = bytesOf(entry.data);
      if (candidate.byteLength > LIMITS.fileBytes || totalBytes + candidate.byteLength > LIMITS.fileBytes) throw new Error("ZIP payload exceeds the 256 MiB size limit.");
    }
    const raw = entry.data instanceof Blob ? new Uint8Array(await entry.data.arrayBuffer()) : bytesOf(entry.data);
    totalBytes += raw.byteLength;
    if (raw.byteLength > LIMITS.fileBytes || totalBytes > LIMITS.fileBytes) throw new Error("ZIP payload exceeds the 256 MiB size limit.");
    prepared.push({ nameBytes: encoder.encode(name), data: raw, crc: crc32(raw) });
  }

  let localSize = 0;
  let centralSize = 0;
  for (const entry of prepared) {
    localSize += 30 + entry.nameBytes.length + entry.data.byteLength;
    centralSize += 46 + entry.nameBytes.length;
  }
  const totalSize = localSize + centralSize + 22;
  if (totalSize > 0xffffffff) throw new Error("ZIP exceeds the classic ZIP format limit.");
  const bytes = new Uint8Array(totalSize);
  const view = new DataView(bytes.buffer);
  let offset = 0;
  let centralOffset = localSize;
  for (const entry of prepared) {
    const localOffset = offset;
    view.setUint32(offset, 0x04034b50, true); view.setUint16(offset + 4, 20, true); view.setUint16(offset + 6, 0x0800, true);
    view.setUint16(offset + 8, 0, true); view.setUint16(offset + 10, 0, true); view.setUint16(offset + 12, 0x0021, true);
    view.setUint32(offset + 14, entry.crc, true); view.setUint32(offset + 18, entry.data.byteLength, true); view.setUint32(offset + 22, entry.data.byteLength, true);
    view.setUint16(offset + 26, entry.nameBytes.length, true); view.setUint16(offset + 28, 0, true);
    bytes.set(entry.nameBytes, offset + 30); bytes.set(entry.data, offset + 30 + entry.nameBytes.length);
    offset += 30 + entry.nameBytes.length + entry.data.byteLength;
    view.setUint32(centralOffset, 0x02014b50, true); view.setUint16(centralOffset + 4, 20, true); view.setUint16(centralOffset + 6, 20, true);
    view.setUint16(centralOffset + 8, 0x0800, true); view.setUint16(centralOffset + 10, 0, true); view.setUint16(centralOffset + 12, 0, true); view.setUint16(centralOffset + 14, 0x0021, true);
    view.setUint32(centralOffset + 16, entry.crc, true); view.setUint32(centralOffset + 20, entry.data.byteLength, true); view.setUint32(centralOffset + 24, entry.data.byteLength, true);
    view.setUint16(centralOffset + 28, entry.nameBytes.length, true); view.setUint16(centralOffset + 30, 0, true); view.setUint16(centralOffset + 32, 0, true);
    view.setUint16(centralOffset + 34, 0, true); view.setUint16(centralOffset + 36, 0, true); view.setUint32(centralOffset + 38, 0, true); view.setUint32(centralOffset + 42, localOffset, true);
    bytes.set(entry.nameBytes, centralOffset + 46);
    centralOffset += 46 + entry.nameBytes.length;
  }
  offset = centralOffset;
  view.setUint32(offset, 0x06054b50, true); view.setUint16(offset + 4, 0, true); view.setUint16(offset + 6, 0, true);
  view.setUint16(offset + 8, prepared.length, true); view.setUint16(offset + 10, prepared.length, true); view.setUint32(offset + 12, centralSize, true);
  view.setUint32(offset + 16, localSize, true); view.setUint16(offset + 20, 0, true);
  return new Blob([bytes], { type: "application/zip" });
}

/** Build the Nioh 2 Mod Manager's inert import ZIP; the manager performs its own validation. */
export async function createNioh2ManagerPackageBlob(mod) {
  if (!mod || mod.gameId !== "nioh2_pc" || mod.valid === false || !Array.isArray(mod.files) || !mod.files.length) {
    throw new Error("The Nioh 2 Mod Manager handoff requires one validated Nioh 2 package.");
  }
  const id = String(mod.id || "").toLocaleLowerCase("en-US");
  if (!/^[a-z0-9][a-z0-9._-]{1,47}$/.test(id) || id.includes("disabled")) {
    throw new Error("The Nioh 2 Mod Manager requires a 2–48 character safe mod ID without 'disabled'.");
  }
  if (typeof mod.name !== "string" || !mod.name.trim() || mod.name.trim().length > 120) throw new Error("The Nioh 2 Mod Manager requires a name of 1–120 characters.");
  if (typeof mod.version !== "string" || !mod.version.trim() || mod.version.length > 80) throw new Error("The Nioh 2 Mod Manager requires a version of 1–80 characters.");

  const iniFiles = mod.files.filter((file) => typeof file.target === "string" && file.target.toLocaleLowerCase("en-US").endsWith(".ini"));
  const assetExtensions = new Set([".fmt", ".vb", ".ib", ".dds"]);
  const assets = mod.files.filter((file) => typeof file.target === "string" && assetExtensions.has(file.target.slice(file.target.lastIndexOf(".")).toLocaleLowerCase("en-US")));
  if (iniFiles.length !== 1 || assets.length === 0) throw new Error("Nioh 2 manager packages need exactly one .ini target and at least one .fmt, .vb, .ib, or .dds target.");
  const iniPath = sanitizeRelativePath(iniFiles[0].target);
  const modRoot = iniPath.includes("/") ? iniPath.slice(0, iniPath.lastIndexOf("/")) : "";
  const targets = new Set();
  const entries = [{ path: "koei-mod.json", data: JSON.stringify({
    schema_version: 1,
    game_id: "nioh2_pc",
    id,
    name: mod.name.trim(),
    version: mod.version.trim(),
    dependencies: (mod.dependencies || []).filter((dependency) => !dependency.optional).map((dependency) => {
      const dependencyId = String(dependency.id || "").toLocaleLowerCase("en-US");
      if (!/^[a-z0-9][a-z0-9._-]{1,47}$/.test(dependencyId) || dependencyId.includes("disabled")) throw new Error("A required dependency cannot be represented by the Nioh 2 Mod Manager contract.");
      return dependencyId;
    }),
    conflicts: [],
  }, null, 2) }];
  for (const file of mod.files) {
    const target = sanitizeRelativePath(file.target);
    const key = target.toLocaleLowerCase("en-US");
    if (targets.has(key)) throw new Error(`Nioh 2 package contains colliding targets: ${target}`);
    targets.add(key);
    if (modRoot && !target.startsWith(`${modRoot}/`)) throw new Error("All Nioh 2 package files must be inside the folder containing the .ini marker.");
    if (target.toLocaleLowerCase("en-US") === iniPath.toLocaleLowerCase("en-US")) continue;
    const extension = target.slice(target.lastIndexOf(".")).toLocaleLowerCase("en-US");
    if (!assetExtensions.has(extension)) throw new Error(`Unsupported Nioh 2 Mod Manager asset type: ${target}`);
    const payload = mod.payloads?.get(file.source);
    if (!payload) throw new Error(`Staged payload is missing: ${file.source}`);
    entries.push({ path: target, data: payload });
  }
  const iniPayload = mod.payloads?.get(iniFiles[0].source);
  if (!iniPayload) throw new Error(`Staged payload is missing: ${iniFiles[0].source}`);
  entries.push({ path: iniPath, data: iniPayload });
  return createZipBlob(entries);
}
