from pathlib import Path

from figma_flutter_agent.generator.dart_syntax_repairs import fix_garbage_closers_after_link_rich

p = Path(r"E:/@dev/demo_app/lib/features/sign_up_and_sign_in/sign_up_and_sign_in_screen.dart")
s = p.read_text(encoding="utf-8")
fixed = fix_garbage_closers_after_link_rich(s)
print("changed", fixed != s)
if fixed != s:
    p.write_text(fixed, encoding="utf-8")
    print("wrote demo screen")
