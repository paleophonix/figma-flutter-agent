"""Persistent Discord view to close a feedback issue."""

from __future__ import annotations

import disnake


class CloseIssueButton(disnake.ui.Button):
    """Close linked tracker issue when user autoclose is enabled."""

    def __init__(self, *, job_id: str) -> None:
        self.job_id = job_id
        super().__init__(
            label="Закрыть тикет",
            style=disnake.ButtonStyle.secondary,
            custom_id=f"close_issue:{job_id}",
        )

    async def callback(self, inter: disnake.MessageInteraction) -> None:
        from control_panel.bot.handlers.close_issue import handle_close_issue

        await handle_close_issue(inter=inter, job_id=self.job_id)


class CloseIssueView(disnake.ui.View):
    """Optional close button under issue notifications."""

    def __init__(self, *, job_id: str) -> None:
        super().__init__(timeout=None)
        self.add_item(CloseIssueButton(job_id=job_id))
