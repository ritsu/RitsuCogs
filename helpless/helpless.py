from discord.ext import commands
from cogs.utils import checks
from cogs.utils.dataIO import dataIO
from __main__ import send_cmd_help
import os
import copy


class CustomHelpFormatter(commands.HelpFormatter):
    """Derived from discord.ext.commands.HelpFormatter
    Makes base class Squid-Plugins Permissions aware.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def format(self):
        """Overrides HelpFormatter.format()"""

        # Make sure Helpless cog is loaded
        help_cog = self.context.bot.get_cog("Helpless")
        if help_cog is None:
            return super().format()
        help_config = help_cog.config

        # Do not filter help for owner
        if self.context.message.author.id == self.context.bot.settings.owner:
            return super().format()

        # self._paginator is defined outside init in base class
        # noinspection PyAttributeOutsideInit
        self._paginator = commands.Paginator()

        # Filter DM
        if self.context.message.channel.is_private and help_config["dm"]["filter"]:
            self._paginator.add_line(help_config["dm"]["msg"], empty=True)
            self._paginator.close_page()
            return self._paginator.pages

        # Filter bot (calling help without args)
        if self.is_bot() and help_config["bot"]["filter"]:
            self._paginator.add_line(help_config["bot"]["msg"], empty=True)
            self._paginator.close_page()
            return self._paginator.pages

        # Filter command (permissions)
        perm_cog = self.context.bot.get_cog('Permissions')
        if (not help_config["permission"]["filter"] or
                not perm_cog or
                not hasattr(perm_cog, 'resolve_permission') or
                self.context.message.channel.is_private):
            return super().format()

        # Help is being called for a command
        if isinstance(self.command, commands.Command):
            # Make a shallow copy and change the command
            fake_context = copy.copy(self.context)
            fake_context.command = self.command
            has_perm = perm_cog.resolve_permission(fake_context)
            if not has_perm:
                self._paginator.add_line("This command has been disabled.", empty=True)
                self._paginator.close_page()
                return self._paginator.pages
            else:
                return super().format()

        # If subcommand list is empty, do not return normal help text
        if len(list(self.filter_command_list())) == 0:
            self._paginator.add_line("This command has been disabled.", empty=True)
            self._paginator.close_page()
            return self._paginator.pages

        return super().format()

    def filter_command_list(self):
        """Overrides HelpFormatter.format()"""

        # Make sure Helpless cog is loaded
        help_cog = self.context.bot.get_cog("Helpless")
        if help_cog is None:
            return super().filter_command_list()
        help_config = help_cog.config

        # Do not filter help for owner
        if self.context.message.author.id == self.context.bot.settings.owner:
            return super().filter_command_list()

        # Filter command (permissions)
        perm_cog = self.context.bot.get_cog('Permissions')
        if (not help_config["permission"]["filter"] or
                not perm_cog or
                not hasattr(perm_cog, "resolve_permission") or
                self.context.message.channel.is_private):
            return super().filter_command_list()

        # noinspection PyShadowingBuiltins
        def predicate(tuple):
            cmd = tuple[1]
            if self.is_cog():
                # filter commands that don't exist to this cog.
                if cmd.instance is not self.command:
                    return False

            if cmd.hidden and not self.show_hidden:
                return False

            # Filter permission
            fake_context = copy.copy(self.context)
            fake_context.command = cmd
            has_perm = perm_cog.resolve_permission(fake_context)
            if not has_perm:
                return False

            if self.show_check_failure:
                # we don't wanna bother doing the checks if the user does not
                # care about them, so just return true.
                return True

            try:
                return cmd.can_run(self.context) and self.context.bot.can_run(self.context)
            except commands.CommandError:
                return False

        iterator = self.command.commands.items() if not self.is_cog() else self.context.bot.commands.items()
        return filter(predicate, iterator)


class Helpless:
    """Various filters for the help command

    Permission based filtering depends on:
    https://github.com/tekulvw/Squid-Plugins/blob/master/permissions/permissions.py
    """

    default_config = {"permission": {
        "filter": True,
        "msg": "This command has been disabled."},
        "dm": {
            "filter": False,
            "msg": "Help via DM has been disabled."},
        "bot": {
            "filter": False,
            "msg": "Bot help has been disabled."}}
    base_dir = os.path.join("data", "helpless")
    config_path = os.path.join(base_dir, "config.json")

    def __init__(self, bot):
        self.bot = bot
        self.bot.formatter = CustomHelpFormatter()

        # Config
        self.config = dataIO.load_json(self.config_path)

    async def config_set(self, message, parent, child, value):
        """Write to config"""
        destination = message.author if message.channel.is_private else message.channel
        self.config[parent][child] = value
        dataIO.save_json(self.config_path, self.config)
        display_value = value
        if value is True:
            display_value = "on"
        elif value is False:
            display_value = "off"
        await self.bot.send_message(destination, "`{} {}` is now `{}`".format(parent, child, display_value))

    @commands.group(pass_context=True)
    @checks.is_owner()
    async def helpless(self, ctx):
        """Toggle various levels of help filtering"""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)
            return

    @helpless.group(pass_context=True, name="bot")
    async def b(self, ctx):
        """Manage bot help filtering ('[p]help' without arguments)"""
        if ctx.invoked_subcommand is None or isinstance(ctx.invoked_subcommand, commands.Group):
            await send_cmd_help(ctx)
            return

    @b.command(pass_context=True, name="on")
    async def b_on(self, ctx):
        """Turn bot help filtering on"""
        await self.config_set(ctx.message, "bot", "filter", True)

    @b.command(pass_context=True, name="off")
    async def b_off(self, ctx):
        """Turn bot help filtering off"""
        await self.config_set(ctx.message, "bot", "filter", False)

    @b.command(pass_context=True, name="msg")
    async def b_msg(self, ctx, *, msg: str):
        """Set bot help placeholder message"""
        await self.config_set(ctx.message, "bot", "msg", msg)

    @helpless.group(pass_context=True)
    async def dm(self, ctx):
        """Manage DM help filtering"""
        if ctx.invoked_subcommand is None or isinstance(ctx.invoked_subcommand, commands.Group):
            await send_cmd_help(ctx)
            return

    @dm.command(pass_context=True, name="on")
    async def dm_on(self, ctx):
        """Turn DM help filtering on"""
        await self.config_set(ctx.message, "dm", "filter", True)

    @dm.command(pass_context=True, name="off")
    async def dm_off(self, ctx):
        """Turn DM help filtering off"""
        await self.config_set(ctx.message, "dm", "filter", False)

    @dm.command(pass_context=True, name="msg")
    async def dm_msg(self, ctx, *, msg: str):
        """Set DM help placeholder message"""
        await self.config_set(ctx.message, "dm", "msg", msg)

    @helpless.group(pass_context=True)
    async def p(self, ctx):
        """Manage permission based filtering
        (Requires Squid-Plugins Permissions cog)"""

        if ctx.invoked_subcommand is None or isinstance(ctx.invoked_subcommand, commands.Group):
            await send_cmd_help(ctx)
            return

    @p.command(pass_context=True, name="on")
    async def p_on(self, ctx):
        """Turn permission help filtering on"""
        await self.config_set(ctx.message, "permission", "filter", True)

    @p.command(pass_context=True, name="off")
    async def p_off(self, ctx):
        """Turn permission help filtering off"""
        await self.config_set(ctx.message, "permission", "filter", False)

    @p.command(pass_context=True, name="msg")
    async def p_msg(self, ctx, *, msg: str):
        """Set permission help placeholder message"""
        await self.config_set(ctx.message, "permission", "msg", msg)

    @helpless.command(name="config")
    async def show_config(self):
        """Show current Helpless config"""
        msg = ""
        for parent in self.config:
            msg += "\n{}\n".format(parent)
            for child in self.config[parent]:
                value = self.config[parent][child]
                if value is True:
                    value = "on"
                elif value is False:
                    value = "off"
                msg += "{:>8} : {}\n".format(child, value)
        await self.bot.say("```py{}```".format(msg))


def check_folders():
    if not os.path.exists(Helpless.base_dir):
        print("Creating " + Helpless.base_dir + " folder...")
        os.makedirs(Helpless.base_dir)


def check_files():
    if not dataIO.is_valid_json(Helpless.config_path):
        print("Creating default " + Helpless.config_path + " ...")
        dataIO.save_json(Helpless.config_path, Helpless.default_config)


def setup(bot):
    check_folders()
    check_files()
    n = Helpless(bot)
    bot.add_cog(n)
