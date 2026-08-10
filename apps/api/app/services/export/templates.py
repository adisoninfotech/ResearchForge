"""Compatible starting templates — not officially certified publisher formats."""

from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import ExportTemplateId
from app.models.export import TEMPLATE_COMPATIBILITY_WARNING


@dataclass(frozen=True)
class ExportTemplate:
    id: ExportTemplateId
    name: str
    version: str
    description: str
    column_layout: str
    latex_documentclass: str
    latex_options: str
    css_class: str
    page_width_in: float
    page_height_in: float
    warning: str = TEMPLATE_COMPATIBILITY_WARNING


TEMPLATES: dict[str, ExportTemplate] = {
    ExportTemplateId.GENERIC_ACADEMIC.value: ExportTemplate(
        id=ExportTemplateId.GENERIC_ACADEMIC,
        name="Generic academic manuscript",
        version="1.0.0",
        description="Single-column academic manuscript compatible starting template.",
        column_layout="one",
        latex_documentclass="article",
        latex_options="11pt",
        css_class="rf-tpl-generic",
        page_width_in=8.5,
        page_height_in=11.0,
    ),
    ExportTemplateId.IEEE_TWO_COLUMN.value: ExportTemplate(
        id=ExportTemplateId.IEEE_TWO_COLUMN,
        name="IEEE-style two-column manuscript",
        version="1.0.0",
        description=(
            "Two-column layout inspired by common IEEE conference/journal styles. "
            "Compatible starting template only."
        ),
        column_layout="two",
        latex_documentclass="IEEEtran",
        latex_options="conference",
        css_class="rf-tpl-ieee",
        page_width_in=8.5,
        page_height_in=11.0,
    ),
    ExportTemplateId.SPRINGER_LNCS.value: ExportTemplate(
        id=ExportTemplateId.SPRINGER_LNCS,
        name="Springer LNCS-style manuscript",
        version="1.0.0",
        description=(
            "Single-column layout inspired by Springer Lecture Notes in Computer Science. "
            "Compatible starting template only."
        ),
        column_layout="one",
        latex_documentclass="llncs",
        latex_options="",
        css_class="rf-tpl-lncs",
        page_width_in=6.1,
        page_height_in=9.25,
    ),
    ExportTemplateId.ACM.value: ExportTemplate(
        id=ExportTemplateId.ACM,
        name="ACM-style manuscript",
        version="1.0.0",
        description=(
            "Two-column layout inspired by ACM conference formats. "
            "Compatible starting template only."
        ),
        column_layout="two",
        latex_documentclass="acmart",
        latex_options="sigconf",
        css_class="rf-tpl-acm",
        page_width_in=8.5,
        page_height_in=11.0,
    ),
}


def get_template(template_id: str) -> ExportTemplate:
    key = template_id if template_id in TEMPLATES else ExportTemplateId.GENERIC_ACADEMIC.value
    return TEMPLATES[key]


def list_templates() -> list[dict[str, str]]:
    return [
        {
            "id": t.id.value,
            "name": t.name,
            "version": t.version,
            "description": t.description,
            "column_layout": t.column_layout,
            "warning": t.warning,
        }
        for t in TEMPLATES.values()
    ]
