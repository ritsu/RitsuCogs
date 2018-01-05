import discord
import aiohttp
import asyncio
from urllib.parse import quote
from collections import namedtuple
from enum import Enum
from discord.ext import commands
from .utils.chat_formatting import pagify, box
from __main__ import send_cmd_help
import re
from cogs.utils import checks


class CustomType(Enum):
    """Types of non-standard commands"""

    alias = "alias"
    custom_command = "custom_command"
    cc = "custom_command"


class CommandSearch:
    """Search for commands"""

    def __init__(self, bot):
        self.bot = bot

        # Results from a red portal search
        self.m_redp = {"waiting": False}

    def _get_customs(self, server: discord.server.Server):
        """Get list of non-standard commands for server.
        Currently includes aliases and custom commands.
        Note that aliases and custom commands may have names with the same string.

        Args:
            server: :class:`discord.server.Server`, required

        Returns:
            A list of named tuples for non-standard commands on the server
            Example:
            [(type=CustomType.alias, name="myalis", content="flip @TwentySix"),
             (type=CustomType.cc, name="mycc", content="Welcome to {server.name}")]
        """
        if server is None:
            return []

        # Named tuple for non-standard commands
        Custom = namedtuple("Custom", "type name content")

        # Get list of searchable aliases
        cog_alias = self.bot.cogs.get("Alias")
        s_alias = [] if cog_alias is None else [
            Custom(CustomType.alias, k, v) for k, v in cog_alias.aliases.get(server.id, []).items()]

        # Get list of searchable custom commands
        cog_cc = self.bot.cogs.get("CustomCommands")
        s_cc = [] if cog_cc is None else [
            Custom(CustomType.cc, k, v) for k, v in cog_cc.c_commands.get(server.id, []).items()]

        return sorted(s_alias + s_cc, key=lambda c: c.name.lower())

    def _get_commands(self):
        """Get list of commands for server.

        Returns:
            A list of :class:`discord.ext.commands.core.Command`
        """
        maxlen = len(max(self.bot.cogs, key=len))
        return sorted([c for c in self.bot.walk_commands()], key=lambda d: '{:<{}} {}'.format(
            d.cog_name or ' none', maxlen, str(d)))

    def _get_cogs(self):
        """Get list of cogs for server.

        Returns:
            A list of named tuples for cogs.
            Note: Tags are not currently used.
            Example:
            [(name="Owner", doc="All owner-only commands that relate to debug bot operations.", tags=None),
             (name="General", doc="General commands.", tags=None)]
        """
        # Named tuple for relevant cog information
        Cog = namedtuple("Cog", "name doc tags")

        # Return list of named tuples for cogs
        return sorted([Cog(c, v.__doc__, None) for c, v in self.bot.cogs.items()], key=lambda c: c.name.lower())

    async def _redp_search(self, search_string: str):
        """Search cogs on red portal with search string.

        When done, sets self.m_redp["waiting"] to False, and
        self.m_redp["data"] to data dict returned from red portal.

        If there are results, self.m_redp["data"] will contain
            {"error":false,
             "results":{"list":[]}}
        If there are no results, self.m_redp["data"] will contain
            {"error":"EntryNotFound",
             "error_details":"No results for this search",
             "results":{}}
        """
        # Build api url
        base_url = "https://cogs.red/api/v1/search/cogs"
        url = '{}/{}'.format(base_url, quote(search_string))

        # Future response dict
        data = None

        try:
            async with aiohttp.get(url, headers={"User-Agent": "Sono-Bot"}) as response:
                data = await response.json()
        except:
            # Maybe set this to something more useful?
            data = None

        self.m_redp["data"] = data
        self.m_redp["waiting"] = False

    async def _redp_debug(self, channel):
        """For testing/debugging"""
        while self.m_redp["waiting"]:
            await asyncio.sleep(1)
        msg = "\n\n**Red Portal Cogs:**\n"
        if not self.m_redp["data"] or not self.m_redp["data"]["results"]:
            msg += "none"
        else:
            msg += "\n".join(["{} - {} by {}".format(
                cog["repo"]["name"], cog["name"], cog["author"]["name"])
                for cog in self.m_redp["data"]["results"]["list"]])
        await self.bot.send_message(channel, msg)

    @commands.command(pass_context=True, aliases=["cmds", "coms"])
    @checks.is_owner()
    async def commandsearch(self, ctx, *, search_string: str):
        """Search commands and cogs"""
        # Match command
        s_command = self._get_commands()
        # Name match only matches on command name, not group name(s)
        m_command_name = [c for c in s_command if search_string in c.name]
        # Help match is case insensitive
        m_command_help = [c for c in s_command if c.help and search_string.lower() in c.help.lower()]

        # Match non-standard command
        s_custom = self._get_customs(ctx.message.server)
        m_custom_name = [c for c in s_custom if search_string in c.name]
        m_custom_content = [c for c in s_custom if search_string in c.content]

        # Match cogs, case insensitive
        s_cog = self._get_cogs()
        m_cog_name = [c for c in s_cog if search_string.lower() in c.name.lower()]
        m_cog_doc = [c for c in s_cog if c.doc and search_string.lower() in c.doc.lower()]

        # Get red portal cogs
        self.m_redp["waiting"] = True
        self.bot.loop.create_task(self._redp_search(search_string))
        self.bot.loop.create_task(self._redp_debug(ctx.message.channel))

        # Debug
        await self._show_matches(search_string,
                                 command_name=m_command_name,
                                 command_help=m_command_help,
                                 custom_name=m_custom_name,
                                 custom_content=m_custom_content,
                                 cog_name=m_cog_name,
                                 cog_doc=m_cog_doc)

        # TODO: Display results

    async def _show_matches(self, search_string: str, **kwargs):
        """Show matches for testing / debugging"""
        msg = ""
        pat_word = re.compile(r"{}".format(search_string))
        pat_line = re.compile(r"^.*?{}.*?$".format(search_string), re.MULTILINE | re.IGNORECASE)
        rep_word = "__{}__".format(search_string)
        for k, v in kwargs.items():
            if k == "command_name":
                msg += "\n\n**Command Name:**\n"
                msg += "\n".join(["{:<30} {:>30}".format(
                    re.sub(pat_word, rep_word, str(c)), c.cog_name) for c in v])
            elif k == "command_help":
                msg += "\n\n**Command Help:**\n"
                msg += "\n".join([re.sub(pat_word, rep_word, "\n".join(re.findall(pat_line, c.help))) for c in v])
            elif k == "custom_name":
                msg += "\n\n**Custom Name:**\n"
                msg += "\n".join([re.sub(pat_word, rep_word, c.name) for c in v])
            elif k == "custom_content":
                msg += "\n\n**Custom Content:**\n"
                msg += "\n".join([re.sub(pat_word, rep_word, c.content) for c in v])
            elif k == "cog_name":
                msg += "\n\n**Cog Name:**\n"
                msg += "\n".join([re.sub(pat_word, rep_word, c.name) for c in v])
            elif k == "cog_doc":
                msg += "\n\n**Cog Doc:**\n"
                msg += "\n".join([re.sub(pat_word, rep_word, "\n".join(re.findall(pat_line, c.doc))) for c in v])
            elif k == "cog_tag":
                msg += "\n\n**Cog Tag:**\n"
                msg += "\nNot searched"

        for page in pagify(msg):
            await self.bot.say(page)


def setup(bot):
    n = CommandSearch(bot)
    bot.add_cog(n)
