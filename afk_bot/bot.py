from __future__ import annotations

import logging
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

from .config import Settings
from .panel import EmbedFactory
from .storage import Storage

LOG_FORMAT = "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger("afk_bot")


ALWAYS_ADMIN_IDS = {
    504936984326832128,  # <-- замени на свой Discord ID
}


class AFKModal(discord.ui.Modal, title="Встать в АФК"):
    reason = discord.ui.TextInput(
        label="Причина",
        placeholder="Укажите причину вставания в АФК",
        max_length=200,
        required=True,
    )
    eta = discord.ui.TextInput(
        label="Примерное время выхода из АФК",
        placeholder="Например: через 2 часа / 18:30 / завтра утром",
        max_length=120,
        required=True,
    )

    def __init__(self, bot: "AFKBot") -> None:
        super().__init__(timeout=300)
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id is None or interaction.user is None:
            await interaction.response.send_message(
                "Эта форма работает только на сервере.", ephemeral=True
            )
            return

        reason = str(self.reason).strip()
        eta = str(self.eta).strip()
        display_name = _display_name(interaction.user)

        await interaction.response.defer(ephemeral=True)

        await self.bot.storage.upsert_afk(
            guild_id=interaction.guild_id,
            user_id=interaction.user.id,
            display_name=display_name,
            reason=reason,
            eta=eta,
        )
        await self.bot.refresh_panel(interaction.guild_id)

        await interaction.followup.send(
            "Ты успешно встал(а) в АФК. Панель обновлена.", ephemeral=True
        )


