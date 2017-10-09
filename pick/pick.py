import random
import discord
from discord.ext import commands


class Pick:
    """Pick random users from your server"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(pass_context=True, no_pm=True)
    async def pick(self, ctx, *args: str):
        """Pick random users from the server (ignores bots)
        Usage: pick [num] [roles] online notafk
        Examples:
            pick          Pick 1 random user
            pick 5        Pick 5 random users
            pick online   Pick 1 random online user
            pick notafk   Pick 1 random online user who is not idle, dnd, or invis
            pick myrole   Pick 1 random user who has role "myrole"
            pick -myrole  Pick 1 random user who does not have role "myrole"
        Using multiple options (order does not matter):
            pick 2 online             Pick 2 online users
            pick 3 mods               Pick 3 mods
            pick 4 notafk subs -mods  Pick 4 subs who are not mods and are online and not idle, dnd, or invis
            pick sub fam -mod -admin  Pick 1 user who is either sub or fam, but not mod or admin
        """

        # Get params
        num = 1
        online = False
        not_afk = False
        include = set()
        exclude = set()
        for term in args:
            if term.isdigit():
                num = int(term)
            elif term.lower() == "online":
                online = True
            elif term.lower() == "notafk":
                not_afk = True
            else:
                role = term[1:] if term.startswith('-') else term
                if role not in (r.name for r in ctx.message.server.roles):
                    await self.bot.say("Role `{}` not found on server".format(role))
                    return
                if term.startswith('-'):
                    exclude.add(role)
                else:
                    include.add(role)

        # Build list of eligible members
        members = []
        for m in ctx.message.server.members:
            if online and m.status == m.status.offline:
                continue
            if not_afk and (m.status in [m.status.offline, m.status.idle, m.status.dnd, m.status.invisible]):
                continue
            if m.bot:
                continue
            roles = set([r.name for r in m.roles])
            if len(include) > 0 and len(include.intersection(roles)) == 0:
                continue
            if len(exclude) > 0 and len(exclude.intersection(roles)) > 0:
                continue
            members.append(m)

        # Pick members
        if len(members) < num or num <= 0:
            await self.bot.say("Cannot pick {} from {}".format(num, len(members)))
            return
        picked = random.sample(members, num)

        # Build Embed
        names = "\n".join(["[**{}**]({})".format(p.display_name, p.avatar_url) for p in picked])
        ids = "\n".join([str(p) for p in picked])
        embed = discord.Embed(colour=ctx.message.author.colour)
        embed.title = "Picked {} user{}".format(num, "s" if num > 1 else "")
        embed.add_field(name="Name", value=names)
        embed.add_field(name="Id", value=ids)
        embed.set_footer(text="out of {} possible user{}".format(len(members), "s" if len(members) > 1 else ""))
        await self.bot.say(embed=embed)

    @commands.command(pass_context=True, no_pm=True)
    async def pickfrom(self, ctx, *args: str):
        """Pick from a list of names
        Usage: pickfrom [names] [num]
        Examples:
            pickfrom a b c d    Pick 1 from a, b, c, d
            pickfrom a b c d 2  Pick 2 from a, b, c, d
        """

        # Get params
        num = 1
        names = []
        for i, term in enumerate(args):
            if (i == len(args) - 1) and term.isdigit():
                num = int(term)
            else:
                names.append(term)

        # Pick names
        if len(names) < num or num <= 0:
            await self.bot.say("Cannot pick {} from {}".format(num, len(names)))
            return
        picked = random.sample(names, num)

        # Build Embed
        name = "Picked {} name{}".format(num, "s" if num > 1 else "")
        value = "\n".join(["**{}**".format(p) for p in picked])
        embed = discord.Embed(colour=ctx.message.author.colour)
        embed.add_field(name=name, value=value)
        embed.set_footer(text="out of {} possible name{}".format(len(names), "s" if len(names) > 1 else ""))
        await self.bot.say(embed=embed)


def setup(bot):
    n = Pick(bot)
    bot.add_cog(n)
