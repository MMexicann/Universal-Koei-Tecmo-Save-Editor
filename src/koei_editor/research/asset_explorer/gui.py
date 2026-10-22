"""Local, read-only asset inspection workspace for the desktop application."""

from __future__ import annotations

from base64 import b64encode
import math
from pathlib import Path, PurePosixPath
import queue
import threading
import tkinter as tk
from tkinter import filedialog, ttk

from koei_editor.research.asset_explorer.g1t import (
    MAX_FILE_SIZE as MAX_G1T_BYTES,
    TextureRecord,
    parse_g1t,
)
from koei_editor.research.asset_explorer.zip_archive import (
    ZipMember,
    parse_zip_archive,
    read_member,
)


MAX_GUI_G1T_BYTES = min(MAX_G1T_BYTES, 64 * 1024 * 1024)
MAX_MEDIA_BYTES = 32 * 1024 * 1024
MAX_LIST_ROWS = 2_000
IMAGE_EXTENSIONS = frozenset({"png", "dds"})
AUDIO_EXTENSIONS = frozenset({"wav", "flac", "ogg", "vorbis", "mp3"})
MODEL_EXTENSIONS = frozenset({"obj", "stl", "ply", "glb"})

_TEXT = {
    "en": {
        "open": "Open local file…", "back": "Back to archive", "filter": "Filter list",
        "name": "Name / texture", "kind": "Type", "size": "Bytes",
        "identity": "Format recognition does not identify a game or edition.",
        "idle": "Read-only inspection. Nothing is extracted or written.",
        "archive": "Standard ZIP container; game identity is not inferred.",
        "texture": "G1T subset recognized; title and edition are not inferred.",
        "media": "Generic media format; title and edition are not inferred.",
        "unsupported": "This file extension is outside the inspected format subset.",
        "busy": "Inspecting selected bytes…", "showing": "Showing {shown} of {total} entries.",
        "rows": "{total} entries.", "image": "{fmt} · {width} × {height} · {mode}",
        "audio": "{fmt} · {channels} channels · {rate} Hz · {duration}",
        "audio_preview": "Waveform preview: {duration} at {rate} Hz{truncated}.",
        "truncated": " · first 5 seconds only", "mesh": "{fmt} · {vertices} vertices · {faces} triangles",
        "bounds": "Bounds: {bounds}", "texture_line": "G1T v{version} · {fmt} · {width} × {height} · {mips} mip levels",
        "error": "Inspection failed: {error}", "choose": "Choose an archive, G1T texture file, image, audio file or model.",
        "directory": "Directory", "select_texture": "Select a texture to preview.", "mip": "Mip level",
    },
    "de": {
        "open": "Lokale Datei öffnen…", "back": "Zurück zum Archiv", "filter": "Liste filtern",
        "name": "Name / Textur", "kind": "Typ", "size": "Bytes",
        "identity": "Das Format allein bestimmt kein Spiel und keine Edition.",
        "idle": "Nur Lesezugriff. Es wird nichts entpackt oder gespeichert.",
        "archive": "Standard-ZIP-Container; Spielidentität wird nicht abgeleitet.",
        "texture": "G1T-Teilformat erkannt; Titel und Edition werden nicht abgeleitet.",
        "media": "Allgemeines Medienformat; Titel und Edition werden nicht abgeleitet.",
        "unsupported": "Diese Dateiendung gehört nicht zu den unterstützten Prüfformaten.",
        "busy": "Ausgewählte Bytes werden geprüft…", "showing": "{shown} von {total} Einträgen angezeigt.",
        "rows": "{total} Einträge.", "image": "{fmt} · {width} × {height} · {mode}",
        "audio": "{fmt} · {channels} Kanäle · {rate} Hz · {duration}",
        "audio_preview": "Wellenformvorschau: {duration} mit {rate} Hz{truncated}.",
        "truncated": " · nur die ersten 5 Sekunden", "mesh": "{fmt} · {vertices} Eckpunkte · {faces} Dreiecke",
        "bounds": "Grenzen: {bounds}", "texture_line": "G1T v{version} · {fmt} · {width} × {height} · {mips} Mip-Stufen",
        "error": "Prüfung fehlgeschlagen: {error}", "choose": "Wähle ein Archiv, eine G1T-Texturdatei, ein Bild, eine Audiodatei oder ein Modell.",
        "directory": "Ordner", "select_texture": "Wähle eine Textur zur Vorschau.", "mip": "Mip-Stufe",
    },
}


