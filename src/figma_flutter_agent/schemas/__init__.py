"""Shared schema models for parser, LLM, and generator stages."""

from figma_flutter_agent.schemas.generation import (
    AssetManifest,
    AssetManifestEntry,
    ExtractedWidget,
    FlutterGenerationResponse,
    FlutterRepairIrPatch,
    FlutterRepairPatch,
    FlutterRepairPatchResponse,
    FontFaceRequirement,
    FontManifest,
    FontPubspecAsset,
    FontPubspecFamily,
    RepairCpiSupervisorResponse,
    merge_asset_manifests,
)
from figma_flutter_agent.schemas.geometry import (
    Affine2,
    Alignment,
    AxisPins,
    CascadeContext,
    FlexSolution,
    GeomRect,
    GeometryFrame,
    HeightFit,
    LayerClass,
    LayoutBackend,
    LayoutSlotIr,
    Padding,
    Sizing,
    StackPlacement,
    TextMetricsFrame,
    WrapKind,
)
from figma_flutter_agent.schemas.ir import (
    AdaptiveRule,
    AdaptiveRuleWhen,
    FlexWrapIr,
    ScreenIr,
    WidgetIrArgValue,
    WidgetIrKind,
    WidgetIrNode,
    WidgetIrOverrides,
    WidgetIrRef,
    WidgetIrState,
)
from figma_flutter_agent.schemas.style import (
    ComponentVariant,
    CornerRadii,
    GradientFill,
    GradientStop,
    NodeStyle,
    ShadowEffect,
    TextSpanPart,
)
from figma_flutter_agent.schemas.tokens import DesignTokens, TypographyStyle, TypographyToken
from figma_flutter_agent.schemas.tree import CleanDesignTreeNode
from figma_flutter_agent.schemas.types import (
    HorizontalConstraint,
    NodeType,
    ScrollAxis,
    SizingMode,
    VerticalConstraint,
)
