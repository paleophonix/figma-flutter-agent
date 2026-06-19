# OpenCode repair prompts

## Purpose

Raw ACDP layer bodies for the 7-step OpenCode repair pipeline. Tags and ordering are applied by `dev/opencode/prompt.py` via `_acdp_layer` / `_compose_acdp_prompt` (see `docs/projects/repair/opencode-debug-state.md` §8.2).

## Layout

```text
.opencode/prompts/
  repair-master-screen.md    # L1 body — SCREEN board
  repair-master-forensic.md  # L1 body — FORENSIC board
  repair-invariants.md       # L3 body — shared (planned)
  README.md

.opencode/skills/<step>/     # L2–L6 bodies per step (planned)
```

**Source file rule:** plain prose only — no `<Lx:...>` tags, no YAML front matter, no markdown headings in prompt bodies. Metadata lives in README and code.

## Assembly

```text
prompt(step N) =
  _acdp_layer("L1:PURPOSE", read(master[board]))
+ _acdp_layer("L3:PRINCIPLES", read(repair-invariants) + step_l3)
+ _acdp_layer("L2:ROLE", read(skill.l2))
+ …
+ runtime: reasoning_chain, run_context, schema, output_path
```

## Usage example

```python
from pathlib import Path
from figma_flutter_agent.llm.prompts.compose import _acdp_layer

repo = Path(__file__).resolve().parents[2]
l1_body = (repo / ".opencode/prompts/repair-master-screen.md").read_text(encoding="utf-8").strip()
l1_block = _acdp_layer("L1:PURPOSE", l1_body)
```

## LLM context

Pass assembled tagged blocks to the model. Never send raw repo paths as the whole system prompt without layer wrapping.
