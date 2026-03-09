from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import discord

MSK = timezone(timedelta(hours=3), name="MSK")
ETA_META_PREFIX = "afkmeta:"


class EmbedFactory:
    FIELD_LIMIT = 1024
    TOTAL_LIMIT = 6000
    MAX_FIELDS = 25

    @staticmethod
    def _entry_line(index: int, entry) -> str:
        user_id = getattr(entry, "user_id", None)
        name = discord.utils.escape_markdown(getattr(entry, "display_name", "Неизвестно"))
        reason = discord.utils.escape_markdown(getattr(entry, "reason", "Не указана"))
        eta = discord.utils.escape_markdown(getattr(entry, "eta", "Не указано"))

        user_ref = f"<@{user_id}>" if user_id else name

        return (
            f"**{index}.** {user_ref}\n"
            f"Причина: {reason}\n"
            f"Когда вернётся: {eta}"
        )

        now_ts = int(datetime.now(MSK).timestamp())
        elapsed = _format_duration(max(0, now_ts - meta["start_ts"]))
        remaining = _format_duration(max(0, meta["end_ts"] - now_ts))
        started_text = datetime.fromtimestamp(meta["start_ts"], tz=MSK).strftime("%d.%m.%Y %H:%M:%S MSK")

        return (
            f"**{index}. {name}**\n"
            f"Причина: {reason}\n"
            f"Встал в АФК: {started_text}\n"
            f"Прошло: {elapsed}\n"
            f"Авто-выход: {meta['display_eta']}\n"
            f"Осталось: {remaining}"
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

        for index,  in enumerate(entries, start=1):
            line = cls.__line(index, )
            candidate = line if not current else f"{current}\n\n{line}"

            if len(candidate) <= cls.FIELD_LIMIT:
                current = candidate
                shown = index
                continue

            if current:
                chunks.append(current)
                if len(chunks) >= cls.MAX_FIELDS:
                    break
                current = line if len(line) <= cls.FIELD_LIMIT else line[: cls.FIELD_LIMIT - 1] + "…"
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



def _resolve__meta(: Any) -> dict[str, Any] | None:
    eta_value = str(getattr(, "eta", "") or "")
    meta = _decode_afk_meta(eta_value)
    if meta is not None:
        return meta

    start_ts = _extract_start_ts()
    if start_ts is None:
        return None

    end_dt = _derive_end_datetime_from_raw(eta_value.strip(), datetime.fromtimestamp(start_ts, tz=MSK))
    if end_dt is None:
        return None

    return {
        "start_ts": start_ts,
        "end_ts": int(end_dt.timestamp()),
        "display_eta": end_dt.strftime("%d.%m.%Y %H:%M MSK"),
    }



def _decode_afk_meta(value: str) -> dict[str, Any] | None:
    if not value.startswith(ETA_META_PREFIX):
        return None
    try:
        payload = json.loads(value[len(ETA_META_PREFIX):])
    except json.JSONDecodeError:
        return None

    try:
        return {
            "start_ts": int(payload["start_ts"]),
            "end_ts": int(payload["end_ts"]),
            "display_eta": str(payload["display_eta"]),
        }
    except (KeyError, TypeError, ValueError):
        return None



def _extract_start_ts(: Any) -> int | None:
    for attr_name in ("started_at", "created_at", "afk_since", "entered_at", "timestamp"):
        value = getattr(, attr_name, None)
        parsed = _coerce_timestamp(value)
        if parsed is not None:
            return parsed
    return None



def _coerce_timestamp(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=MSK)
        return int(value.astimezone(MSK).timestamp())
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        if stripped.isdigit():
            return int(stripped)
        try:
            parsed = datetime.fromisoformat(stripped)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=MSK)
        return int(parsed.astimezone(MSK).timestamp())
    return None



def _derive_end_datetime_from_raw(raw_input: str, start_dt: datetime) -> datetime | None:
    if raw_input.isdigit():
        return start_dt + timedelta(minutes=int(raw_input))

    if len(raw_input) == 5 and raw_input[2] == ":":
        try:
            hour = int(raw_input[:2])
            minute = int(raw_input[3:5])
        except ValueError:
            return None
        if hour > 23 or minute > 59:
            return None
        return start_dt.replace(hour=hour, minute=minute, second=0, microsecond=0)

    if len(raw_input) == 16 and raw_input[2] == "." and raw_input[5] == "." and raw_input[10] == " " and raw_input[13] == ":":
        try:
            day = int(raw_input[0:2])
            month = int(raw_input[3:5])
            year = int(raw_input[6:10])
            hour = int(raw_input[11:13])
            minute = int(raw_input[14:16])
            return datetime(year, month, day, hour, minute, tzinfo=MSK)
        except ValueError:
            return None

    return None



def _format_duration(total_seconds: int) -> str:
    days, rem = divmod(total_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    if days:
        return f"{days}д {hours:02}:{minutes:02}:{seconds:02}"
    return f"{hours:02}:{minutes:02}:{seconds:02}"
