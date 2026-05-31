from figma_flutter_agent.fixtures.golden_planned import build_fixture_planned_files
from figma_flutter_agent.generator.planned_dart import reconcile_planned_dart_files

layout = reconcile_planned_dart_files(build_fixture_planned_files("sign_up_and_sign_in"))[
    "lib/generated/sign_up_and_sign_in_layout.dart"
]
for key in ("figma-1_3972", "figma-1_3973", "figma-1_3970"):
    i = layout.find(key)
    print("===", key, "idx", i)
    if i >= 0:
        print(layout[i : i + 550])
        print()
