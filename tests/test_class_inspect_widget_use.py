"""Widget-use detection must not treat Flutter SDK types as planned widgets."""

from figma_flutter_agent.generator.planned.reconcile.class_inspect import (
    _collect_widget_use_class_names,
)


def test_collect_widget_use_ignores_flutter_sdk_ctors() -> None:
    source = """
    return Row(
      children: [
        const Text('hi'),
        ProductCardWidget(key: key),
        Container(child: SizedBox.shrink()),
      ],
    );
    """
    names = _collect_widget_use_class_names(source)
    assert names == {"ProductCardWidget"}
