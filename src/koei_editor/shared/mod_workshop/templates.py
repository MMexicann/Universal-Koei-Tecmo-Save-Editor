"""Generic starter layouts for user-authored replacement mods."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ProjectTemplate:
    template_id: str
    name: str
    description: str
    asset_guidance: str
    asset_subfolders: tuple[str, ...] = ()


PROJECT_TEMPLATES = (
    ProjectTemplate(
        template_id="blank",
        name="Blank replacement mod",
        description="A clean project for any user-authored replacement files.",
        asset_guidance="Add only files you created or are licensed to redistribute.",
    ),
    ProjectTemplate(
        template_id="texture-replacement",
        name="Texture replacement",
        description="A starter layout for a new texture or material replacement.",
        asset_guidance=(
            "Add your own replacement image files. Enter destination paths from "
            "public modding documentation; the workshop does not extract game files."
        ),
        asset_subfolders=("textures",),
    ),
    ProjectTemplate(
        template_id="audio-replacement",
        name="Audio replacement",
        description="A starter layout for a new audio replacement.",
        asset_guidance=(
            "Add your own replacement audio files. Enter destination paths from "
            "public modding documentation; the workshop does not extract game files."
        ),
        asset_subfolders=("audio",),
    ),
)

TEMPLATE_BY_ID = {template.template_id: template for template in PROJECT_TEMPLATES}


def get_template(template_id: str) -> ProjectTemplate:
    """Return a template by stable ID or raise ``ValueError``."""
    try:
        return TEMPLATE_BY_ID[template_id]
    except KeyError as exc:
        raise ValueError(f"Unknown mod project template: {template_id}") from exc


def list_templates() -> tuple[ProjectTemplate, ...]:
    """Return the available templates in display order."""
    return PROJECT_TEMPLATES
