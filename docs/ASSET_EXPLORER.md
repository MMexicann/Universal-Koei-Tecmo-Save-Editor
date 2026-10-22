# Game Asset Explorer

The **Game Asset Explorer** is a read-only workspace under **Tools → Editing &
Research**. It inspects local files in memory. It does not modify input files,
extract archive members to disk, execute game programs or third-party command
line tools, contact a network service, or store file paths in preferences.

Format recognition means only that the bytes passed the listed container or
decoder checks. It does not establish a Koei Tecmo title, platform, game build,
or edition. In particular, ZIP is a general-purpose container, not a verified
Koei Tecmo archive signature.

## Validated subset

| Input | Current inspection | Scope and limits |
|---|---|---|
| ZIP / ZIP64 | List members; read one selected member in memory and verify its CRC | Stored and deflate compression only. The reader rejects unsafe/conflicting names, encrypted or special members, excessive counts/sizes/ratios, unsupported compression, and stale member records. No extraction or game identity claim. |
| G1T | List texture records and preview a selected mip | Header versions `0600`, `0601`, and `0602`; raw BGRA8 (`0x01`)/RGBA8 (`0x02`), DXT1 (`0x06`, `0x59`), and DXT5 (`0x08`, `0x5B`). The parser accepts at most 512 MiB; the workspace limits direct and ZIP-contained G1T inputs to 64 MiB. Other G1T revisions and formats are rejected. |
| Images | PNG and DDS preview | The bounded in-process decoder accepts non-interlaced 8-bit RGB/RGBA/palette PNG and DXT1/DXT5 DDS, capped at 32 MiB input and 4,194,304 pixels. Other PNG modes, DDS formats, and multi-frame images are rejected. |
| Audio | WAV, FLAC, Vorbis in Ogg, and MP3 metadata plus a short waveform | Input is capped at 32 MiB and a known source duration at 24 hours. The waveform decodes at most five seconds at 22,050 Hz mono; the workspace does not play or export audio. Ogg Opus is not claimed. |
| Models | OBJ, STL, PLY, and GLB geometry summary and wireframe | Input is capped at 32 MiB, with limits of 50,000 vertices and 100,000 triangles. Text formats cap lines at 256 Ki characters and one million records. GLB buffer-view and accessor materialization is capped at 128 MiB in total. OBJ is reduced to position and face records; materials, normals, UVs, and sidecars are ignored. External GLB buffers/images are not opened. GLTF animation, materials, and rigged-model rendering are outside this preview. |

ZIP member previews accept only the same image, audio, model, and G1T subsets.
The workspace has no generic extraction button or write path. Member reads are
bounded and performed only after the user selects an entry.

## Source and licensing

The G1T table/entry facts were checked against
[three-houses-research-team/G1Tool, `G1T.cs`, commit
`68c5a42b170d49ea03e3d0b138e7fa8c4a5bdb91`](https://github.com/three-houses-research-team/G1Tool/tree/68c5a42b170d49ea03e3d0b138e7fa8c4a5bdb91).
Only the bounded parser was independently adapted from that MIT source; the
Windows Forms application, its graphics dependencies, and game files are not
bundled. The complete MIT notice is in
[`G1Tool-MIT.txt`](../licenses/G1Tool-MIT.txt).

Preview dependencies are permissively licensed: miniaudio 1.71 (MIT, including
its listed miniaudio and stb_vorbis notices) and trimesh 5.1.1 (MIT). Their
runtime dependencies are NumPy 2.5.4 (BSD-3-Clause and component notices), cffi
2.1.1 (MIT-0), and pycparser 3.12 (BSD-3-Clause). PNG and DXT preview code is
independently implemented against the public format specifications; no Pillow
code is included. The Windows build pins these versions, while source installs
on Python 3.10+ resolve versions compatible with that interpreter. Retained
notices are listed in
[`licenses/README.md`](../licenses/README.md) and included in Windows runtime
license resources. These packages are used in process; no arbitrary executable,
FFmpeg fallback, external viewer, or network resolver is invoked.

## Exclusions and evidence

No title-specific Koei Tecmo archive signature is currently exposed. Research
found the MIT TitanUnpacker/AoT1 candidate, but its input path is selected by an
adjacent sidecar and the upstream reader does not validate an archive magic or
bound every record. There is no genuine fixture to establish that signature, so
the candidate is excluded. This workspace does not claim support for LINKDATA,
PAK, G1M, G1T revisions outside the subset above, or any other proprietary game
container/model format. No game assets, extracted files, screenshots, or native
game archives are included as fixtures.

Validation evidence is generated from small synthetic byte fixtures only:

| Area | AI-readable checks |
|---|---|
| Standard ZIP listing and member reads | `tests/test_asset_explorer_zip.py` — synthetic stored/deflated and ZIP64 cases, malformed-directory/name/limit checks, and CRC-checked reads. |
| G1T metadata and bounds | `tests/test_asset_explorer_g1t.py` — synthetic version/format records, mip spans, unknown formats, and malformed/truncated inputs. |
| Image, audio, and model previews | `tests/test_asset_explorer_media.py` — synthetic PNG/DDS, WAV/FLAC/Vorbis/MP3, OBJ/STL/PLY/GLB inputs and malformed or over-limit cases. |
| Workspace file/member dispatch | `tests/test_asset_explorer_gui.py` — direct and ZIP-contained synthetic PNGs reach the in-memory preview path without extracting a member. |
| Application routing | `tests/test_application_shell.py` — stable menu/palette route and retained workspace integration. |

These tests establish parser behavior for the listed subsets, not compatibility
with a particular Koei Tecmo game, release build, or native game asset. No real
game file was used to qualify this feature.