def _read_path_limited(path: Path, limit: int) -> bytes:
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f"file exceeds the {limit:,}-byte inspection limit")
    return data


def _extension(name: str) -> str:
    return PurePosixPath(name).suffix.lower().lstrip(".")


def _inspect_media(data: bytes, extension: str):
    from koei_editor.research.asset_explorer import media

    if extension in IMAGE_EXTENSIONS:
        return "image", media.inspect_image(data, extension)
    if extension in AUDIO_EXTENSIONS:
        return "audio", media.inspect_audio(data, extension)
    if extension in MODEL_EXTENSIONS:
        return "model", media.inspect_model(data, extension)
    return "unsupported", None


def _load_local(path_text: str):
    path = Path(path_text)
    extension = path.suffix.lower().lstrip(".")
    if extension == "zip":
        return "archive", path, parse_zip_archive(path)
    if extension == "g1t":
        data = _read_path_limited(path, MAX_GUI_G1T_BYTES)
        return "textures", path.name, data, parse_g1t(data), None
    if extension in IMAGE_EXTENSIONS | AUDIO_EXTENSIONS | MODEL_EXTENSIONS:
        data = _read_path_limited(path, MAX_MEDIA_BYTES)
        inspected, preview = _inspect_media(data, extension)
        if inspected == "unsupported":
            return "unsupported", path.name
        return inspected, path.name, preview, None
    return "unsupported", path.name


def _load_zip_member(path_text: str, member: ZipMember):
    extension = _extension(member.name)
    if member.is_directory:
        return "unsupported", member.name
    if extension == "g1t":
        data = read_member(path_text, member, max_bytes=MAX_GUI_G1T_BYTES)
        return "textures", member.name, data, parse_g1t(data), member
    if extension in IMAGE_EXTENSIONS | AUDIO_EXTENSIONS | MODEL_EXTENSIONS:
        data = read_member(path_text, member, max_bytes=MAX_MEDIA_BYTES)
        inspected, preview = _inspect_media(data, extension)
        if inspected == "unsupported":
            return "unsupported", member.name, member
        return inspected, member.name, preview, member
    return "unsupported", member.name, member


