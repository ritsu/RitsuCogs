from discord.ext import commands
from .utils.dataIO import fileIO
import os
import asyncio
import aiohttp
from datetime import datetime

try: # check if BeautifulSoup4 is installed
	from bs4 import BeautifulSoup
	soupAvailable = True
except:
	soupAvailable = False

class TokyoTosho:
    """TokyoTosho search and RSS alerts"""

    types = {"anime": 1, "music": 2, "manga": 3, "hentai": 4, "other": 5, "raws": 7, "drama": 8, "music-video": 9, "non-english": 10, "batch": 11, "hentai-anime": 12, "hentai-manga": 13, "hentai-games": 14, "jav": 15 }
    base_url = "http://tokyotosho.info/"
    more_limit = 5
    max_comment_length = 160
    max_alert = 5
    check_delay = 60
    pubdate_format = "%a, %d %b %Y %H:%M:%S %Z"

    def __init__(self, bot):
        self.bot = bot
        self.alerts = fileIO("data/tokyotosho/alerts.json", "load")

    def check_type(self):
        pass

    def build_query(self):
        pass

    @commands.group(pass_context = True)
    async def tt(self, ctx):
        """TokyoTosho search and RSS alerts"""

        if ctx.invoked_subcommand is None:
            await self.bot.say("```"
                               "\nTokyoTosho search and RSS alerts"
                               "\n\nCommands:"
                               "\n\tlist    List current RSS alerts"
                               "\n\tremove  Remove an RSS alert"
                               "\n\tcheck   Check current RSS alerts against RSS feed"
                               "\n\ttypes   Show valid types/categories"
                               "\n\tadd     Add an RSS alert for new torrents on TokyoTosho"
                               "\n\tsearch  Search TokyoTosho and display results"
                               "\n\nType !help command for more info on a command."
                               "```")

    @tt.command(pass_context=True, name='search', aliases=['s'])
    async def ttsearch(self, ctx, *query: str):
        """Search TokyoTosho and display results

        !tt search <term>+ (-<term>*) (#<type>)

        Examples:
            search horriblesubs madoka 1080
            search madoka -horriblesubs -dub
            search madoka #music
        """

        # build query
        terms = ""
        type = ""
        for term in query:
            if term[0] == '#':
                if type:
                    await self.bot.say("Only 1 type can be specified for search")
                    return
                if term[1:].lower() in TokyoTosho.types:
                    type = str(TokyoTosho.types[term[1:].lower()])
                else:
                    await self.bot.say(term[1:] + " is not a valid type. Type !tt types to show valid types.")
                    return
            elif terms:
                terms += "+" + term
            else:
                terms = term
        q = "terms=" + terms
        if type:
            q += "&type=" + type
        url = TokyoTosho.base_url + "search.php?" + q

        # parse results
        await self.bot.say("Querying " + url + " ...")
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                soup = BeautifulSoup(await response.text(), "html.parser")

        table = soup.find("table", attrs={"class": "listing"})
        rows = table.find_all("tr")
        result = []
        count = 0
        for row in rows:
            td_link = row.find("td", attrs={"class": "desc-top"})
            td_desc = row.find("td", attrs={"class": "desc-bot"})
            if td_link:
                a_link = td_link.find_all("a")[-1]
                #await self.bot.say("**" + a_link.get_text() + "** ::\n " + a_link["href"])
                item = "**" + a_link.get_text() + "** :: " + a_link.get("href")
            elif td_desc:
                desc = td_desc.get_text()
                if len(desc) > TokyoTosho.max_comment_length:
                    desc = desc[:TokyoTosho.max_comment_length] + " ..."
                #await self.bot.say("`" + td_desc.get_text() + "`")
                # remove links from comment
                desc = desc.replace("http", "h\*\*p")
                item += "\n" + desc
                result.append(item)
                count += 1

        summary = table.find_next_sibling("p")
        result.append("*" + summary.get_text() + "*")

        # display results in channel
        lines_displayed = 0
        for r in result:
            # flood prevention
            if lines_displayed > 0 and lines_displayed % TokyoTosho.more_limit == 0:
                await self.bot.say("Type 'more' or 'm' to continue...")
                answer = await self.bot.wait_for_message(timeout=15, author=ctx.message.author)
                if not answer or answer.content.lower() not in ["more", "m"]:
                    await self.bot.say("Command output stopped.")
                    return
            if r:
                await self.bot.say(r)
                lines_displayed += 1

    @tt.command(pass_context=True, name='add', aliases=['a'])
    async def ttadd(self, ctx, *query: str):
        """Add an RSS alert for new torrents on TokyoTosho

        !tt add (<term>*) (-<term>*) (#<type>*)

        Examples:
            add horriblesubs madoka 1080
            add madoka -horriblesubs -dub
            add madoka #anime #music
        """

        channel = ctx.message.channel

        # build query
        include = set()
        exclude = set()
        type = set()
        for term in query:
            if term[0] == '#':
                if term[1:].lower() in TokyoTosho.types:
                    type.add(str(TokyoTosho.types[term[1:].lower()]))
                else:
                    await self.bot.say(term[1:] + " is not a valid type. Type !tt types to show valid types.")
                    return
            elif term[0] == '-':
                exclude.add(term)
            else:
                include.add(term)

        # check if alert already exists
        for i, s in enumerate(self.alerts):
            #check if type + include + exclude sets match
            tmp_include = set(s["INCLUDE"])
            tmp_exclude = set(s["EXCLUDE"])
            tmp_type = set(s["TYPE"])
            if include == tmp_include and exclude == tmp_exclude and type == tmp_type:
                if channel.id in s["CHANNELS"]:
                    await self.bot.say("Alert already exists in this channel. Type !tt list to view current alerts.")
                    return
                else:
                    self.alerts[i]["CHANNELS"].append(channel.id)
                    fileIO("data/tokyotosho/alerts.json", "save", self.alerts)
                    await self.bot.say("Alert has been added to this channel with the following options:"
                                       "\nInclude: " + ", ".join(include) +
                                       "\nExclude: " + ", ".join(exclude) +
                                       "\nType: "  + ", ".join([k for k, v in TokyoTosho.types.items() if str(v) in type])
                    )
                    return

        # add alert
        self.alerts.append({"LAST_PUBDATE": "",
                            "CHANNELS": [channel.id],
                            "INCLUDE": list(include),
                            "EXCLUDE": list(exclude),
                            "TYPE": list(type)})

        await self.bot.say("Alert activated for this channel with the following options:"
                           "\nInclude: " + ", ".join(include) +
                           "\nExclude: " + ", ".join(exclude) +
                           "\nType: "  + ", ".join([k for k, v in TokyoTosho.types.items() if str(v) in type])
        )

        fileIO("data/tokyotosho/alerts.json", "save", self.alerts)

    @tt.command(pass_context=True, name='remove', aliases=['r'])
    async def ttremove(self, ctx, *query: str):
        """Remove an RSS alert

        !tt remove <term>+ (-<term>*) (#<type>*)
        """

        channel = ctx.message.channel

        # build query
        include = set()
        exclude = set()
        type = set()
        for term in query:
            if term[0] == '#':
                if term[1:].lower() in TokyoTosho.types:
                    type.add(str(TokyoTosho.types[term[1:].lower()]))
                else:
                    await self.bot.say(term[1:] + " is not a valid type. Type !tt types to show valid types.")
                    return
            elif term[0] == '-':
                exclude.add(term)
            else:
                include.add(term)

        # look for alert and remove if found
        count = 0
        for i, s in enumerate(self.alerts):
            #check if type + include + exclude sets match
            tmp_include = set(s["INCLUDE"])
            tmp_exclude = set(s["EXCLUDE"])
            tmp_type = set(s["TYPE"])
            if include == tmp_include and exclude == tmp_exclude and type == tmp_type:
                if channel.id in s["CHANNELS"]:
                    count += 1
                    if len(s["CHANNELS"]) == 1:
                        self.alerts.remove(s)
                        await self.bot.say("Alert has been removed from this channel.")
                    else:
                        self.alerts[i]["CHANNELS"].remove(channel.id)
                        await self.bot.say("Alert has been removed from this channel.")

        if not count:
            await self.bot.say("Alert not found.")

        # update file
        fileIO("data/tokyotosho/alerts.json", "save", self.alerts)

    @tt.command(pass_context=True, name='list', aliases=['l'])
    async def ttlist(self, ctx, *query: str):
        """List current RSS alerts"""

        channel = ctx.message.channel
        count = 0
        for i, s in enumerate(self.alerts):
            if channel.id in s["CHANNELS"]:
                await self.bot.say("Include: " + ", ".join(s["INCLUDE"]) +
                                   "\nExclude: " + ", ".join(s["EXCLUDE"]) +
                                   "\nType: "  + ", ".join([k for k, v in TokyoTosho.types.items() if str(v) in s["TYPE"]]) +
                                   "\n------------")
                count += 1

        if not count:
            await self.bot.say("No alerts found for this channel.")

    @tt.command(pass_context=True, name='check', aliases=['c'])
    async def ttcheck(self, ctx, *query: str):
        """Check current RSS alerts against RSS feed"""

        # get rss
        url = TokyoTosho.base_url + "rss.php"
        await self.bot.say("Querying " + url + " ...")
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                soup = BeautifulSoup(await response.text(), "xml")

        channel = ctx.message.channel
        count = 0
        for i, s in enumerate(self.alerts):
            if channel.id in s["CHANNELS"]:
                count += 1
                await self.bot.say("Include: " + ", ".join(s["INCLUDE"]) +
                                   "\nExclude: " + ", ".join(s["EXCLUDE"]) +
                                   "\nType: "  + ", ".join([k for k, v in TokyoTosho.types.items() if str(v) in s["TYPE"]]))
                include = set(s["INCLUDE"])
                exclude = set([term[1:] for term in s["EXCLUDE"]])
                type = set([k for k, v in TokyoTosho.types.items() if str(v) in s["TYPE"]])

                # parse rss and display result
                items = soup.find_all("item")
                count_found = 0
                for item in items:
                    match = True
                    title = item.find("title").get_text()
                    for term in include:
                        if term.lower() not in title.lower():
                            match = False
                            break
                    if not match:
                        continue
                    for term in exclude:
                        if term.lower() in title.lower():
                            match = False
                            break
                    if not match:
                        continue
                    for term in type:
                        if term.lower() == item.find("category").get_text().lower():
                            break
                        match = False
                    if not match:
                        continue
                    await self.bot.say("**" + title + "** :: " + item.find("link").get_text() + "\n" + item.find("pubDate").get_text())
                    break
                if not match:
                    await self.bot.say("No items found for this alert.")
                await self.bot.say("------------")
        if not count:
            await self.bot.say("No alerts found for this channel.")

    @tt.command(pass_context=True, name='types', aliases=['t'])
    async def tttypes(self, context):
        """Show valid types/categories"""

        await self.bot.say(", ".join(sorted(TokyoTosho.types.keys())))


    async def rss_checker(self):
        """Check RSS feed for new items"""

        while self == self.bot.get_cog("TokyoTosho"):
            # get rss
            url = TokyoTosho.base_url + "rss.php"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    soup = BeautifulSoup(await response.text(), "xml")

            # iterate through alerts
            for i, s in enumerate(self.alerts):
                include = set(s["INCLUDE"])
                exclude = set([term[1:] for term in s["EXCLUDE"]])
                type = set([k for k, v in TokyoTosho.types.items() if str(v) in s["TYPE"]])
                last_pubdate = s["LAST_PUBDATE"]

                # parse rss
                items = soup.find_all("item")
                result = ""
                new_pubdate = ""
                count = 0
                for item in items:
                    match = True

                    # skip items that are older than the last alerted item (assume rss is sorted by date, newest first)
                    pubdate = item.find("pubDate").get_text()
                    if last_pubdate and datetime.strptime(last_pubdate, TokyoTosho.pubdate_format) >= datetime.strptime(pubdate, TokyoTosho.pubdate_format):
                        break

                    # skip items that do not include all required search terms
                    title = item.find("title").get_text()
                    for term in include:
                        if term.lower() not in title.lower():
                            match = False
                            break
                    if not match:
                        continue

                    # skip items that include any of the excluded search terms
                    for term in exclude:
                        if term.lower() in title.lower():
                            match = False
                            break
                    if not match:
                        continue

                    # skip items that do not include at least one of the type categories
                    for term in type:
                        if term.lower() == item.find("category").get_text().lower():
                            break
                        match = False
                    if not match:
                        continue

                    # add result and update pubdate
                    result += "**" + title + "** :: " + item.find("link").get_text() + "\n" + item.find("pubDate").get_text() + "\n"
                    if not new_pubdate:
                        new_pubdate = pubdate
                    count += 1
                    if count > TokyoTosho.max_alert:
                        break

                # alert channels
                if result:
                    for channel in s["CHANNELS"]:
                        channel_obj = self.bot.get_channel(channel)
                        if channel_obj is None:
                            continue
                        can_speak = channel_obj.permissions_for(channel_obj.server.me).send_messages
                        if channel_obj and can_speak:
                            await self.bot.send_message(
                                self.bot.get_channel(channel),
                                "TokyoTosho RSS alert:\n" + result)

                # update LAST_PUBDATE
                if new_pubdate:
                    self.alerts[i]["LAST_PUBDATE"] = new_pubdate
                    fileIO("data/tokyotosho/alerts.json", "save", self.alerts)

                await asyncio.sleep(0.5)

            await asyncio.sleep(TokyoTosho.check_delay)

        # end while loop
    # end rss_checker


def check_folders():
    if not os.path.exists("data/tokyotosho"):
        print("Creating data/tokyotosho folder...")
        os.makedirs("data/tokyotosho")


def check_files():
    f = "data/tokyotosho/alerts.json"
    if not fileIO(f, "check"):
        print("Creating empty alerts.json...")
        fileIO(f, "save", [])


def setup(bot):
    if soupAvailable:
        check_folders()
        check_files()
        n = TokyoTosho(bot)
        loop = asyncio.get_event_loop()
        loop.create_task(n.rss_checker())
        bot.add_cog(n)
    else:
        raise RuntimeError("You need to run `pip3 install beautifulsoup4`")
