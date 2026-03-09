from __future__ import annotations

import discord


class EmbedFactory:
    FIELD_LIMIT = 1024
    TOTAL_LIMIT = 6000
    MAX_FIELDS = 25

    @staticmethod
    def _entry_line(index: int, entry) -> str:
        user_id = getattr(entry, "user_id", None)
        name = discord.utils.escape_markdown(
            getattr(entry, "display_name", "Неизвестно")
        )
        reason = discord.utils.escape_markdown(
            getattr(entry, "reason", "Не указана")
        )
        eta = discord.utils.escape_markdown(
            getattr(entry, "eta", "Не указано")
        )

        user_ref = f"<@{user_id}>" if user_id else name

        return (
            f"**{index}.** {user_ref}\n"
            f"Причина: {reason}\n"
            f"Когда вернётся: {eta}"
        )

    @classmethod
    def build_panel(cls, entries) -> discord.Embed:
        embed = discord.Embed(
            title="AFK-панель",
            description="Нажми кнопку ниже, чтобы встать в АФК или выйти из него.",
            color=discord.Color.blurple(),
        )

        if not entries:
            embed.add_field(
                name="Сейчас в АФК",
                value="Никто не стоит в АФК.",
                inline=False,
            )
            return embed

        chunks: list[str] = []
        current = ""
        shown = 0

        for index, entry in enumerate(entries, start=1):
            line = cls._entry_line(index, entry)
            candidate = line if not current else f"{current}\n\n{line}"

            if len(candidate) <= cls.FIELD_LIMIT:
                current = candidate
                shown = index
                continue

            if current:
                chunks.append(current)
                if len(chunks) >= cls.MAX_FIELDS:
                    break
                current = line
                shown = index
            else:
                chunks.append(line[: cls.FIELD_LIMIT - 1] + "…")
                shown = index
                if len(chunks) >= cls.MAX_FIELDS:
                    break
                current = ""

        if current and len(chunks) < cls.MAX_FIELDS:
            chunks.append(current)

        total_chars = len(embed.title or "") + len(embed.description or "")
        used_chunks: list[str] = []

        for chunk in chunks:
            extra = len("Сейчас в АФК") + len(chunk)
            if total_chars + extra > cls.TOTAL_LIMIT:
                break
            used_chunks.append(chunk)
            total_chars += extra

        hidden_count = max(0, len(entries) - shown)
        if hidden_count and used_chunks:
            suffix = f"\n\n*И ещё {hidden_count} чел.*"
            last = used_chunks[-1]
            if len(last) + len(suffix) <= cls.FIELD_LIMIT:
                used_chunks[-1] = last + suffix
            else:
                overflow_text = f"И ещё {hidden_count} чел."
                if (
                    len(used_chunks) < cls.MAX_FIELDS
                    and total_chars + len("Сейчас в АФК (ещё)") + len(overflow_text) <= cls.TOTAL_LIMIT
                ):
                    used_chunks.append(overflow_text)

        for idx, chunk in enumerate(used_chunks, start=1):
            field_name = "Сейчас в АФК" if idx == 1 else f"Сейчас в АФК (часть {idx})"
            embed.add_field(name=field_name, value=chunk, inline=False)

        embed.set_footer(text=f"Всего в АФК: {len(entries)}")
        return embed
