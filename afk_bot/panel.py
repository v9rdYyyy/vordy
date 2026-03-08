from __future__ import annotations

from datetime import timezone

import discord

from .models import AFKEntry

UTC = timezone.utc


class EmbedFactory:
    TITLE = "Atletico Famq"
    DESCRIPTION = "Этот бот создан для мониторинга АФК нашей семьи!"

    @classmethod
    def build_panel(cls, entries: list[AFKEntry]) -> discord.Embed:
        embed = discord.Embed(
            title=cls.TITLE,
            description=cls.DESCRIPTION,
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="Список АФК",
            value=cls._format_entries(entries),
            inline=False,
        )
        embed.set_footer(text="Используйте кнопки ниже для управления АФК статусом")
        return embed

    @staticmethod
    def _format_entries(entries: list[AFKEntry]) -> str:
        if not entries:
            return "Сейчас никто не стоит в АФК."

        blocks: list[str] = []
        for index, entry in enumerate(entries, start=1):
            started_ts = int(entry.started_at.astimezone(UTC).timestamp())
            reason = discord.utils.escape_markdown(entry.reason)
            eta = discord.utils.escape_markdown(entry.eta)
            display_name = discord.utils.escape_markdown(entry.display_name)
            blocks.append(
                "\n".join(
                    [
                        f"**{index}. {display_name}** (<@{entry.user_id}>)",
                        f"> Причина: {reason}",
                        f"> Примерный выход: {eta}",
                        f"> Встал в АФК: <t:{started_ts}:f>",
                        f"> Сидит в АФК: <t:{started_ts}:R>",
                    ]
                )
            )

        text = "\n\n".join(blocks)
        if len(text) > 4000:
            return (
                text[:3900]
                + "\n\n...\nСписок обрезан, потому что Discord ограничивает размер embed-поля."
            )
        return text
