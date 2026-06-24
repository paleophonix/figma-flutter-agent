"""GitLab Issue-first workflow for the control panel."""

from control_panel.gitlab_workflow.orchestrate import handle_gitlab_event

__all__ = ["handle_gitlab_event"]
