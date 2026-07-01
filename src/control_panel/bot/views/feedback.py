"""Persistent Discord views for preview and quality feedback."""

from __future__ import annotations

import disnake

from control_panel.db import Quality


class FeedbackButton(disnake.ui.Button):
    """Quality rating button with a stable custom_id."""

    def __init__(
        self, *, job_id: str, quality: Quality, label: str, style: disnake.ButtonStyle
    ) -> None:
        self.job_id = job_id
        self.quality = quality
        super().__init__(
            label=label,
            style=style,
            custom_id=f"gen_fb:{job_id}:{quality.value}",
        )

    async def callback(self, inter: disnake.MessageInteraction) -> None:
        from control_panel.bot.handlers.feedback import handle_feedback

        await handle_feedback(inter=inter, job_id=self.job_id, quality=self.quality)


class PreviewFeedbackView(disnake.ui.View):
    """Quality feedback buttons for one job (preview links live in message body)."""

    def __init__(self, *, job_id: str) -> None:
        super().__init__(timeout=None)
        self.add_item(
            FeedbackButton(
                job_id=job_id,
                quality=Quality.TOTAL_MESS,
                label="Полное месиво",
                style=disnake.ButtonStyle.danger,
            )
        )
        self.add_item(
            FeedbackButton(
                job_id=job_id,
                quality=Quality.MAJOR_WRONG,
                label="Значительная часть неверна",
                style=disnake.ButtonStyle.danger,
            )
        )
        self.add_item(
            FeedbackButton(
                job_id=job_id,
                quality=Quality.MINOR_WRONG,
                label="Небольшая мелочь",
                style=disnake.ButtonStyle.secondary,
            )
        )
        self.add_item(
            FeedbackButton(
                job_id=job_id,
                quality=Quality.GOOD,
                label="Норм качество",
                style=disnake.ButtonStyle.success,
            )
        )
