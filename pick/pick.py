import random
import time
import math
import discord
from discord.ext import commands
from enum import Enum
from __main__ import send_cmd_help
import asyncio


class PickType(Enum):
    """ Types of events for PickEvent """

    custom = "custom"
    event = "event"
    instant = "instant"


class PickEvent:
    """ An event created by Pick

    Attributes
    ----------
    author    : :class:`Member`   user that started the event
    channel   : :class:`Channel`  channel where the event is taking place
    name      : str               name of event
    duration  : int               duration of event in seconds
    num       : int               number of users to pick
    roles     : dict              roles to include or exclude
    statuses  : dict              statuses to include or exclude
    picktype  : :enum:`PickType`  type of pick
    itemtype  : str               type of item
    items     : list              users / names entered in the event
    start_time: float             time when event started (seconds since epoch)
    """

    __slots__ = ["author", "channel", "name", "duration", "num", "roles", "statuses",
                 "picktype", "itemtype", "items", "start_time"]

    def __init__(self, message, **kwargs):
        self.author = message.author
        self.channel = message.channel
        self.name = kwargs.get("name", None)
        self.duration = kwargs.get("duration", None)
        self.num = kwargs.get("num", 1)
        self.roles = kwargs.get("roles", {"include": set(), "exclude": set()})
        self.statuses = kwargs.get("statuses", {"include": set(), "exclude": set()})
        self.picktype = kwargs.get("picktype", PickType.instant)
        self.itemtype = "choice" if self.picktype == PickType.custom else "member"
        self.items = []
        self.start_time = time.time()

    def add(self, item):
        """Add item to pick candidates"""
        self.items.append(item)

    def contains(self, item) -> bool:
        """Check if item is a pick candidate"""
        return item in self.items

    def validate(self, member: discord.Member) -> bool:
        """Check if Discord member is a valid member for pick event"""
        if member.bot:
            return False
        if not self.channel.permissions_for(member).read_messages:
            return False
        roles = set([r.name for r in member.roles])
        if len(self.roles["include"]) > 0 and len(self.roles["include"].intersection(roles)) == 0:
            return False
        if len(self.roles["exclude"]) > 0 and len(self.roles["exclude"].intersection(roles)) > 0:
            return False
        if len(self.statuses["include"]) > 0 and member.status.value not in self.statuses["include"]:
            return False
        if len(self.statuses["exclude"]) > 0 and member.status.value in self.statuses["exclude"]:
            return False
        return True

    def pick(self) -> list:
        """Pick item(s) from candidates and return result"""
        return random.sample(self.items, self.num) if self.num < len(self.items) else self.items

    def time_left(self) -> int:
        """Number of seconds until event is over"""
        return int(math.ceil(self.duration - (time.time() - self.start_time)))

    @staticmethod
    def params_for(picktype: PickType) -> dict:
        """Return default params based on pick type"""
        return {"roles": {"include": set(), "exclude": set()},
                "statuses": {"include": set(), "exclude": set()},
                "picktype": picktype}