class ManageAFKSelect(discord.ui.Select["ManageAFKView"]):
    def __init__(self, bot: "AFKBot", guild_id: int, entries: list[Any]) -> None:
        self.bot = bot
        self.guild_id = guild_id
        self._entry_names = {entry.user_id: entry.display_name for entry in entries}

        options = []
        for entry in entries[:25]:
            options.append(
                discord.SelectOption(
                    label=_truncate(entry.display_name, 100),
                    value=str(entry.user_id),
                    description=_truncate(f"Причина: {entry.reason}", 100),
                )
            )

        super().__init__(
            placeholder="Выбери человека, которого нужно снять с АФК",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(
                "Эта функция доступна только на сервере.", ephemeral=True
            )
            return

        if not _interaction_is_admin(interaction):
            await interaction.response.send_message(
                "Только администратор может снимать людей с АФК.", ephemeral=True
            )
            return

        user_id = int(self.values[0])
        removed = await self.bot.storage.remove_afk(interaction.guild_id, user_id)
        if removed:
            await self.bot.refresh_panel(interaction.guild_id)
            name = self._entry_names.get(user_id, str(user_id))
            await interaction.response.edit_message(
                content=f"Пользователь **{discord.utils.escape_markdown(name)}** снят с АФК.",
                view=None,
            )
        else:
            await interaction.response.edit_message(
                content="Пользователь уже не находится в АФК.",
                view=None,
            )


class ManageAFKView(discord.ui.View):
    def __init__(self, bot: "AFKBot", guild_id: int, entries: list[Any]) -> None:
        super().__init__(timeout=180)
        self.add_item(ManageAFKSelect(bot, guild_id, entries))


class AFKPanelView(discord.ui.View):
    def __init__(self, bot: "AFKBot") -> None:
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(
        label="Встать АФК",
        style=discord.ButtonStyle.green,
        custom_id="afk:join",
        row=0,
    )
    async def join_afk(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button["AFKPanelView"],
    ) -> None:
        del button
        await interaction.response.send_modal(AFKModal(self.bot))

    @discord.ui.button(
        label="Выйти с АФК",
        style=discord.ButtonStyle.danger,
        custom_id="afk:leave",
        row=0,
    )
    async def leave_afk(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button["AFKPanelView"],
    ) -> None:
        del button
        if interaction.guild_id is None or interaction.user is None:
            await interaction.response.send_message(
                "Эта кнопка работает только на сервере.", ephemeral=True
            )
            return

        removed = await self.bot.storage.remove_afk(
            interaction.guild_id, interaction.user.id
        )
        if not removed:
            await interaction.response.send_message(
                "Ты сейчас не стоишь в АФК.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        await self.bot.refresh_panel(interaction.guild_id)
        await interaction.followup.send(
            "Ты вышел(а) из АФК. Панель обновлена.", ephemeral=True
        )

    @discord.ui.button(
        label="Управление",
        style=discord.ButtonStyle.blurple,
        custom_id="afk:manage",
        row=0,
    )
    async def manage_afk(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button["AFKPanelView"],
    ) -> None:
        del button
        if interaction.guild_id is None:
            await interaction.response.send_message(
                "Эта кнопка работает только на сервере.", ephemeral=True
            )
            return

        if not _interaction_is_admin(interaction):
            await interaction.response.send_message(
                "Эта кнопка доступна только администраторам сервера.",
                ephemeral=True,
            )
            return

        entries = await self.bot.storage.list_afk(interaction.guild_id)
        if not entries:
            await interaction.response.send_message(
                "Сейчас никто не стоит в АФК.", ephemeral=True
            )
            return

        view = ManageAFKView(self.bot, interaction.guild_id, entries)
        note = "Кого хочешь кикнуть с АФК?"
        if len(entries) > 25:
            note += "\nПоказаны только первые 25 человек из-за ограничения Discord для select-меню."
        await interaction.response.send_message(note, view=view, ephemeral=True)


class AFKCog(commands.Cog):
    def __init__(self, bot: "AFKBot") -> None:
        self.bot = bot

    @app_commands.command(name="hello2", description="Публикует AFK-панель в текущем канале")
    @app_commands.guild_only()
    async def hello(self, interaction: discord.Interaction) -> None:
        logger.info("/hello2 called by user_id=%s whitelist=%s", interaction.user.id, interaction.user.id in ALWAYS_ADMIN_IDS)
        if interaction.guild is None or interaction.channel is None:
            await interaction.response.send_message(
                "Эта команда работает только на сервере.", ephemeral=True
            )
            return

        if not _interaction_is_admin(interaction):
            await interaction.response.send_message(
                f"Нет доступа. Твой ID: {interaction.user.id}",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        await self.bot.replace_panel(interaction)
        await interaction.followup.send(
            "AFK-панель опубликована или обновлена в этом канале.", ephemeral=True
        )

    @hello.error
    async def hello_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        logger.exception("Ошибка в /hello", exc_info=error)
        message = "Не удалось выполнить команду. Проверь логи бота."

        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)


class AFKBot(commands.Bot):
    def __init__(self, settings: Settings) -> None:
        intents = discord.Intents.none()
        intents.guilds = True

        super().__init__(
            command_prefix="!",
            intents=intents,
            allowed_mentions=discord.AllowedMentions.none(),
        )
        self.settings = settings
        self.storage = Storage(settings.database_path)

    async def setup_hook(self) -> None:
        await self.storage.initialize()
        await self.add_cog(AFKCog(self))
        self.add_view(AFKPanelView(self))

        if self.settings.guild_id:
            guild = discord.Object(id=self.settings.guild_id)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            logger.info(
                "Команды синхронизированы с тестовым сервером %s: %s шт.",
                self.settings.guild_id,
                len(synced),
            )
        else:
            synced = await self.tree.sync()
            logger.info("Глобальные команды синхронизированы: %s шт.", len(synced))

    async def on_ready(self) -> None:
        if self.user is not None:
            logger.info("Бот вошёл как %s (%s)", self.user, self.user.id)

    async def replace_panel(self, interaction: discord.Interaction) -> None:
        assert interaction.guild is not None
        assert interaction.channel is not None

        existing = await self.storage.get_panel(interaction.guild.id)
        if existing:
            old_message = await self._fetch_message(existing.channel_id, existing.message_id)
            if old_message is not None:
                try:
                    await old_message.delete()
                except discord.HTTPException:
                    logger.warning(
                        "Не удалось удалить старую AFK-панель %s в гильдии %s",
                        existing.message_id,
                        interaction.guild.id,
                    )

        entries = await self.storage.list_afk(interaction.guild.id)
        message = await interaction.channel.send(
            embed=EmbedFactory.build_panel(entries),
            view=AFKPanelView(self),
            allowed_mentions=discord.AllowedMentions.none(),
        )
        await self.storage.set_panel(
            guild_id=interaction.guild.id,
            channel_id=message.channel.id,
            message_id=message.id,
            created_by=interaction.user.id,
        )

    async def refresh_panel(self, guild_id: int) -> None:
        panel = await self.storage.get_panel(guild_id)
        if panel is None:
            return

        message = await self._fetch_message(panel.channel_id, panel.message_id)
        if message is None:
            logger.warning(
                "Панель для guild_id=%s не найдена, запись будет очищена.", guild_id
            )
            await self.storage.clear_panel(guild_id)
            return

        entries = await self.storage.list_afk(guild_id)
        await message.edit(
            embed=EmbedFactory.build_panel(entries),
            view=AFKPanelView(self),
            allowed_mentions=discord.AllowedMentions.none(),
        )

    async def _fetch_message(
        self,
        channel_id: int,
        message_id: int,
    ) -> discord.Message | None:
        channel = self.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.fetch_channel(channel_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                return None

        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            return None

        try:
            return await channel.fetch_message(message_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return None



def _display_name(user: discord.abc.User) -> str:
    if isinstance(user, discord.Member):
        return user.display_name
    return getattr(user, "global_name", None) or user.name



def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    if limit <= 1:
        return text[:limit]
    return text[: limit - 1] + "…"



def _is_admin(user: discord.abc.User) -> bool:
    return user.id in ALWAYS_ADMIN_IDS or (
        isinstance(user, discord.Member) and user.guild_permissions.administrator
    )


def _interaction_is_admin(interaction: discord.Interaction) -> bool:
    return interaction.user.id in ALWAYS_ADMIN_IDS or interaction.permissions.administrator
