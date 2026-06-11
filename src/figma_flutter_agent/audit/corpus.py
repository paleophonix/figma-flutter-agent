"""Structural fixture corpus for systemic pipeline audits."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from figma_flutter_agent.fixtures.screens_manifest import fixtures_root


@dataclass(frozen=True, slots=True)
class AuditCorpusEntry:
    """One auditable layout fixture with a structural pattern label."""

    pattern_class: str
    layout_path: Path
    feature_name: str
    description: str
    manifest_id: str | None = None


def _layout(name: str) -> Path:
    return fixtures_root() / "layouts" / name


AUDIT_CORPUS: tuple[AuditCorpusEntry, ...] = (
    AuditCorpusEntry(
        pattern_class="auth_forms",
        layout_path=_layout("sign_up_and_sign_in_layout.json"),
        feature_name="sign_up_and_sign_in",
        description="Social row and credential fields",
        manifest_id="sign_up_and_sign_in",
    ),
    AuditCorpusEntry(
        pattern_class="lists_cards",
        layout_path=_layout("reminders_layout.json"),
        feature_name="reminders",
        description="Reminder list with cards and FAB",
        manifest_id="reminders",
    ),
    AuditCorpusEntry(
        pattern_class="media_chrome",
        layout_path=_layout("music_v2_layout.json"),
        feature_name="music_v2",
        description="Media player chrome",
        manifest_id="music_v2",
    ),
    AuditCorpusEntry(
        pattern_class="media_chrome_dirty_names",
        layout_path=_layout("music_v2_ru_dirty_layout.json"),
        feature_name="music_v2",
        description="Same geometry with Cyrillic and garbage layer names",
        manifest_id="music_v2_ru_dirty",
    ),
    AuditCorpusEntry(
        pattern_class="bounded_overflow",
        layout_path=_layout("bounded_order_card.json"),
        feature_name="bounded_order_card",
        description="T2b bounded slot conservation",
        manifest_id="bounded_order_card",
    ),
    AuditCorpusEntry(
        pattern_class="consent_checkbox",
        layout_path=_layout("consent_checkbox_row.json"),
        feature_name="consent_checkbox",
        description="Checkbox host beside multiline label in ROW",
        manifest_id="consent_checkbox",
    ),
    AuditCorpusEntry(
        pattern_class="flex_summary_row",
        layout_path=_layout("flex_summary_row.json"),
        feature_name="flex_summary_row",
        description="spaceBetween label/value without absolute pins",
        manifest_id="flex_summary_row",
    ),
    AuditCorpusEntry(
        pattern_class="prefilled_input",
        layout_path=_layout("prefilled_input_field.json"),
        feature_name="prefilled_input",
        description="Flex INPUT with prefilled value typography",
        manifest_id="prefilled_input",
    ),
    AuditCorpusEntry(
        pattern_class="a11y_form",
        layout_path=_layout("elastic_form_a11y.json"),
        feature_name="elastic_form_a11y",
        description="Orphan raw Figma email INPUT frame",
    ),
    AuditCorpusEntry(
        pattern_class="deep_nesting",
        layout_path=_layout("deep_nesting_8x.json"),
        feature_name="deep_nesting",
        description="Eight-level nesting stress",
    ),
    AuditCorpusEntry(
        pattern_class="variant_topology",
        layout_path=_layout("variant_topology.json"),
        feature_name="variant_topology",
        description="Component variant topology",
    ),
)
