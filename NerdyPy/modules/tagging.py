# -*- coding: utf-8 -*-

from datetime import UTC, datetime
from io import BytesIO
from typing import Literal

from discord import Color, Embed, FFmpegOpusAudio, Interaction, app_commands
from discord.ext.commands import GroupCog

from models.tagging import Tag, TagType

from utils.audio import QueuedSong, QueueMixin
from utils.checks import can_stop_playback, is_connected_to_voice
from utils.download import download
from utils.errors import NerpyException
from utils.helpers import error_context, send_paginated


@app_commands.guild_only()
@app_commands.checks.bot_has_permissions(send_messages=True)
class Tagging(QueueMixin, GroupCog, group_name="tag"):
    """Command group for sound and text tags"""

    queue_group = app_commands.Group(name="queue", description="Manage the Tag Queue")

    def __init__(self, bot):
        bot.log.info(f"loaded {__name__}")

        self.bot = bot
        self.queue = {}
        self.audio = self.bot.audio

    @app_commands.command(name="get")
    @app_commands.check(is_connected_to_voice)
    async def _tag_get(self, interaction: Interaction, name: str):
        """sound and text tags"""
        await self._send_to_queue(interaction, name)

    @app_commands.command(name="skip")
    @app_commands.check(can_stop_playback)
    async def _skip_audio(self, interaction: Interaction):
        """skip current track"""
        self.audio.stop(interaction.guild.id)
        await interaction.response.send_message("Skipped.", ephemeral=True)

    @queue_group.command(name="list")
    async def _list_queue(self, interaction: Interaction):
        """list current items in queue"""
        await self._send_queue_list(interaction)

    @queue_group.command(name="drop")
    @app_commands.checks.has_permissions(mute_members=True)
    async def _drop_queue(self, interaction: Interaction):
        """drop the playlist entirely"""
        self._stop_and_clear_queue(interaction.guild.id)
        await interaction.response.send_message("Queue dropped.", ephemeral=True)

    @app_commands.command(name="create")
    @app_commands.rename(tag_type="type")
    async def _tag_create(
        self, interaction: Interaction, name: str, tag_type: Literal["sound", "text", "url"], content: str
    ) -> None:
        """Create Tags."""
        with self.bot.session_scope() as session:
            if Tag.exists(name, interaction.guild.id, session):
                await interaction.response.send_message(f'tag "{name}" already exists!', ephemeral=True)
                return

        await interaction.response.defer(ephemeral=True)
        tag_type_val = TagType[tag_type].value

        with self.bot.session_scope() as session:
            self.bot.log.debug(f'{error_context(interaction)}: creating tag "{name}"')
            _tag = Tag(
                Name=name,
                Author=str(interaction.user),
                Type=tag_type_val,
                CreateDate=datetime.now(UTC),
                Count=0,
                Volume=100,
                GuildId=interaction.guild.id,
            )

            Tag.add(_tag, session)
            session.flush()

            self._add_tag_entries(session, _tag, content)

        self.bot.log.info(f'{error_context(interaction)}: tag "{name}" created')
        await interaction.followup.send(f'tag "{name}" created!', ephemeral=True)

    @app_commands.command(name="add")
    async def _tag_add(self, interaction: Interaction, name: str, content: str):
        """add an entry to an existing tag"""
        with self.bot.session_scope() as session:
            if not Tag.exists(name, interaction.guild.id, session):
                await interaction.response.send_message(f'tag "{name}" doesn\'t exists!', ephemeral=True)
                return

        await interaction.response.defer(ephemeral=True)
        with self.bot.session_scope() as session:
            _tag = Tag.get(name, interaction.guild.id, session)
            self._add_tag_entries(session, _tag, content)

        self.bot.log.info(f'{error_context(interaction)}: added entry to tag "{name}"')
        await interaction.followup.send(f'Entry added to tag "{name}"!', ephemeral=True)

    @app_commands.command(name="volume")
    async def _tag_volume(self, interaction: Interaction, name: str, vol: int):
        """adjust the volume of a sound tag"""
        if not 0 <= vol <= 200:
            await interaction.response.send_message("Volume must be between 0 and 200.", ephemeral=True)
            return
        self.bot.log.debug(f'{error_context(interaction)}: set volume of "{name}" to {vol}')
        with self.bot.session_scope() as session:
            if not Tag.exists(name, interaction.guild.id, session):
                await interaction.response.send_message(f'tag "{name}" doesn\'t exist!', ephemeral=True)
                return

        with self.bot.session_scope() as session:
            _tag = Tag.get(name, interaction.guild.id, session)
            _tag.Volume = vol
        await interaction.response.send_message(f'changed volume of "{name}" to {vol}.', ephemeral=True)

    @app_commands.command(name="delete")
    async def _tag_delete(self, interaction: Interaction, name: str):
        """delete a tag?"""
        self.bot.log.info(f'{error_context(interaction)}: deleting tag "{name}"')
        with self.bot.session_scope() as session:
            if not Tag.exists(name, interaction.guild.id, session):
                await interaction.response.send_message(f'tag "{name}" doesn\'t exist!', ephemeral=True)
                return

            Tag.delete(name, interaction.guild.id, session)
        await interaction.response.send_message(f'tag "{name}" deleted!', ephemeral=True)

    _TAG_TYPE_EMOJI = {
        TagType.sound.value: "\U0001f50a",
        TagType.text.value: "\U0001f4dd",
        TagType.url.value: "\U0001f517",
    }

    @app_commands.command(name="list")
    async def _tag_list(self, interaction: Interaction):
        """a list of all available tags"""
        with self.bot.session_scope() as session:
            tags = Tag.get_all_from_guild(interaction.guild.id, session)

            if not tags:
                await interaction.response.send_message("No tags found.", ephemeral=True)
                return

            msg = ""
            last_header = None
            for t in tags:
                if t.Name[0].upper() != last_header:
                    last_header = t.Name[0].upper()
                    if msg:
                        msg += "\n"
                    msg += f"**{last_header}**\n"
                emoji = self._TAG_TYPE_EMOJI.get(t.Type, "\u2753")
                count = t.entries.count()
                plural = "entry" if count == 1 else "entries"
                msg += f"> {emoji} `{t.Name}` \u2014 {count} {plural}\n"

            await send_paginated(interaction, msg, title="\U0001f3f7\ufe0f Tags", color=0x2ECC71)

    @app_commands.command(name="info")
    async def _tag_info(self, interaction: Interaction, name: str):
        """information about the tag"""
        with self.bot.session_scope() as session:
            t = Tag.get(name, interaction.guild.id, session)
            emoji = self._TAG_TYPE_EMOJI.get(t.Type, "\u2753")
            tag_type = TagType(t.Type).name.capitalize()
            entries = t.entries.count()

            emb = Embed(title=f"\U0001f3f7\ufe0f {t.Name}", color=Color(0x2ECC71))
            emb.add_field(name="Author", value=t.Author)
            emb.add_field(name="Type", value=f"{emoji} {tag_type}")
            emb.add_field(name="Created", value=t.CreateDate.strftime("%Y-%m-%d %H:%M"))
            emb.add_field(name="Hits", value=str(t.Count))
            emb.add_field(name="Entries", value=str(entries))
            if t.Type == TagType.sound.value:
                emb.add_field(name="Volume", value=f"{t.Volume}%")

            await interaction.response.send_message(embed=emb)

    @app_commands.command(name="raw")
    async def _tag_raw(self, interaction: Interaction, name: str):
        """raw tag data"""
        with self.bot.session_scope() as session:
            t = Tag.get(name, interaction.guild.id, session)
            msg = ""
            for i, entry in enumerate(t.entries.all(), start=1):
                if entry.TextContent:
                    msg += f"`{i}` {entry.TextContent}\n"
                else:
                    msg += f"`{i}` *(binary audio data)*\n"

            await send_paginated(interaction, msg, title=f"\U0001f3f7\ufe0f {t.Name} \u2014 Raw", color=0x2ECC71)

    async def _send_to_queue(self, interaction: Interaction, tag_name):
        self.bot.log.info(f'{error_context(interaction)}: requesting tag "{tag_name}"')
        with self.bot.session_scope() as session:
            _tag = Tag.get(tag_name, interaction.guild.id, session)
            if _tag is None:
                raise NerpyException(f'I searched everywhere, but could not find a Tag called "{tag_name}"!')

            if TagType(_tag.Type) is TagType.sound:
                song = QueuedSong(interaction.user.voice.channel, self._fetch, tag_name, tag_name)
                await self.audio.play(interaction.guild.id, song)
                await interaction.response.send_message(f"Playing **{tag_name}**", ephemeral=True)
            else:
                random_entry = _tag.get_random_entry()
                await interaction.response.send_message(random_entry.TextContent)

    def _fetch(self, song: QueuedSong):
        with self.bot.session_scope() as session:
            _tag = Tag.get(song.fetch_data, song.channel.guild.id, session)
            random_entry = _tag.get_random_entry()

            volume_multiplier = _tag.Volume / 100

            # Create FFmpegOpusAudio with volume adjustment
            data = BytesIO(random_entry.ByteContent)
            song.stream = FFmpegOpusAudio(data, pipe=True, options=f"-filter:a volume={volume_multiplier}")

    @staticmethod
    def _add_tag_entries(session, _tag, entry):
        if _tag.Type == TagType.text.value or _tag.Type == TagType.url.value:
            _tag.add_entry(entry, session)
        elif _tag.Type is TagType.sound.value:
            _tag.add_entry(entry, session, byt=download(entry, tag=True))


async def setup(bot):
    """adds this module to the bot"""
    await bot.add_cog(Tagging(bot))
