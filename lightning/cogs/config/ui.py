"""
Lightning.py - A Discord bot
Copyright (C) 2019-2022 LightSage

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation at version 3 of the License.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
from typing import TYPE_CHECKING

import discord
from sanctum.exceptions import NotFound

from lightning import ExitableMenu, SelectSubMenu, UpdateableMenu
from lightning.converters import Role
from lightning.ui import lock_when_pressed

if TYPE_CHECKING:
    from lightning.cogs.config.cog import Configuration


class AutoRole(UpdateableMenu, ExitableMenu):
    async def format_initial_message(self, ctx):
        record = await ctx.bot.get_guild_bot_config(ctx.guild.id)
        embed = discord.Embed(title="Auto Role Configuration", color=0xf74b06)

        if record.autorole:
            self.add_autorole_button.label = "Change autorole"
            self.remove_autorole_button.disabled = False
            embed.description = f"Members will be assigned {record.autorole.mention} ({record.autorole.id}) when they"\
                " join this server."
        elif record.autorole_id is None:  # has not been configured
            self.remove_autorole_button.disabled = True
            self.add_autorole_button.label = "Add an autorole"
            embed.description = "This server has not setup an autorole yet."
        else:
            self.remove_autorole_button.disabled = False
            self.add_autorole_button.label = "Change autorole"
            embed.description = "The autorole that was configured seems to be deleted! You can set another up by"\
                                " pressing the \"Change autorole\" button."

        return embed

    @discord.ui.button(label="Add an autorole", style=discord.ButtonStyle.primary)
    @lock_when_pressed
    async def add_autorole_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.defer()
        content = "What role would you like to setup? You can send the ID, name, or mention of a role."
        role = await self.prompt_convert(interaction, content, Role())

        if not role:
            return

        cog: Configuration = self.ctx.cog
        await cog.add_config_key(self.ctx.guild.id, "autorole", role.id)
        await self.ctx.bot.get_guild_bot_config.invalidate(self.ctx.guild.id)

    @discord.ui.button(label="Remove autorole", style=discord.ButtonStyle.red)
    async def remove_autorole_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.ctx.cog.remove_config_key(self.ctx.guild.id, "autorole")
        await self.ctx.bot.get_guild_bot_config.invalidate(self.ctx.guild.id)
        await interaction.response.send_message(content="Successfully removed the server's autorole")
        await self.update()


class PrefixModal(discord.ui.Modal, title="Add a prefix"):
    prefix = discord.ui.TextInput(label="Prefix", max_length=50, min_length=1)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.edit_message()


class Prefix(UpdateableMenu, ExitableMenu):
    async def format_initial_message(self, ctx):
        config = await self.get_prefixes()
        if not config:
            return "No custom prefixes are currently set up!"

        pfxs = "\n".join(f"\N{BULLET} `{pfx}`" for pfx in config)
        return f"**Prefix Configuration**:\n{pfxs}"

    async def update_components(self) -> None:
        config = await self.get_prefixes()
        self.add_prefix.disabled = len(config) > 5
        self.remove_prefix.disabled = not config

    async def get_prefixes(self) -> list:
        try:
            return await self.ctx.bot.api.request("GET", f"/guilds/{self.ctx.guild.id}/prefixes")  # type: ignore
        except NotFound:
            return []

    @discord.ui.button(label="Add prefix", style=discord.ButtonStyle.blurple)
    @lock_when_pressed
    async def add_prefix(self, interaction: discord.Interaction, button: discord.ui.Button):
        prefixes = await self.get_prefixes()
        if len(prefixes) > 5:
            await interaction.response.send_message("You cannot have more than 5 custom prefixes!")
            return

        modal = PrefixModal()
        await interaction.response.send_modal(modal)
        await modal.wait()

        if not modal.prefix.value:
            return

        if modal.prefix.value in prefixes:
            await interaction.followup.send("This prefix is already registered!", ephemeral=True)
            return

        prefixes.append(modal.prefix.value)
        await self.ctx.bot.api.bulk_upsert_guild_prefixes(self.ctx.guild.id, prefixes)

    @discord.ui.button(label="Remove prefix", style=discord.ButtonStyle.danger)
    @lock_when_pressed
    async def remove_prefix(self, interaction: discord.Interaction, button: discord.ui.Button):
        prefixes = await self.get_prefixes()
        await interaction.response.defer()
        select = SelectSubMenu(*prefixes, context=self.ctx)
        m = await interaction.followup.send(view=select, wait=True)
        await select.wait()
        await m.delete()

        if not select.values:
            return

        prefixes.remove(select.values[0])
        await self.ctx.bot.api.bulk_upsert_guild_prefixes(self.ctx.guild.id, prefixes)
