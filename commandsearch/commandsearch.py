import discord
from discord.ext import commands
from .utils.chat_formatting import pagify, box
from __main__ import send_cmd_help


class CommandSearch:
    """Search for commands"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=["cmds", "coms"])
    async def commandsearch(self, search_string: str):
        """Search commands"""
        # Build commands list
        commands_flat = {}
        for k, v in self.bot.commands.items():
            self._add_command(k, v, commands_flat)

        # Get matches
        matches = [c for c in commands_flat if search_string in c]

        # Display embed if possible
        cmds = "\n".join(matches)
        cogs = "\n".join([str(commands_flat[m].cog_name) for m in matches])
        if not matches:
            embed = discord.Embed(colour=0xcc0000)
            embed.description = "No results for '{}'".format(search_string)
            await self.bot.say(embed=embed)
        elif len(cmds) < 900 and len(cogs) < 900:
            embed = discord.Embed(colour=0x00cc00)
            embed.add_field(name="Command", value=cmds)
            embed.add_field(name="Cog", value=cogs)
            embed.set_footer(text="{} result{} for '{}'".format(
                len(matches), "" if len(matches) == 1 else "s", search_string))
            await self.bot.say(embed=embed)
        else:
            maxlen = len(max(matches, key=len))
            msg = "\n".join(["{0:{1}}  {2}".format(m, maxlen, str(commands_flat[m].cog_name)) for m in matches])
            for page in pagify(msg):
                await self.bot.whisper(box(page))

    def _add_command(self, name, command, commands_flat, prefix=""):
        """Adds command to a given dict"""
        if isinstance(command, commands.core.Group):
            prefix += " {}".format(name)
            for k, v in command.commands.items():
                self._add_command(k, v, commands_flat, prefix)
        else:
            name = "{} {}".format(prefix, name).strip()
            commands_flat[name] = command


def setup(bot):
    n = CommandSearch(bot)
    bot.add_cog(n)