class Pick:
    """Pick random users from your channel"""

    def __init__(self, bot):
        self.bot = bot
        self.events = []
        self.task = bot.loop.create_task(self.check_events())

    def __unload(self):
        self.task.cancel()

    @commands.group(pass_context=True)
    async def picks(self, ctx):
        """View and manage live pick events"""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)
            return

    @picks.command(pass_context=True, name="delete")
    async def picks_delete(self, ctx, name: str, channel: discord.Channel=None):
        """Delete a pick event you created

        Description:
          name     Name of event
          channel  Channel event is in (optional)

        Examples:
          picks delete giveaway
          picks delete giveaway #contests
        """
        if not channel:
            channel = ctx.message.channel
        events = [event for event in self.events if event.channel == channel and event.name == name]
        if len(events) == 0:
            await self.bot.say("Event `{}` not found in channel `{}`".format(name, channel.name))
            return
        event = events[0]
        if event.author != ctx.message.author:
            await self.bot.say("Only the event creator can delete this event")
        else:
            self.events.remove(event)
            await self.bot.say("**{}** deleted.".format(event.name))

    @picks.command(pass_context=True, name="force")
    async def picks_force(self, ctx, name: str, channel: discord.Channel=None):
        """Force the bot to pick for an event you created

        Description:
          name     Name of event
          channel  Channel event is in (optional)

        Examples:
          picks force giveaway
          picks force giveaway #contests
        """
        if not channel:
            channel = ctx.message.channel
        events = [event for event in self.events if event.channel == channel and event.name == name]
        if len(events) == 0:
            await self.bot.say("Event `{}` not found in channel `{}`".format(name, channel.name))
            return
        event = events[0]
        if event.author != ctx.message.author:
            await self.bot.say("Only the event creator can force pick")
        else:
            self.events.remove(event)
            await self._show_picks(event)

    @picks.command(pass_context=True, name="show")
    async def picks_show(self, ctx, name: str, channel: discord.Channel=None):
        """Show details about a pick event

        Description:
          name     Name of event
          channel  Channel event is in (optional)

        Examples:
          picks show giveaway
          picks show giveaway #contests
        """
        if not channel:
            channel = ctx.message.channel
        events = [event for event in self.events if event.channel == channel and event.name == name]
        if len(events) == 0:
            await self.bot.say("Event `{}` not found in channel `{}`".format(name, channel.name))
            return
        event = events[0]
        msg = "Stats for **{0}**. Type **{0}** in *#{1}* to be entered.".format(event.name, event.channel.name)
        await self._show_event(event, ctx.message.channel, msg)

    @picks.command(pass_context=True, name="check")
    async def picks_check(self, ctx):
        """Check if you are entered into any pick events.
        Bot will whisper you.
        """
        events = ["**{}**".format(event.name) for event in self.events if event.contains(ctx.message.author)]
        if len(events) == 0:
            await self.bot.whisper("You are not entered in any events.")
        else:
            await self.bot.whisper("You are entered in the following events: {}".format(", ".join(events)))

    @picks.command(pass_context=True, name="list")
    async def picks_list(self, ctx):
        """List all currently running pick events on this server"""
        # Get events
        events = [event for event in self.events if event.channel.server == ctx.message.server]
        context = ctx.message.server.name

        # Create embed
        embed = discord.Embed(colour=ctx.message.author.colour)
        embed.title = "Live Events for {}:".format(context)
        if len(events) > 0:
            embed.add_field(name="Event", value="\n".join(["**{}**".format(e.name) for e in events]))
            embed.add_field(name="Remaining", value="\n".join([self._seconds_to_hms(e.time_left()) for e in events]))
            embed.add_field(name="Creator", value="\n".join(["[**{}**]({}) in _#{}_".format(
                e.author.display_name, e.author.avatar_url, e.channel.name) for e in events]))
        else:
            embed.description = "None"
        await self.bot.send_message(ctx.message.channel, embed=embed)

    @commands.command(pass_context=True, no_pm=True)
    async def pick(self, ctx, *args: str):
        """Pick random users from the channel (ignores bots)
        Usage:
          pick [num] +[role] -[role] +[status] -[status]

        Description:
          num     Number of users to pick (default is 1)
          +role   Users must have at least one of these roles
          -role   Users cannot have any of these roles
          +status Users must have at least one of these statuses
          -status Users cannot have any of these statuses

        Status Options:
          'online'    Online (green dot)
          'idle'      Idle / Away (orange dot)
          'dnd'       Do not disturb (red dot)
          'invisible' Invisible
          'offline'   Offline

        Examples:
          pick 2
          pick 3 +mod +online
          pick 3 +sub +patreon -mod -admin -offline -invisible
        """
        # Get params
        params = PickEvent.params_for(PickType.instant)
        statuses = set([s.value for s in discord.enums.Status])
        roles = set([r.name for r in ctx.message.server.roles])
        for arg in args:
            if arg[0] == "+":
                term = arg[1:]
                if term in statuses:
                    params["statuses"]["include"].add(term)
                elif term in roles:
                    params["roles"]["include"].add(term)
                else:
                    await self.bot.say("Role not found: `{}`".format(term))
                    return
            elif arg[0] == "-":
                term = arg[1:]
                if term in statuses:
                    params["statuses"]["exclude"].add(term)
                elif term in roles:
                    params["roles"]["exclude"].add(term)
                else:
                    await self.bot.say("Role not found: `{}`".format(term))
                    return
            elif arg.isdigit():
                # This needs to be at end of elifs to avoid catching
                # roles that are all numeric characters
                params["num"] = int(arg)
            else:
                await self.bot.say("Unrecognized option: `{}`".format(arg))
                return

        # Perform pick
        event = PickEvent(ctx.message, **params)
        for member in ctx.message.server.members:
            if event.validate(member):
                event.add(member)
        await self._show_picks(event)

    @commands.command(pass_context=True, no_pm=True)
    async def pickfor(self, ctx, *args: str):
        """Create a pick event users can enter by typing the name of the event in chat
        Usage:
          pickfor <event> <duration> [num] +[role] -[role]

        Description:
          event    Name of the event
          duration How long event will last before bot picks winners
                   Duration is any number followed by 's', 'm', or 'h'
          num      Number of users to pick (default is 1)
          +role    Users must have at least one of these roles
          -role    Users cannot have any of these roles

        Examples:
          pickfor raffle 60s 2
          pickfor giveaway 24h 3
          pickfor myteam 2m 4 +mod +sub
        """
        if not args:
            await send_cmd_help(ctx)
            return

        # Get params
        params = PickEvent.params_for(PickType.event)
        roles = set([r.name for r in ctx.message.server.roles])
        for arg in args:
            if arg[0] == "+":
                term = arg[1:]
                if term in roles:
                    params["roles"]["include"].add(term)
                else:
                    await self.bot.say("Role not found: `{}`".format(term))
                    return
            elif arg[0] == "-":
                term = arg[1:]
                if term in roles:
                    params["roles"]["exclude"].add(term)
                else:
                    await self.bot.say("Role not found: `{}`".format(term))
                    return
            elif arg[:-1].isdigit() and arg[-1] in ('s', 'm', 'h'):
                params["duration"] = self._get_seconds(arg)
            elif arg.isdigit():
                params["num"] = int(arg)
            elif "name" not in params:
                params["name"] = arg
            else:
                await self.bot.say("Unrecognized option: `{}`".format(arg))
                return

        # Validate params
        if "name" not in params:
            await self.bot.say("Event name missing")
            return
        if "duration" not in params:
            await self.bot.say("Event duration missing")
            return

        # Create event
        event = PickEvent(ctx.message, **params)
        if params["name"] in [event.name for event in self.events if event.channel == ctx.message.channel]:
            msg = "An event named `{}` already exists. Please specify a different name.".format(params["name"])
            await self.bot.say(msg)
            return
        self.events.append(event)
        msg = "**{0}** started! Type **{0}** in chat within {1} to be entered.".format(
            event.name, self._seconds_to_hms(event.duration))
        await self._show_event(event, event.channel, msg)

    @commands.command(pass_context=True, no_pm=True)
    async def pickfrom(self, ctx, *args: str):
        """Pick from a list of names
        Usage: pickfrom <names> [num]

        Description:
            pickfrom a b c     Pick 1 from a, b, c
            pickfrom a b c 2   Pick 2 from a, b, c
        """
        if not args:
            await send_cmd_help(ctx)
            return

        # Get params
        params = PickEvent.params_for(PickType.custom)
        names = list(args)
        if names[-1].isdigit() and int(names[-1]) > 0:
            params["num"] = int(names.pop())

        # Perform pick
        event = PickEvent(ctx.message, **params)
        for name in names:
            event.add(name)
        await self._show_picks(event)

    async def check_events(self):
        """Loop to check events and perform picks when event is up"""
        while True:
            for event in self.events:
                if event.time_left() <= 0:
                    await self._show_picks(event)
                    self.events.remove(event)
            await asyncio.sleep(1)

    async def on_message(self, message):
        """Check messages for entries into events"""
        if message.author.bot:
            return
        for event in [e for e in self.events if e.channel == message.channel and e.name == message.content]:
            if not event.contains(message.author) and event.validate(message.author):
                event.add(message.author)

    async def _show_picks(self, event: PickEvent):
        """Perform picks and display results in event channel"""
        picks = event.pick()
        embed = discord.Embed(colour=event.author.colour)
        embed.description = "Picked **{}**".format(len(picks))
        if event.picktype == PickType.instant:
            embed.description += " {}{}".format(event.itemtype, "" if len(picks) == 1 else "s")
        elif event.picktype == PickType.event:
            embed.description += " {}{} for **{}**".format(event.itemtype, "" if len(picks) == 1 else "s", event.name)
        if len(picks) > 0:
            if event.picktype == PickType.custom:
                embed.description += "\n"
                embed.description += "\n".join(["**{}**".format(p) for p in picks])
            else:
                names = "\n".join(["[**{}**]({})".format(p.display_name, p.avatar_url) for p in picks])
                ids = "\n".join([str(p) for p in picks])
                embed.add_field(name="Name", value=names)
                embed.add_field(name="Id", value=ids)
        embed.set_footer(text="out of {} possible {}{}".format(
            len(event.items), event.itemtype, "" if len(event.items) == 1 else "s"))
        if event.picktype == PickType.event:
            await self.bot.send_message(event.channel, "{}".format(event.author.mention), embed=embed)
        else:
            await self.bot.send_message(event.channel, embed=embed)

    async def _show_event(self, event: PickEvent, channel: discord.Channel, description: str=""):
        """Display event status to the channel requesting it,
        not necessarily the channel the event belongs to
        """
        embed = discord.Embed(colour=event.author.colour)
        embed.description = description
        embed.add_field(name="Duration", value=self._seconds_to_hms(event.duration))
        embed.add_field(name="Remaining", value=self._seconds_to_hms(event.time_left()))
        embed.add_field(name="Number entered", value=str(len(event.items)))
        embed.add_field(name="Number to pick", value=event.num)
        include = ", ".join(event.roles["include"]) if len(event.roles["include"]) > 0 else "--"
        exclude = ", ".join(event.roles["exclude"]) if len(event.roles["exclude"]) > 0 else "--"
        embed.add_field(name="Roles Included", value=include)
        embed.add_field(name="Roles Excluded", value=exclude)
        embed.set_footer(text="Created by {} in #{}".format(event.author.display_name, event.channel.name))
        await self.bot.send_message(channel, embed=embed)

    @staticmethod
    def _get_seconds(s: str) -> int:
        """ Parse seconds from string in format [num](s|m|h) """
        if not s[:-1].isdigit():
            return -1
        elif s[-1] == 's':
            return int(s[:-1])
        elif s[-1] == 'm':
            return int(s[:-1]) * 60
        elif s[-1] == 'h':
            return int(s[:-1]) * 60 * 60
        else:
            return -1

    @staticmethod
    def _seconds_to_hms(s: int) -> str:
        """ Convert seconds to xx:xx:xx """
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        if h > 0:
            return "{}:{:02d}:{:02d}".format(h, m, s)
        else:
            return "{:02d}:{:02d}".format(m, s)


def setup(bot):
    n = Pick(bot)
    bot.add_cog(n)
