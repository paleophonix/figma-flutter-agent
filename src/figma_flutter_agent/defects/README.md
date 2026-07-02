# defects

## Purpose

Load and validate the machine-checkable defect corpus under `corpus/`.

## Usage Example

```python
from figma_flutter_agent.defects import load_corpus
from figma_flutter_agent.defects.validation import validate_corpus

corpus = load_corpus()
errors = validate_corpus(corpus)
```

## LLM Context

Diagnose skills map symptoms to `family_id` from `corpus/families.yaml`. Cases reference families and must pass `figma-flutter defects validate`.
