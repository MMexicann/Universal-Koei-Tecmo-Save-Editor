"""Tkinter interface for the Koei Tecmo Mod Creation Workshop."""

from __future__ import annotations

import json
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from .asset_explorer import register_replacement
from .models import Dependency, ModManifest
from .packaging import build_package, verify_package
from .project_manager import (
    add_dependency,
    initialize_project,
    load_project,
    remove_dependency,
    save_manifest,
)
from .templates import list_templates
from .validation import CompatibilityContext, InstalledMod, validate_manifest, validate_project


class ModWorkshopWindow:
    """A focused project workspace; game files are never browsed or extracted."""

    def __init__(self, parent: tk.Misc):
        self.parent = parent
        self.window = tk.Toplevel(parent)
        self.window.title("Koei Tecmo Mod Creation Workshop")
        self.window.geometry("1120x800")
        self.window.minsize(880, 640)
        self.window.transient(parent)
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.project_dir: Path | None = None
        self.manifest: ModManifest | None = None
        self.last_context: CompatibilityContext | None = None
        self.last_validation: dict | None = None
        self.last_package_report: dict | None = None
        self.status = tk.StringVar(self.window, value="Create or open a mod project to begin.")

        header = ttk.Frame(self.window, padding=(22, 16, 22, 8))
        header.pack(fill="x")
        ttk.Label(header, text="MOD CREATION WORKSHOP", font=("TkDefaultFont", 18, "bold")).pack(anchor="w")
        ttk.Label(
            header,
            text="Build a mod from files you created or may redistribute. Original game assets are never extracted or packaged.",
            style="Muted.TLabel",
            wraplength=1040,
        ).pack(anchor="w", pady=(5, 0))

        notice = ttk.LabelFrame(self.window, text="Packaging and validation scope", padding=(12, 8))
        notice.pack(fill="x", padx=22, pady=(4, 10))
        ttk.Label(
            notice,
            text=(
                "The package verifier checks manifest fields, safe archive paths and file hashes. "
                "Compatibility compares the game/build and installed dependencies you enter. "
                "Asset rights are self-declared; neither ownership nor in-game loading is independently verified."
            ),
            wraplength=1040,
            justify="left",
        ).pack(anchor="w")

        self.notebook = ttk.Notebook(self.window)
        self.notebook.pack(fill="both", expand=True, padx=22, pady=(0, 10))
        self.project_tab = ttk.Frame(self.notebook, padding=16)
        self.assets_tab = ttk.Frame(self.notebook, padding=16)
        self.dependencies_tab = ttk.Frame(self.notebook, padding=16)
        self.compatibility_tab = ttk.Frame(self.notebook, padding=16)
        self.package_tab = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(self.project_tab, text="Project")
        self.notebook.add(self.assets_tab, text="Replacements")
        self.notebook.add(self.dependencies_tab, text="Dependencies")
        self.notebook.add(self.compatibility_tab, text="Compatibility")
        self.notebook.add(self.package_tab, text="Package")
        self._build_project_tab()
        self._build_assets_tab()
        self._build_dependencies_tab()
        self._build_compatibility_tab()
        self._build_package_tab()
        ttk.Label(self.window, textvariable=self.status, style="Muted.TLabel", padding=(22, 0, 22, 14)).pack(anchor="w")

    def _build_project_tab(self) -> None:
        frame = self.project_tab
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(3, weight=1)
        ttk.Label(frame, text="Starter template").grid(row=0, column=0, sticky="w", pady=5)
        self.template_by_name = {template.name: template.template_id for template in list_templates()}
        self.template_choice = tk.StringVar(self.window, value=list(self.template_by_name)[0])
        ttk.Combobox(
            frame,
            textvariable=self.template_choice,
            values=tuple(self.template_by_name),
            state="readonly",
            width=36,
        ).grid(row=0, column=1, columnspan=3, sticky="ew", padx=(10, 0), pady=5)

        ttk.Label(frame, text="Project parent folder").grid(row=1, column=0, sticky="w", pady=5)
        self.project_parent = tk.StringVar(self.window)
        ttk.Entry(frame, textvariable=self.project_parent).grid(row=1, column=1, columnspan=2, sticky="ew", padx=(10, 8), pady=5)
        ttk.Button(frame, text="Choose…", command=self._choose_parent).grid(row=1, column=3, sticky="e", pady=5)
        self.project_path_hint = ttk.Label(frame, text="A new folder named with the mod ID will be created under the selected parent.",
                                           style="Muted.TLabel", wraplength=840)
        self.project_path_hint.grid(row=2, column=1, columnspan=3, sticky="w", padx=(10, 0), pady=(0, 10))

        self.fields = {
            key: tk.StringVar(self.window)
            for key in ("mod_id", "name", "version", "author", "game_id", "game_version", "platform", "license")
        }
        field_rows = (
            ("mod_id", "Mod ID", "name", "Display name"),
            ("version", "Mod version", "author", "Author"),
            ("game_id", "Game ID", "game_version", "Compatible game version / range"),
            ("platform", "Platform", "license", "Mod license"),
        )
        row = 3
        for left_key, left_label, right_key, right_label in field_rows:
            ttk.Label(frame, text=left_label).grid(row=row, column=0, sticky="w", pady=5)
            ttk.Entry(frame, textvariable=self.fields[left_key]).grid(row=row, column=1, sticky="ew", padx=(10, 18), pady=5)
            ttk.Label(frame, text=right_label).grid(row=row, column=2, sticky="w", pady=5)
            ttk.Entry(frame, textvariable=self.fields[right_key]).grid(row=row, column=3, sticky="ew", padx=(10, 0), pady=5)
            row += 1

        ttk.Label(frame, text="Description").grid(row=row, column=0, sticky="nw", pady=5)
        self.description = ScrolledText(frame, height=5, wrap="word")
        self.description.grid(row=row, column=1, columnspan=3, sticky="nsew", padx=(10, 0), pady=5)
        frame.rowconfigure(row, weight=1)
        row += 1

        buttons = ttk.Frame(frame)
        buttons.grid(row=row, column=0, columnspan=4, sticky="ew", pady=(12, 0))
        ttk.Button(buttons, text="Create project", command=self.create_project).pack(side="left")
        ttk.Button(buttons, text="Open project…", command=self.open_project).pack(side="left", padx=(8, 0))
        ttk.Button(buttons, text="Save metadata", command=self.save_project).pack(side="left", padx=(8, 0))
        self.current_path = tk.StringVar(self.window, value="No project is open.")
        ttk.Label(frame, textvariable=self.current_path, style="Muted.TLabel", wraplength=900).grid(
            row=row + 1, column=0, columnspan=4, sticky="w", pady=(10, 0)
        )

    def _build_assets_tab(self) -> None:
        frame = self.assets_tab
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        self.asset_tree = ttk.Treeview(
            frame,
            columns=("source", "license", "rights", "sha"),
            show="tree headings",
            selectmode="browse",
            height=9,
        )
        self.asset_tree.heading("#0", text="Game destination")
        self.asset_tree.heading("source", text="Project file")
        self.asset_tree.heading("license", text="License")
        self.asset_tree.heading("rights", text="Rights declaration")
        self.asset_tree.heading("sha", text="SHA-256")
        self.asset_tree.column("#0", width=250)
        self.asset_tree.column("source", width=210)
        self.asset_tree.column("license", width=125)
        self.asset_tree.column("rights", width=155)
        self.asset_tree.column("sha", width=145)
        self.asset_tree.grid(row=0, column=0, columnspan=4, sticky="nsew")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.asset_tree.yview)
        scroll.grid(row=0, column=4, sticky="ns")
        self.asset_tree.configure(yscrollcommand=scroll.set)

        ttk.Label(frame, text="Target path").grid(row=1, column=0, sticky="w", pady=(12, 4))
        self.target_path = tk.StringVar(self.window)
        ttk.Entry(frame, textvariable=self.target_path).grid(row=1, column=1, columnspan=3, sticky="ew", padx=(8, 0), pady=(12, 4))
        ttk.Label(frame, text="License").grid(row=2, column=0, sticky="w", pady=4)
        self.asset_license = tk.StringVar(self.window)
        ttk.Entry(frame, textvariable=self.asset_license).grid(row=2, column=1, sticky="ew", padx=(8, 16), pady=4)
        ttk.Label(frame, text="Rights status").grid(row=2, column=2, sticky="w", pady=4)
        self.asset_rights = tk.StringVar(self.window, value="creator-owned")
        ttk.Combobox(
            frame,
            textvariable=self.asset_rights,
            values=("creator-owned", "permissive-license", "public-domain"),
            state="readonly",
            width=22,
        ).grid(row=2, column=3, sticky="ew", padx=(8, 0), pady=4)
        ttk.Label(frame, text="Attribution (required for permissive-license)").grid(row=3, column=0, sticky="w", pady=4)
        self.attribution = tk.StringVar(self.window)
        ttk.Entry(frame, textvariable=self.attribution).grid(row=3, column=1, columnspan=3, sticky="ew", padx=(8, 0), pady=4)
        actions = ttk.Frame(frame)
        actions.grid(row=4, column=0, columnspan=4, sticky="ew", pady=(10, 0))
        ttk.Button(actions, text="Add replacement file…", command=self.add_replacement).pack(side="left")
        ttk.Button(actions, text="Remove selected", command=self.remove_replacement).pack(side="left", padx=(8, 0))
        ttk.Label(
            frame,
            text="Choose files already inside this project. Use public documentation for destination paths; the workshop does not inspect game archives.",
            style="Muted.TLabel",
            wraplength=920,
        ).grid(row=5, column=0, columnspan=4, sticky="w", pady=(14, 0))

    def _build_dependencies_tab(self) -> None:
        frame = self.dependencies_tab
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        self.dependency_tree = ttk.Treeview(
            frame, columns=("mod_id", "version", "optional"), show="headings", height=10
        )
        self.dependency_tree.heading("version", text="Required version")
        self.dependency_tree.heading("optional", text="Optional")
        self.dependency_tree.heading("mod_id", text="Dependency ID")
        self.dependency_tree.column("mod_id", width=300)
        self.dependency_tree.column("version", width=220)
        self.dependency_tree.column("optional", width=120)
        self.dependency_tree.grid(row=0, column=0, columnspan=4, sticky="nsew")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.dependency_tree.yview)
        scroll.grid(row=0, column=4, sticky="ns")
        self.dependency_tree.configure(yscrollcommand=scroll.set)
        ttk.Label(frame, text="Dependency ID").grid(row=1, column=0, sticky="w", pady=(14, 4))
        self.dependency_id = tk.StringVar(self.window)
        ttk.Entry(frame, textvariable=self.dependency_id).grid(row=1, column=1, sticky="ew", padx=(8, 16), pady=(14, 4))
        ttk.Label(frame, text="Version rule").grid(row=1, column=2, sticky="w", pady=(14, 4))
        self.dependency_version = tk.StringVar(self.window, value="*")
        ttk.Entry(frame, textvariable=self.dependency_version).grid(row=1, column=3, sticky="ew", padx=(8, 0), pady=(14, 4))
        self.dependency_optional = tk.BooleanVar(self.window, value=False)
        ttk.Checkbutton(frame, text="Optional dependency", variable=self.dependency_optional).grid(
            row=2, column=1, sticky="w", padx=(8, 0), pady=4
        )
        actions = ttk.Frame(frame)
        actions.grid(row=3, column=0, columnspan=4, sticky="ew", pady=(8, 0))
        ttk.Button(actions, text="Add dependency", command=self.add_dependency).pack(side="left")
        ttk.Button(actions, text="Remove selected", command=self.remove_dependency).pack(side="left", padx=(8, 0))
        ttk.Label(frame, text="Use * for any version or comma-separated rules such as >=1.2.0,<2.0.0.",
                  style="Muted.TLabel").grid(row=4, column=0, columnspan=4, sticky="w", pady=(14, 0))

    def _build_compatibility_tab(self) -> None:
        frame = self.compatibility_tab
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(3, weight=1)
        ttk.Label(
            frame,
            text="Compare a project against the target details and installed mod versions you provide.",
            style="Muted.TLabel",
            wraplength=900,
        ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 12))
        self.context_fields = {
            key: tk.StringVar(self.window)
            for key in ("game_id", "game_version", "platform")
        }
        for row, key, label in (
            (1, "game_id", "Selected game ID"),
            (2, "game_version", "Selected game version"),
            (3, "platform", "Selected platform"),
        ):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=4)
            ttk.Entry(frame, textvariable=self.context_fields[key]).grid(row=row, column=1, columnspan=3, sticky="ew", padx=(8, 0), pady=4)
        ttk.Label(frame, text="Installed mods (one mod_id=version per line)").grid(
            row=4, column=0, columnspan=4, sticky="w", pady=(10, 4)
        )
        self.installed_mods_text = ScrolledText(frame, height=6, wrap="none")
        self.installed_mods_text.grid(row=5, column=0, columnspan=4, sticky="nsew")
        frame.rowconfigure(5, weight=1)
        ttk.Button(frame, text="Run compatibility check", command=self.run_compatibility_check).grid(
            row=6, column=0, sticky="w", pady=(10, 5)
        )
        ttk.Label(
            frame,
            text="This check uses the values entered here. It cannot detect the installed game build or confirm runtime behavior.",
            style="Muted.TLabel",
            wraplength=920,
        ).grid(row=6, column=1, columnspan=3, sticky="w", padx=(12, 0), pady=(10, 5))
        self.compatibility_output = ScrolledText(frame, height=10, wrap="word", state="disabled")
        self.compatibility_output.grid(row=7, column=0, columnspan=4, sticky="nsew", pady=(6, 0))
        frame.rowconfigure(7, weight=1)

    def _build_package_tab(self) -> None:
        frame = self.package_tab
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(2, weight=1)
        ttk.Label(
            frame,
            text=(
                "Build includes mod.json, verification.json and only the replacement files listed in the project. "
                "No original game files, archives or unrelated project files are included."
            ),
            wraplength=920,
            justify="left",
        ).grid(row=0, column=0, sticky="w", pady=(0, 10))
        buttons = ttk.Frame(frame)
        buttons.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(buttons, text="Build verified ZIP…", command=self.build_package).pack(side="left")
        ttk.Button(buttons, text="Verify ZIP…", command=self.verify_package).pack(side="left", padx=(8, 0))
        ttk.Button(buttons, text="Export AI-readable report…", command=self.export_report).pack(side="left", padx=(8, 0))
        self.package_output = ScrolledText(frame, wrap="word", state="disabled")
        self.package_output.grid(row=2, column=0, sticky="nsew")

    def _choose_parent(self) -> None:
        folder = filedialog.askdirectory(parent=self.window, title="Choose the parent folder for a new mod project")
        if folder:
            self.project_parent.set(folder)

    def _read_form(self, *, include_project_records: bool = True) -> ModManifest:
        project_records = self.manifest if include_project_records else None
        return ModManifest(
            mod_id=self.fields["mod_id"].get().strip(),
            name=self.fields["name"].get().strip(),
            version=self.fields["version"].get().strip(),
            author=self.fields["author"].get().strip(),
            description=self.description.get("1.0", "end-1c").strip(),
            game_id=self.fields["game_id"].get().strip(),
            game_version=self.fields["game_version"].get().strip(),
            platform=self.fields["platform"].get().strip(),
            license=self.fields["license"].get().strip(),
            dependencies=project_records.dependencies if project_records else (),
            replacements=project_records.replacements if project_records else (),
        )

    def create_project(self) -> None:
        try:
            manifest = self._read_form(include_project_records=False)
            parent = Path(self.project_parent.get()).expanduser()
            if not self.project_parent.get().strip():
                raise ValueError("Choose a parent folder for the new project.")
            validation = validate_manifest(manifest)
            if not validation.valid:
                raise ValueError("Cannot create project: " + "; ".join(
                    item.message for item in validation.findings if item.severity == "error"
                ))
            project = parent / manifest.mod_id
            initialize_project(project, manifest, self.template_by_name[self.template_choice.get()])
            self._activate_project(project, manifest)
        except Exception as error:
            messagebox.showerror("Could not create project", str(error), parent=self.window)
            return
        self.status.set(f"Created project at {project}")

    def open_project(self) -> None:
        folder = filedialog.askdirectory(parent=self.window, title="Open a mod project folder")
        if not folder:
            return
        try:
            manifest = load_project(folder)
            self._activate_project(Path(folder), manifest)
        except Exception as error:
            messagebox.showerror("Could not open project", str(error), parent=self.window)
            return
        self.status.set(f"Opened {manifest.name}")

    def save_project(self, *, sync_context: bool = True) -> bool:
        if self.project_dir is None:
            self.status.set("Create or open a project before saving metadata.")
            return False
        try:
            manifest = self._read_form()
            validation = validate_manifest(manifest)
            if not validation.valid:
                raise ValueError("Cannot save project: " + "; ".join(
                    item.message for item in validation.findings if item.severity == "error"
                ))
            save_manifest(self.project_dir, manifest)
            self.manifest = manifest
            self._refresh_assets()
            self._refresh_dependencies()
            self.last_validation = None
            self.last_context = None
            self.last_package_report = None
            if sync_context:
                self._sync_context_from_manifest()
        except Exception as error:
            messagebox.showerror("Could not save project", str(error), parent=self.window)
            return False
        self.status.set("Project metadata saved.")
        return True

    def _activate_project(self, project: Path, manifest: ModManifest) -> None:
        self.project_dir = project.resolve()
        self.manifest = manifest
        for key in self.fields:
            self.fields[key].set(getattr(manifest, key))
        self.description.delete("1.0", "end")
        self.description.insert("1.0", manifest.description)
        self.project_parent.set(str(project.parent))
        self.project_path_hint.configure(text=f"Open project: {project}")
        self.current_path.set(str(project))
        self._sync_context_from_manifest()
        self._refresh_assets()
        self._refresh_dependencies()
        self.last_context = None
        self.last_validation = None
        self.last_package_report = None
        self.status.set(f"Opened {manifest.name}")

    def _sync_context_from_manifest(self) -> None:
        if self.manifest is None:
            return
        for key in self.context_fields:
            self.context_fields[key].set(getattr(self.manifest, key))

    def _require_project(self) -> bool:
        if self.project_dir is None or self.manifest is None:
            messagebox.showinfo("Open a project first", "Create or open a project on the Project tab first.", parent=self.window)
            self.notebook.select(self.project_tab)
            return False
        return True

    def add_replacement(self) -> None:
        if not self._require_project():
            return
        assets = self.project_dir / "assets"
        assets.mkdir(parents=True, exist_ok=True)
        source = filedialog.askopenfilename(parent=self.window, title="Choose a replacement file inside the project",
                                            initialdir=assets)
        if not source:
            return
        try:
            record = register_replacement(
                self.project_dir,
                source,
                self.target_path.get(),
                license=self.asset_license.get(),
                rights_status=self.asset_rights.get(),
                attribution=self.attribution.get(),
            )
            assert self.manifest is not None
            if any(item.target_path.casefold() == record.target_path.casefold() for item in self.manifest.replacements):
                raise ValueError(f"A replacement is already registered for {record.target_path}.")
            manifest = ModManifest(**{
                **self.manifest.__dict__,
                "replacements": self.manifest.replacements + (record,),
            })
            save_manifest(self.project_dir, manifest)
            self.manifest = manifest
            self.target_path.set("")
            self._refresh_assets()
            self.last_validation = None
            self.last_context = None
            self.last_package_report = None
        except Exception as error:
            messagebox.showerror("Could not add replacement", str(error), parent=self.window)
            return
        self.status.set(f"Registered replacement {record.target_path}")

    def remove_replacement(self) -> None:
        if not self._require_project():
            return
        selected = self.asset_tree.selection()
        if not selected:
            self.status.set("Select a replacement to remove.")
            return
        target = self.asset_tree.item(selected[0], "text")
        assert self.manifest is not None
        replacements = tuple(item for item in self.manifest.replacements if item.target_path != target)
        self.manifest = ModManifest(**{**self.manifest.__dict__, "replacements": replacements})
        save_manifest(self.project_dir, self.manifest)
        self._refresh_assets()
        self.last_validation = None
        self.last_context = None
        self.last_package_report = None
        self.status.set(f"Removed replacement {target}")

    def _refresh_assets(self) -> None:
        for child in self.asset_tree.get_children():
            self.asset_tree.delete(child)
        if self.manifest is None:
            return
        for item in self.manifest.replacements:
            self.asset_tree.insert(
                "",
                "end",
                text=item.target_path,
                values=(item.source_path, item.license, item.rights_status, item.sha256[:12] + "…"),
            )

    def add_dependency(self) -> None:
        if not self._require_project():
            return
        try:
            assert self.manifest is not None
            dependency = Dependency(
                mod_id=self.dependency_id.get().strip(),
                version=self.dependency_version.get().strip(),
                optional=self.dependency_optional.get(),
            )
            updated = add_dependency(self.manifest, dependency)
            save_manifest(self.project_dir, updated)
            self.manifest = updated
            self.dependency_id.set("")
            self.dependency_version.set("*")
            self.dependency_optional.set(False)
            self._refresh_dependencies()
            self.last_context = None
            self.last_validation = None
            self.last_package_report = None
        except Exception as error:
            messagebox.showerror("Could not add dependency", str(error), parent=self.window)
            return
        self.status.set(f"Declared dependency {dependency.mod_id}")

    def remove_dependency(self) -> None:
        if not self._require_project():
            return
        selected = self.dependency_tree.selection()
        if not selected:
            self.status.set("Select a dependency to remove.")
            return
        mod_id = self.dependency_tree.item(selected[0], "values")[0]
        assert self.manifest is not None
        self.manifest = remove_dependency(self.manifest, mod_id)
        save_manifest(self.project_dir, self.manifest)
        self._refresh_dependencies()
        self.last_context = None
        self.last_validation = None
        self.last_package_report = None
        self.status.set(f"Removed dependency {mod_id}")

    def _refresh_dependencies(self) -> None:
        for child in self.dependency_tree.get_children():
            self.dependency_tree.delete(child)
        if self.manifest is None:
            return
        for item in self.manifest.dependencies:
            self.dependency_tree.insert("", "end", values=(item.mod_id, item.version, "Yes" if item.optional else "No"))

    def _read_context(self) -> CompatibilityContext:
        installed = []
        for line_number, line in enumerate(self.installed_mods_text.get("1.0", "end-1c").splitlines(), start=1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                raise ValueError(f"Installed mod line {line_number} must use mod_id=version.")
            mod_id, version = (part.strip() for part in line.split("=", 1))
            if not mod_id or not version:
                raise ValueError(f"Installed mod line {line_number} needs both an ID and a version.")
            installed.append(InstalledMod(mod_id, version))
        return CompatibilityContext(
            game_id=self.context_fields["game_id"].get().strip(),
            game_version=self.context_fields["game_version"].get().strip(),
            platform=self.context_fields["platform"].get().strip(),
            installed_mods=tuple(installed),
        )

    def run_compatibility_check(self) -> None:
        if not self._require_project():
            return
        if not self.save_project(sync_context=False):
            return
        try:
            context = self._read_context()
            report = validate_project(self.project_dir, context)
        except Exception as error:
            messagebox.showerror("Compatibility check failed", str(error), parent=self.window)
            return
        data = report.to_dict()
        self._set_text(self.compatibility_output, json.dumps(data, indent=2, ensure_ascii=False))
        self.last_validation = data
        self.last_context = context if report.valid else None
        self.last_package_report = None
        if report.valid:
            self.status.set("Compatibility and source integrity checks passed for the entered context.")
        else:
            self.status.set(f"Compatibility check found {data['summary']['errors']} error(s). Review the report.")

    def build_package(self) -> None:
        if not self._require_project():
            return
        if not self.save_project(sync_context=False):
            return
        try:
            context = self._read_context()
        except Exception as error:
            messagebox.showerror("Invalid compatibility context", str(error), parent=self.window)
            return
        suggested = f"{self.manifest.mod_id}-{self.manifest.version}.zip"
        destination = filedialog.asksaveasfilename(
            parent=self.window,
            title="Save verified mod package",
            initialdir=str(self.project_dir.parent),
            initialfile=suggested,
            defaultextension=".zip",
            filetypes=(("Mod package", "*.zip"), ("All files", "*")),
        )
        if not destination:
            return
        try:
            report = build_package(self.project_dir, destination, context)
        except Exception as error:
            messagebox.showerror("Package was not created", str(error), parent=self.window)
            return
        self.last_package_report = report
        self.last_validation = report.get("compatibility", {}).get("validation")
        self.last_context = context
        self._set_text(self.package_output, json.dumps(report, indent=2, ensure_ascii=False))
        self.status.set(f"Verified package created: {destination}")

    def verify_package(self) -> None:
        package = filedialog.askopenfilename(
            parent=self.window,
            title="Choose a mod package to verify",
            filetypes=(("Mod package", "*.zip"), ("All files", "*")),
        )
        if not package:
            return
        try:
            report = verify_package(package)
        except Exception as error:
            messagebox.showerror("Package verification failed", str(error), parent=self.window)
            self.status.set("Package verification failed.")
            return
        self.last_package_report = report
        self._set_text(self.package_output, json.dumps(report, indent=2, ensure_ascii=False))
        self.status.set(f"Package verified: {package}")

    def export_report(self) -> None:
        report = self.last_package_report or self.last_validation
        if report is None:
            messagebox.showinfo("No report yet", "Run compatibility validation or verify a package first.", parent=self.window)
            return
        destination = filedialog.asksaveasfilename(
            parent=self.window,
            title="Export AI-readable validation report",
            defaultextension=".json",
            initialfile="mod-workshop-report.json",
            filetypes=(("JSON report", "*.json"), ("All files", "*")),
        )
        if not destination:
            return
        Path(destination).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        self.status.set(f"Validation report saved: {destination}")

    @staticmethod
    def _set_text(widget: ScrolledText, value: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.configure(state="disabled")

    def close(self) -> None:
        self.window.destroy()
