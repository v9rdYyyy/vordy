from __future__ import annotations

from datetime import datetime, timezone

import discord


class EmbedFactory:
    FIELD_LIMIT = 1024
    TOTAL_LIMIT = 6000
    MAX_FIELDS = 25

    @staticmethod
    def _escape(value: object, default: str) -> str:
        text = getattr(value, "strip", lambda: str(value))() if value is not None else default
        if not text:
            text = default
        return discord.utils.escape_markdown(str(text))

    @staticmethod
    def _parse_datetime(value: object) -> datetime | None:
        if value is None:
            return None

        if isinstance(value, datetime):
            dt = value
        else:
            text = str(value).strip()
            if not text:
                return None

            if text.endswith("Z"):
                text = text[:-1] + "+00:00"

            try:
                dt = datetime.fromisoformat(text)
            except ValueError:
                return None

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    @classmethod
    def _get_started_at(cls, entry) -> datetime | None:
        for attr in ("started_at", "created_at", "afk_since", "entered_at", "timestamp"):
            dt = cls._parse_datetime(getattr(entry, attr, None))
            if dt is not None:
                return dt
        return None

    @staticmethod
    def _format_datetime(dt: datetime | None) -> str:
        if dt is None:
            return "Неизвестно"
        unix_ts = int(dt.timestamp())
        return f"<t:{unix_ts}:f>"

    @staticmethod
    def _format_duration(dt: datetime | None) -> str:
        if dt is None:
            return "Неизвестно"

        seconds = max(0, int((datetime.now(timezone.utc) - dt).total_seconds()))
        days, rem = divmod(seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, _ = divmod(rem, 60)

        parts: list[str] = []
        if days:
            parts.append(f"{days} д")
        if hours:
            parts.append(f"{hours} ч")
        if minutes or not parts:
            parts.append(f"{minutes} мин")
        return " ".join(parts)

    @classmethod
    def _entry_line(cls, index: int, entry) -> str:
        name = cls._escape(getattr(entry, "display_name", None), "Неизвестно")
        reason = cls._escape(getattr(entry, "reason", None), "Не указана")
        eta = cls._escape(getattr(entry, "eta", None), "Не указано")
        started_at = cls._get_started_at(entry)

        return (
            f"**{index}. {name}**\n"
            f"Причина: {reason}\n"
            f"Когда вернётся: {eta}\n"
            f"Встал в АФК: {cls._format_datetime(started_at)}\n"
            f"Прошло: {cls._format_duration(started_at)}"
        )

    @classmethod
    def build_panel(cls, entries) -> discord.Embed:
        embed = discord.Embed(
            title="AFK-панель",
            description="Нажми кнопку ниже, чтобы встать в АФК или выйти из него.",
            color=discord.Color.blurple(),
        )

        if not entries:
            embed.add_field(name="Сейчас в АФК", value="Никто не стоит в АФК.", inline=False)
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
                current = line[: cls.FIELD_LIMIT - 1] + "…" if len(line) > cls.FIELD_LIMIT else line
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
