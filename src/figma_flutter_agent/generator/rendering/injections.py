"""State-management injection helpers for generated screens."""

from __future__ import annotations

import re

BUILD_RETURN_RE = re.compile(
    r"(Widget build\(BuildContext context\) \{.*?)(    return .+?;)(\n  \})",
    re.DOTALL,
)


def showcase_provider_name(screen_class: str) -> str:
    """Derive a lowerCamelCase Riverpod provider id from a screen class name."""
    from figma_flutter_agent.generator.layout.common import to_camel_case

    base = screen_class
    if base.endswith("Screen"):
        base = base[: -len("Screen")]
    return f"{to_camel_case(base)}ReadyProvider"


def inject_riverpod_consumer(screen_code: str, provider_name: str) -> str:
    """Wrap the screen build return value in a Riverpod Consumer."""
    match = BUILD_RETURN_RE.search(screen_code)
    if match is None:
        return screen_code
    prefix, return_stmt, suffix = match.groups()
    wrapped_return = (
        "    return Consumer(\n"
        "      builder: (context, ref, _) {\n"
        f"        ref.watch({provider_name});\n"
        f"        {return_stmt.removeprefix('    ')}\n"
        "      },\n"
        "    );"
    )
    return screen_code.replace(prefix + return_stmt + suffix, prefix + wrapped_return + suffix, 1)


def inject_provider_consumer(screen_code: str, screen_class: str) -> str:
    """Wrap the screen build return value with Provider watch."""
    match = BUILD_RETURN_RE.search(screen_code)
    if match is None:
        return screen_code
    prefix, return_stmt, suffix = match.groups()
    wrapped_return = (
        "    return Consumer<"
        f"{screen_class}State>(\n"
        "      builder: (context, state, _) {\n"
        "        if (!state.ready) {\n"
        "          return const SizedBox.shrink();\n"
        "        }\n"
        f"        {return_stmt.removeprefix('    ')}\n"
        "      },\n"
        "    );"
    )
    return screen_code.replace(prefix + return_stmt + suffix, prefix + wrapped_return + suffix, 1)


def inject_bloc_builder(screen_code: str, screen_class: str) -> str:
    """Wrap the screen build return value in a BlocBuilder when bloc is enabled."""
    cubit = f"{screen_class}Cubit"
    state = f"{screen_class}State"
    match = BUILD_RETURN_RE.search(screen_code)
    if match is None:
        return screen_code
    prefix, return_stmt, suffix = match.groups()
    wrapped_return = (
        "    return BlocBuilder<"
        f"{cubit}, {state}>(\n"
        "      builder: (context, state) {\n"
        f"        {return_stmt.removeprefix('    ')}\n"
        "      },\n"
        "    );"
    )
    return screen_code.replace(prefix + return_stmt + suffix, prefix + wrapped_return + suffix, 1)
