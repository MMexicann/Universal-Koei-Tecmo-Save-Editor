"""Collect only resources used by the toolkit's bounded mesh previews."""
from PyInstaller.utils.hooks import collect_data_files

# Override the upstream hook, which also ships optional browser viewers,
# external-tool script templates and unrelated format schemas.
datas = collect_data_files('trimesh', includes=[
    'resources/creation.json',
    'resources/units_to_inches.json',
    'resources/color_map.json.gzip',
    'resources/templates/ply.json',
])