class AssetExplorerWorkspace:
    """A retained Tk workspace with no asset-write or extraction controls."""

    def __init__(self, root, parent, language="en"):
        self.root = root
        self.language = language if language in _TEXT else "en"
        self.frame = ttk.Frame(parent, padding=12)
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(2, weight=1)
        self._messages: queue.Queue = queue.Queue()
        self._generation = 0
        self._busy = False
        self._closed = False
        self._poll_id = None
        self._filter_id = None
        self._archive_path: str | None = None
        self._archive = None
        self._texture_member: ZipMember | None = None
        self._mode = "empty"
        self._texture_data: bytes | None = None
        self._textures: tuple[TextureRecord, ...] = ()
        self._selected_texture: TextureRecord | None = None
        self._items = ()
        self._item_by_id = {}
        self._status_detail = ""
        self._image_photo = None
        self._last_preview = None
        self._palette = {"background": "#f3f5f7", "surface": "#ffffff", "text": "#243142",
                         "muted": "#586879", "border": "#d8dfe6", "accent": "#92353b"}

        toolbar = ttk.Frame(self.frame)
        toolbar.grid(row=0, column=0, sticky="ew")
        self.open_button = ttk.Button(toolbar, command=self.open_file, style="Primary.TButton")
        self.open_button.pack(side="left")
        self.back_button = ttk.Button(toolbar, command=self.back_to_archive, state="disabled")
        self.back_button.pack(side="left", padx=(8, 16))
        self.filter_label = ttk.Label(toolbar)
        self.filter_label.pack(side="left", padx=(0, 6))
        self.filter = tk.StringVar(root)
        self.filter_entry = ttk.Entry(toolbar, textvariable=self.filter)
        self.filter_entry.pack(side="left", fill="x", expand=True)
        self.filter_entry.bind("<Return>", self._apply_list_filter)
        self.filter.trace_add("write", self._schedule_filter)

        self.identity = tk.StringVar(root, value="")
        ttk.Label(self.frame, textvariable=self.identity, style="Muted.TLabel", wraplength=1100).grid(
            row=1, column=0, sticky="ew", pady=(8, 10))

        content = ttk.Panedwindow(self.frame, orient="horizontal")
        content.grid(row=2, column=0, sticky="nsew")
        list_frame = ttk.Frame(content, padding=(0, 0, 8, 0))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        self.listing = ttk.Treeview(list_frame, columns=("kind", "size"), show="tree headings", selectmode="browse")
        self.listing.heading("#0", text="")
        self.listing.heading("kind", text="")
        self.listing.heading("size", text="")
        self.listing.column("#0", width=330, minwidth=130, stretch=True)
        self.listing.column("kind", width=90, minwidth=70, stretch=False)
        self.listing.column("size", width=85, minwidth=70, anchor="e", stretch=False)
        vertical = ttk.Scrollbar(list_frame, orient="vertical", command=self.listing.yview)
        horizontal = ttk.Scrollbar(list_frame, orient="horizontal", command=self.listing.xview)
        self.listing.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.listing.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        self.listing.bind("<<TreeviewSelect>>", self._selection_changed)
        content.add(list_frame, weight=1)

        preview_frame = ttk.Frame(content, padding=(8, 0, 0, 0))
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(1, weight=1)
        controls = ttk.Frame(preview_frame)
        controls.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        self.preview_summary = tk.StringVar(root, value="")
        ttk.Label(controls, textvariable=self.preview_summary, style="Section.TLabel").pack(side="left", anchor="w")
        self.mip_label = ttk.Label(controls)
        self.mip_label.pack(side="left", padx=(10, 5))
        self.mip = tk.StringVar(root, value="0")
        self.mip_choice = ttk.Combobox(controls, textvariable=self.mip, state="disabled", width=5)
        self.mip_choice.pack(side="left")
        self.mip_choice.bind("<<ComboboxSelected>>", self._mip_changed)
        self.preview_canvas = tk.Canvas(preview_frame, width=540, height=440, highlightthickness=1,
                                        highlightbackground=self._palette["border"])
        self.preview_canvas.grid(row=1, column=0, sticky="nsew")
        content.add(preview_frame, weight=2)

        self.status = tk.StringVar(root, value="")
        ttk.Label(self.frame, textvariable=self.status, style="Muted.TLabel", wraplength=1100).grid(
            row=3, column=0, sticky="ew", pady=(8, 0))
        self.set_language(self.language)
        self._set_detail(self._t("idle"))

    @property
    def busy(self):
        return self._busy

    def _t(self, key, **values):
        return _TEXT[self.language][key].format(**values)

    def set_language(self, language):
        if language not in _TEXT:
            language = "en"
        self.language = language
        self.open_button.configure(text=self._t("open"))
        self.back_button.configure(text=self._t("back"))
        self.filter_label.configure(text=self._t("filter"))
        self.listing.heading("#0", text=self._t("name"))
        self.listing.heading("kind", text=self._t("kind"))
        self.listing.heading("size", text=self._t("size"))
        self.mip_label.configure(text=self._t("mip"))
        self._refresh_status()

    def apply_theme(self, palette):
        self._palette = dict(palette)
        self.preview_canvas.configure(background=palette["surface"], highlightbackground=palette["border"])
        self._render_preview(self._last_preview)

    def dirty_ok(self):
        return True

    def focus_search(self):
        self.filter_entry.focus_set()
        self.filter_entry.selection_range(0, "end")
        return True

    def open_file(self):
        title = "Open local asset" if self.language == "en" else "Lokales Asset öffnen"
        path = filedialog.askopenfilename(
            parent=self.root,
            title=title,
            filetypes=(("Inspected assets", "*.zip *.g1t *.png *.dds *.wav *.flac *.ogg *.mp3 *.obj *.stl *.ply *.glb"),
                       ("All files", "*")),
        )
        if path:
            self._submit(lambda: _load_local(path))

    def _submit(self, operation):
        if self._busy or self._closed:
            return
        self._generation += 1
        generation = self._generation
        self._busy = True
        self._set_detail(self._t("busy"))
        self.open_button.configure(state="disabled")
        self.back_button.configure(state="disabled")

        def run():
            try:
                result = (True, operation())
            except Exception as error:  # Surface rejected and malformed data as a bounded user message.
                result = (False, str(error)[:500])
            self._messages.put((generation, result))

        threading.Thread(target=run, name="asset-inspection", daemon=True).start()
        self._schedule_poll()

    def _schedule_poll(self):
        if not self._closed and self._poll_id is None:
            self._poll_id = self.root.after(60, self._drain_messages)

    def _drain_messages(self):
        self._poll_id = None
        while True:
            try:
                generation, outcome = self._messages.get_nowait()
            except queue.Empty:
                break
            if self._closed or generation != self._generation:
                continue
            self._busy = False
            self.open_button.configure(state="normal")
            self.back_button.configure(
                state="normal" if self._archive is not None and self._mode != "archive"
                and self._texture_member is not None else "disabled")
            ok, result = outcome
            if not ok:
                self._clear_preview()
                self._set_detail(self._t("error", error=result))
                continue
            self._accept_result(result)
        if self._busy:
            self._schedule_poll()

    def _accept_result(self, result):
        kind = result[0]
        if kind == "preview":
            _, preview_kind, preview = result
            self._last_preview = (preview_kind, preview)
            self._render_preview(self._last_preview)
            return
        member = next((value for value in result if isinstance(value, ZipMember)), None)
        self._clear_preview()
        self._texture_data = None
        self._textures = ()
        self._selected_texture = None
        self._texture_member = member
        self.mip_choice.configure(values=(), state="disabled")
        if kind != "archive" and member is None:
            self._archive = None
            self._archive_path = None
        self.back_button.configure(state="normal" if member is not None else "disabled")
        if kind == "archive":
            _, path, archive = result
            self._archive_path = str(path)
            self._archive = archive
            self._mode = "archive"
            self._set_items(tuple(
                (member.id, member.name, self._t("directory") if member.is_directory else _extension(member.name).upper(),
                 "" if member.is_directory else f"{member.size:,}", member)
                for member in archive.entries
            ))
            self.identity.set(self._t("archive"))
            self._set_detail(self._t("rows", total=len(archive.entries)))
            return
        if kind == "textures":
            _, name, data, textures, member = result
            self._texture_data = data
            self._textures = textures
            self._selected_texture = None
            self._mode = "textures"
            self._texture_member = member
            self.back_button.configure(state="normal" if member is not None else "disabled")
            self._set_items(tuple(
                (f"texture:{texture.index}", f"Texture {texture.index:04d}", texture.format_name,
                 f"{texture.width}×{texture.height}", texture)
                for texture in textures
            ))
            self.identity.set(self._t("texture"))
            self._set_detail(f"{name} · {len(textures):,} textures")
            if textures:
                first_id = f"texture:{textures[0].index}"
                self.listing.selection_set(first_id)
                self.listing.focus(first_id)
                self._start_texture_preview(textures[0], 0)
            else:
                self._set_detail(self._t("select_texture"))
            return
        if kind in {"image", "audio", "model"}:
            _, name, preview = result[:3]
            self._mode = "media"
            self._set_items(())
            self.identity.set(self._t("media"))
            self._set_detail(name)
            self._last_preview = (kind, preview)
            self._render_preview(self._last_preview)
            return
        _, name = result[:2]
        self._mode = "empty"
        self._set_items(())
        self.identity.set(self._t("identity"))
        self._set_detail(f"{name} · {self._t('unsupported')}")

    def _set_items(self, items):
        self._items = items
        self._item_by_id = {item[0]: item[4] for item in items}
        self._apply_list_filter()

    def _schedule_filter(self, *_args):
        if self._filter_id is not None:
            self.root.after_cancel(self._filter_id)
        self._filter_id = self.root.after(120, self._apply_list_filter)

    def _apply_list_filter(self, _event=None):
        if self._filter_id is not None:
            try:
                self.root.after_cancel(self._filter_id)
            except tk.TclError:
                pass
            self._filter_id = None
        query = self.filter.get().casefold().strip()
        matches = [item for item in self._items if not query or query in item[1].casefold()]
        visible = matches[:MAX_LIST_ROWS]
        self.listing.delete(*self.listing.get_children())
        for identity, name, kind, size, _metadata in visible:
            self.listing.insert("", "end", iid=identity, text=name, values=(kind, size))
        if len(matches) > MAX_LIST_ROWS:
            self._set_detail(self._t("showing", shown=len(visible), total=len(matches)))
        elif self._items and self._mode == "archive":
            self._set_detail(self._t("rows", total=len(matches)))
        elif self._items and self._mode == "textures":
            pass

    def _selection_changed(self, _event=None):
        if self._busy or not self.listing.selection():
            return
        identity = self.listing.selection()[0]
        item = self._item_by_id.get(identity)
        if self._mode == "archive" and isinstance(item, ZipMember):
            if item.is_directory:
                self._set_detail(item.name)
            else:
                path = self._archive_path
                self._submit(lambda: _load_zip_member(path, item))
        elif self._mode == "textures" and isinstance(item, TextureRecord):
            self._selected_texture = item
            self._start_texture_preview(item, 0)

    def _start_texture_preview(self, texture, level):
        if self._texture_data is None or self._busy:
            return
        data = self._texture_data

        def decode():
            from koei_editor.research.asset_explorer.media import decode_g1t_texture

            raw = texture.read_mip(data, level)
            width, height = max(1, texture.width >> level), max(1, texture.height >> level)
            return "preview", "image", decode_g1t_texture(raw, width, height, texture.format_name)

        self.mip_choice.configure(values=tuple(str(index) for index in range(texture.mip_count)),
                                  state="readonly" if texture.mip_count > 1 else "disabled")
        self.mip.set(str(level))
        self.preview_summary.set(self._t("texture_line", version=texture.version, fmt=texture.format_name,
                                         width=texture.width, height=texture.height, mips=texture.mip_count))
        self._submit(decode)

    def _mip_changed(self, _event=None):
        if self._selected_texture is None:
            return
        try:
            level = int(self.mip.get())
        except ValueError:
            return
        if 0 <= level < self._selected_texture.mip_count:
            self._start_texture_preview(self._selected_texture, level)

    def back_to_archive(self):
        if self._mode == "archive" or self._archive is None or self._archive_path is None:
            return
        self._accept_result(("archive", Path(self._archive_path), self._archive))

    def _clear_preview(self):
        self._last_preview = None
        self._image_photo = None
        self.preview_summary.set("")
        self.preview_canvas.delete("all")

    def _set_detail(self, value):
        self._status_detail = value
        self._refresh_status()

    def _refresh_status(self):
        if not hasattr(self, "status"):
            return
        self.status.set(self._status_detail)

    def _render_preview(self, value):
        self.preview_canvas.delete("all")
        self._image_photo = None
        if not value:
            self.preview_summary.set("")
            return
        kind, preview = value
        if kind == "image":
            max_width = max(64, min(540, self.preview_canvas.winfo_width() - 16))
            max_height = max(64, min(410, self.preview_canvas.winfo_height() - 24))
            stride = max(1, math.ceil(max(preview.width / max_width, preview.height / max_height)))
            width = math.ceil(preview.width / stride)
            height = math.ceil(preview.height / stride)
            background = self._palette["surface"]
            bg = tuple(int(background[index:index + 2], 16) for index in (1, 3, 5))
            rgb = bytearray(width * height * 3)
            source = preview.rgba_bytes
            output = 0
            for y in range(0, preview.height, stride):
                row = y * preview.width * 4
                for x in range(0, preview.width, stride):
                    offset = row + x * 4
                    alpha = source[offset + 3]
                    inverse = 255 - alpha
                    rgb[output] = (source[offset] * alpha + bg[0] * inverse) // 255
                    rgb[output + 1] = (source[offset + 1] * alpha + bg[1] * inverse) // 255
                    rgb[output + 2] = (source[offset + 2] * alpha + bg[2] * inverse) // 255
                    output += 3
            ppm = f"P6\n{width} {height}\n255\n".encode("ascii") + bytes(rgb)
            self._image_photo = tk.PhotoImage(master=self.root, data=b64encode(ppm), format="PPM")
            self.preview_canvas.create_image(self.preview_canvas.winfo_width() // 2,
                                             self.preview_canvas.winfo_height() // 2,
                                             image=self._image_photo, anchor="center")
            self.preview_summary.set(self._t("image", fmt=preview.format, width=preview.width,
                                             height=preview.height, mode=preview.mode))
        elif kind == "audio":
            self.preview_summary.set(self._t("audio", fmt=preview.format, channels=preview.channels,
                                             rate=preview.sample_rate,
                                             duration="unknown" if preview.duration_seconds is None
                                             else f"{preview.duration_seconds:.2f} s"))
            self._draw_waveform(preview)
        elif kind == "model":
            self.preview_summary.set(self._t("mesh", fmt=preview.format, vertices=preview.vertex_count,
                                             faces=preview.face_count))
            self._draw_mesh(preview)

    def _draw_waveform(self, preview):
        canvas = self.preview_canvas
        width, height = 540, 440
        values = preview.waveform
        if not values:
            canvas.create_text(width / 2, height / 2, text="No decoded waveform", fill=self._palette["muted"])
        else:
            center = height // 2
            usable_width = width - 36
            slot = usable_width / len(values)
            canvas.create_line(16, center, width - 16, center, fill=self._palette["border"])
            for index, peak in enumerate(values):
                x = 18 + (index + 0.5) * slot
                y = max(1.0, peak * (height * 0.44))
                canvas.create_line(x, center - y, x, center + y, fill=self._palette["accent"], width=max(1, min(3, int(slot))))
        duration = f"{preview.preview_duration_seconds:.2f} s"
        truncated = self._t("truncated") if preview.truncated else ""
        canvas.create_text(16, height - 14, anchor="w", text=self._t(
            "audio_preview", duration=duration, rate=preview.preview_sample_rate, truncated=truncated),
            fill=self._palette["muted"])

    def _draw_mesh(self, mesh):
        canvas = self.preview_canvas
        if not mesh.vertices or not mesh.faces:
            canvas.create_text(270, 220, text="Empty mesh", fill=self._palette["muted"])
            return
        min_values, max_values = mesh.bounds
        center = tuple((minimum + maximum) / 2 for minimum, maximum in zip(min_values, max_values))
        projected = []
        for x, y, z in mesh.vertices:
            x, y, z = x - center[0], y - center[1], z - center[2]
            projected.append(((x - y) * 0.70710678, (x + y) * 0.40824829 - z * 0.81649658))
        left = min(point[0] for point in projected)
        right = max(point[0] for point in projected)
        top = min(point[1] for point in projected)
        bottom = max(point[1] for point in projected)
        span = max(right - left, bottom - top, 1e-9)
        scale = min(500 / span, 390 / span)
        points = [(270 + x * scale, 220 - y * scale) for x, y in projected]
        stride = max(1, (len(mesh.faces) + 3_999) // 4_000)
        color = self._palette["accent"]
        for face in mesh.faces[::stride]:
            if len(face) < 3:
                continue
            indices = face[:3]
            if any(index < 0 or index >= len(points) for index in indices):
                continue
            a, b, c = (points[index] for index in indices)
            canvas.create_line(a[0], a[1], b[0], b[1], c[0], c[1], a[0], a[1], fill=color, width=1)
        min_text = ", ".join(f"{value:.3g}" for value in min_values)
        max_text = ", ".join(f"{value:.3g}" for value in max_values)
        canvas.create_text(14, 14, anchor="nw", text=self._t("bounds", bounds=f"[{min_text}] – [{max_text}]"),
                           fill=self._palette["muted"])

    def close(self):
        self._closed = True
        self._generation += 1
        if self._poll_id is not None:
            try:
                self.root.after_cancel(self._poll_id)
            except tk.TclError:
                pass
            self._poll_id = None
        if self._filter_id is not None:
            try:
                self.root.after_cancel(self._filter_id)
            except tk.TclError:
                pass
            self._filter_id = None
