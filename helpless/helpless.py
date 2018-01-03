from discord.ext import commands
from cogs.utils import checks
from __main__ import send_cmd_help
import copy


class CustomHelpFormatter(commands.HelpFormatter):
    """Derived from discord.ext.commands.HelpFormatter
    Makes base class Squid-Plugins Permissions aware.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def format(self):
        """Overrides HelpFormatter.format()
        Does not display help for command if user does not have permission.
        """

        # Return super() if there is nothing to be done
        perm_cog = self.context.bot.get_cog('Permissions')
        if (not perm_cog or not hasattr(perm_cog, 'resolve_permission') or
                self.context.message.channel.is_private or
                self.context.message.author.id == self.context.bot.settings.owner):
            return super().format()

        # self._paginator is defined outside init in base class
        # noinspection PyAttributeOutsideInit
        self._paginator = commands.Paginator()

        # Check if help is being called for a command
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

        # Help is being called for a cog, group, or bot
        # If subcommand list is empty, do not return normal help text
        if len(list(self.filter_command_list())) == 0:
            self._paginator.add_line("This command has been disabled.", empty=True)
            self._paginator.close_page()
            return self._paginator.pages

        return super().format()

    def filter_command_list(self):
        """Overrides HelpFormatter.format()
        Does not display help for command if user does not have permission.
        """

        perm_cog = self.context.bot.get_cog('Permissions')
        if (not perm_cog or not hasattr(perm_cog, 'resolve_permission') or
                self.context.message.channel.is_private or
                self.context.message.author.id == self.context.bot.settings.owner):
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

            # Make a shallow copy and change the command.
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
    """Filter help command based on permissions. Useless without:
    https://github.com/tekulvw/Squid-Plugins/blob/master/permissions/permissions.py
    """

    def __init__(self, bot):
        self.bot = bot
        self.bot.formatter = CustomHelpFormatter()

    @commands.group(pass_context=True)
    @checks.is_owner()
    async def helpless(self, ctx):
        """Toggle help filtering based on Permissions cog"""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)
            return

    @helpless.command("on")
    async def turn_on(self):
        """Turn on help filtering"""
        if self._is_on():
            await self.bot.say("Help filtering already on")
        else:
            self.bot.formatter = CustomHelpFormatter()
            await self.bot.say("Help filtering turned on")

    @helpless.command(name="off")
    async def turn_off(self):
        """Turn off help filtering"""
        if self._is_on():
            self.bot.formatter = commands.HelpFormatter()
            await self.bot.say("Help filtering turned off")
        else:
            await self.bot.say("Help filtering already off")

    def _is_on(self):
        """Check if filtering is enabled"""
        return isinstance(self.bot.formatter, CustomHelpFormatter)


def setup(bot):
    n = Helpless(bot)
    bot.add_cog(n)
