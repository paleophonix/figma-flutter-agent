# Purpose
Feedback issue pipeline: screen/asset bundles, LLM ticket text, ARQ `feedback_issue_job`.

# Usage Example
```python
from control_panel.feedback.llm_review import generate_feedback_issue_review
from control_panel.feedback.bundle import build_feedback_bundle_zip
```

# LLM Context
Invoked from `workers/tasks.feedback_issue_job` after user comment; reads `.debug/screen/<project>/<feature>/` triage files for LLM context.
