from discord.ext import commands
from cogs.utils.chat_formatting import escape_mass_mentions
from cogs.utils.dataIO import dataIO
from cogs.utils import checks
import os
import logging
import asyncio
import aiohttp
import re
import js2py
from datetime import datetime

try:
    from urlparse import urlparse
except ImportError:
    from urllib.parse import urlparse

try:  # check if BeautifulSoup4 is installed
    from bs4 import BeautifulSoup
    soupAvailable = True
except:
    soupAvailable = False


class TokyoTosho:
    """TokyoTosho search and RSS alerts"""

    default_config = {"check_interval": 120,
                      "timeout": 8,
                      "items_per_message": 8,
                      "comment_length": 120,
                      "urls": ["https://www.tokyotosho.info/",
                               "http://tokyotosho.se/",
                               "http://tokyo-tosho.net/"],
                      "ignore": []}

    base_dir = os.path.join("data", "tokyotosho")
    config_path = os.path.join(base_dir, "config.json")
    alert_path = os.path.join(base_dir, "alerts.json")

    def __init__(self, bot):
        self.bot = bot

        self.alerts = dataIO.load_json(TokyoTosho.alert_path)
        self.config = dataIO.load_json(TokyoTosho.config_path)

        self.cats = {"anime": 1, "music": 2, "manga": 3, "hentai": 4, "other": 5, "raws": 7, "drama": 8,
                     "music-video": 9, "non-english": 10, "batch": 11, "hentai-anime": 12, "hentai-manga": 13,
                     "hentai-games": 14, "jav": 15}
        self.pubdate_format = "%a, %d %b %Y %H:%M:%S %Z"

    def _get_config(self, param):
        if param in self.config:
            return self.config[param]
        elif param in self.default_config:
            return self.default_config[param]
        else:
            return None

    async def _get_soup(self, **kwargs):
        """Get soup object from tokyotosho
        :kwarg channel_id:   channel id
        :kwarg query:        page or query
        :return:             {"soup": SoupObject, "url": SourceURL}
                             or None if failed to get soup
        """

        soup = None
        url = None
        channel_obj = None
        if "channel_id" in kwargs:
            channel_obj = self.bot.get_channel(kwargs["channel_id"])

        # Try to get soup object from tokyotosho
        for url in self._get_config("urls"):
            if "query" in kwargs:
                url += kwargs["query"]
            try:
                async with CloudflareScraper() as session:
                    async with session.get(url, timeout=self._get_config("timeout")) as response:
                        soup = BeautifulSoup(await response.text(), "html.parser")
                        break
            except Exception as e:
                if channel_obj is not None:
                    await self.bot.send_message(
                        channel_obj,
                        "`{0}` failed with error: `{1}`. Trying next URL...".format(url, e))

        # Check data
        if not soup:
            if channel_obj is not None:
                await self.bot.send_message(channel_obj, "TokyoTosho seems to be down.")
            return None

        return {"soup": soup, "url": url}

    @commands.group(pass_context=True)
    async def tt(self, ctx):
        """TokyoTosho search and RSS alerts"""

        if ctx.invoked_subcommand is None:
            await self.bot.say("```"
                               "\nTokyoTosho search and RSS alerts"
                               "\n\nCommands:"
                               "\n\tsearch  Search TokyoTosho and display results"
                               "\n\tadd     Add an RSS alert for new torrents on TokyoTosho"
                               "\n\tlist    List current RSS alerts"
                               "\n\tcheck   Check current RSS alerts against RSS feed"
                               "\n\tremove  Remove an RSS alert"
                               "\n\tcats    Show valid categories"
                               "\n\tset     Set various options"
                               "\n\nType !help command for more info on a command."
                               "```")

    @tt.command(name='set')
    @checks.is_owner()
    async def set_config(self, *args: str):
        """Set config options

        Usage: set [option] [value]

        Examples:
            set check_interval 300
            set items_per_message 5
            set comment_length 80
            set ignore jav other
        """

        # Echo current config if no args
        if not args:
            await self.bot.say("Current config:\n```{0}```".format(self.sanitize(str(self.config), "box")))
            return

        # Make sure key is valid
        key = args[0]
        if key not in self.default_config:
            await self.bot.say("Unknown option")
            return

        # Get value
        if len(args) == 1:
            # Echo current option if no value
            value = self._get_config(key)
            if isinstance(value, list):
                value = " ".join(value)
            await self.bot.say("Current {0}: `{1}`".format(key, self.sanitize(str(value), "inline")))
            return
        elif key in ("check_interval", "timeout", "items_per_message", "comment_length"):
            value = int(args[1])
        elif key in ("ignore", "urls"):
            value = list(args[1:])
        else:
            await self.bot.say("Unknown option")
            return

        # Save config
        self.config[key] = value
        dataIO.save_json(self.config_path, self.config)

        # Echo new option and value
        if isinstance(value, list):
            value = " ".join(value)
        await self.bot.say("{0} is now `{1}`".format(key, self.sanitize(str(value), "inline")))

        return

    @tt.command(pass_context=True, name='search', aliases=['s'])
    async def search_torrents(self, ctx, *args: str):
        """Search TokyoTosho and display results

        Usage: search [terms] [-terms] [#categories]

        Examples:
            search horriblesubs madoka 1080
            search madoka -horriblesubs -dub
            search madoka #music
        """

        # Build query
        terms = []
        cat = ''
        for term in args:
            if term[0] == '#':
                if cat:
                    await self.bot.say("Only 1 category can be specified for search.")
                    return
                if term[1:].lower() not in self.cats:
                    await self.bot.say(term[1:] + " is not a valid category. Type !tt cats to show valid categories.")
                    return
                cat = str(self.cats[term[1:].lower()])
            else:
                terms.append(term)
        q = ''
        if terms and cat:
            q = "search.php?terms=" + '+'.join(terms) + "&type=" + cat
        elif terms:
            q = "search.php?terms=" + '+'.join(terms)
        elif cat:
            q = "index.php?cat=" + cat

        # Get soup
        result = await self._get_soup(channel_id=ctx.message.channel.id, query=q)
        if not result or result["soup"] is None:
            return
        soup = result["soup"]
        url = result["url"]

        # Parse soup
        table = soup.find("table", attrs={"class": "listing"})
        rows = table.find_all("tr", class_=True)
        result = []
        count = 0
        item = ''
        for row in rows:
            td_link = row.find("td", attrs={"class": "desc-top"})
            td_desc = row.find("td", attrs={"class": "desc-bot"})
            if td_link:
                # Get category
                cat_url = row.find("a").get("href")
                cat_num = int(cat_url[cat_url.find('=')+1:])
                cat_name = list(self.cats.keys())[list(self.cats.values()).index(cat_num)]
                # Skip ignored categories
                if cat_name in self._get_config("ignore"):
                    continue
                # Get name and link
                a_link = td_link.find_all("a")[-1]
                item = "**{0}** :: {1}\n".format(a_link.get_text(), a_link.get("href"))
            elif td_desc:
                # Skip ignored categories
                if cat_name in self._get_config("ignore"):
                    continue
                # Get description
                desc = td_desc.get_text()
                if len(desc) > self._get_config("comment_length"):
                    desc = desc[:self._get_config("comment_length")] + "..."
                # Remove links from comment
                desc = desc.replace("http", "h\*\*p")
                item += "[{0}] {1}\n".format(cat_name.capitalize(), desc)
                result.append(item)
                count += 1

        try:
            summary = table.find_next_sibling("p")
            result.append("*{0}*".format(summary.get_text()))
        except:
            # No summary if search terms not specified
            pass

        # Display results in channel
        await self.bot.say("{0} results from `{1}`".format(count, self.sanitize(url, "plain"), "inline"))
        step = self._get_config("items_per_message")
        messages = [result[i:i+step] for i in range(0, len(result), step)]
        for i, message in enumerate(messages):
            if i > 0:
                await self.bot.say("Type 'more' or 'm' to continue...")
                answer = await self.bot.wait_for_message(timeout=15, author=ctx.message.author)
                if not answer or answer.content.lower() not in ["more", "m"]:
                    await self.bot.say("Command output stopped.")
                    return
            # Respect 2000 character limit per message
            buffer = ""
            for m in message:
                if len(buffer) + len(m) >= 1900:
                    await self.bot.say(buffer)
                    buffer = ""
                buffer += m
            if buffer:
                await self.bot.say(buffer)

    @tt.command(pass_context=True, name='add', aliases=['a'])
    async def add_alert(self, ctx, *args: str):
        """Add an RSS alert for new torrents on TokyoTosho

        Usage: add [terms] [-terms] [#categories]

        Examples:
            add horriblesubs madoka 1080
            add madoka -horriblesubs -dub
            add madoka #anime #music
        """

        if not args:
            await self.bot.say("Type {0}help tt add".format(ctx.prefix))
            return

        # build alert
        include = set()
        exclude = set()
        cat = set()
        for term in args:
            if term[0] == '#':
                if term[1:].lower() in self.cats:
                    cat.add(str(self.cats[term[1:].lower()]))
                else:
                    await self.bot.say("`{0}` is not a valid category. Type {0}tt cats to show valid categories."
                                       .format(term[1:], ctx.prefix))
                    return
            elif term[0] == '-':
                exclude.add(term)
            else:
                include.add(term)

        # check if alert already exists
        for i, s in enumerate(self.alerts):
            # check if include + exclude + cat sets match
            tmp_include = set(s["INCLUDE"])
            tmp_exclude = set(s["EXCLUDE"])
            tmp_cat = set(s["CATEGORY"])
            if include == tmp_include and exclude == tmp_exclude and cat == tmp_cat:
                if ctx.message.channel.id in s["CHANNELS"]:
                    await self.bot.say("Alert already exists in this channel. Type !tt list to see current alerts.")
                    return
                else:
                    self.alerts[i]["CHANNELS"].append(ctx.message.channel.id)
                    dataIO.save_json(self.alert_path, self.alerts)
                    category = [k for k, v in self.cats.items() if str(v) in cat]
                    await self.bot.say(
                        "Alert has been added to this channel with the following options:\n"
                        "```"
                        "\n{0:<13}: {1}".format("Search Terms", self.sanitize(" ".join(include), "box")) +
                        "\n{0:<13}: {1}".format("Exclude Terms", self.sanitize(" ".join(exclude), "box")) +
                        "\n{0:<13}: {1}".format("Categories", self.sanitize(" ".join(category), "box")) +
                        "```"
                    )
                    return

        # add alert
        self.alerts.append({"LAST_PUBDATE": "",
                            "CHANNELS": [ctx.message.channel.id],
                            "INCLUDE": list(include),
                            "EXCLUDE": list(exclude),
                            "CATEGORY": list(cat)})
        dataIO.save_json(self.alert_path, self.alerts)
        category = [k for k, v in self.cats.items() if str(v) in cat]
        await self.bot.say(
            "Alert has been added to this channel with the following options:\n"
            "```"
            "\n{0:<13}: {1}".format("Search Terms", self.sanitize(" ".join(include), "box")) +
            "\n{0:<13}: {1}".format("Exclude Terms", self.sanitize(" ".join(exclude), "box")) +
            "\n{0:<13}: {1}".format("Categories", self.sanitize(" ".join(category), "box")) +
            "```"
        )
        return

    @tt.command(pass_context=True, name='remove', aliases=['r'])
    async def remove_alert(self, ctx, *args: str):
        """Remove an RSS alert

        Usage: remove [terms] [-terms] [#categories]
        """

        if not args:
            await self.bot.say("Type {0}help tt remove".format(ctx.prefix))
            return

        # build query
        include = set()
        exclude = set()
        cat = set()
        for term in args:
            if term[0] == '#':
                if term[1:].lower() in self.cats:
                    cat.add(str(self.cats[term[1:].lower()]))
                else:
                    await self.bot.say(term[1:] + " is not a valid category. Type !tt cats to show valid categories.")
                    return
            elif term[0] == '-':
                exclude.add(term)
            else:
                include.add(term)

        # look for alert and remove if found
        count = 0
        for i, alert in enumerate(self.alerts):
            # check if include + exclude + category sets match
            tmp_include = set(alert["INCLUDE"])
            tmp_exclude = set(alert["EXCLUDE"])
            tmp_cat = set(alert["CATEGORY"])
            if include == tmp_include and exclude == tmp_exclude and cat == tmp_cat:
                if ctx.message.channel.id in alert["CHANNELS"]:
                    count += 1
                    if len(alert["CHANNELS"]) == 1:
                        self.alerts.remove(alert)
                        await self.bot.say("Alert has been removed from this channel.")
                    else:
                        self.alerts[i]["CHANNELS"].remove(ctx.message.channel.id)
                        await self.bot.say("Alert has been removed from this channel.")

        if not count:
            await self.bot.say("Alert not found.")

        # update file
        dataIO.save_json(self.alert_path, self.alerts)

    @tt.command(pass_context=True, name='list', aliases=['l'])
    async def show_alerts(self, ctx):
        """List current RSS alerts

        Usage: list
        """

        count = 0
        for i, alert in enumerate(self.alerts):
            if ctx.message.channel.id in alert["CHANNELS"]:
                category = ['#'+k for k, v in self.cats.items() if str(v) in alert["CATEGORY"]]
                await self.bot.say("```{0} {1} {2}```".format(
                    self.sanitize(" ".join(alert["INCLUDE"]), "box"),
                    self.sanitize(" ".join(alert["EXCLUDE"]), "box"),
                    self.sanitize(" ".join(category), "box")
                ))
                count += 1

        if not count:
            await self.bot.say("No alerts found for this channel.")

    @tt.command(pass_context=True, name='check', aliases=['c'])
    async def check_alerts(self, ctx):
        """Check current RSS alerts against RSS feed

        Usage: check
        """

        # Get rss
        result = await self._get_soup(channel_id=ctx.message.channel.id, query="rss.php")
        if not result or result["soup"] is None:
            return
        soup = result["soup"]

        count = 0
        for i, alert in enumerate(self.alerts):
            msg = []
            if ctx.message.channel.id in alert["CHANNELS"]:
                count += 1
                category = ['#'+k for k, v in self.cats.items() if str(v) in alert["CATEGORY"]]
                msg.append("```{0} {1} {2}```".format(
                    self.sanitize(" ".join(alert["INCLUDE"]), "box"),
                    self.sanitize(" ".join(alert["EXCLUDE"]), "box"),
                    self.sanitize(" ".join(category), "box")
                ))
                include = set(alert["INCLUDE"])
                exclude = set([term[1:] for term in alert["EXCLUDE"]])
                cat = set([k for k, v in self.cats.items() if str(v) in alert["CATEGORY"]])

                # Parse RSS and display result
                items = soup.find_all("item")
                match = False
                found = False
                for item in items:
                    match = True
                    title = item.find("title").get_text()
                    # Skip ignored categories
                    if item.find("category").get_text().lower() in self._get_config("ignore"):
                        continue
                    # Skip items that do not include all required search terms
                    for term in include:
                        if term.lower() not in title.lower():
                            match = False
                            break
                    if not match:
                        continue
                    # Skip items that include any of the excluded search terms
                    for term in exclude:
                        if term.lower() in title.lower():
                            match = False
                            break
                    if not match:
                        continue
                    # Skip items that do not include at least one of the categories
                    for term in cat:
                        match = False
                        if term.lower() == item.find("category").get_text().lower():
                            match = True
                            break
                    if not match:
                        continue
                    # Set found flag
                    found = True
                    # Get item message
                    description = item.find("description").get_text().split("<br />")
                    description = " | ".join([description[1], description[2], description[4]])
                    if len(description) > self._get_config("comment_length")-30:
                        description = description[:self._get_config("comment_length")-27] + "..."
                    msg.append("**{0}** :: {1}\n{2} | {3} | {4}".format(
                        title,
                        item.find("link").get_text(),
                        item.find("pubdate").get_text(),
                        item.find("category").get_text(),
                        description
                    ))
                # Print results
                if not found:
                    msg.append("No items found for this alert.")
                # Respect 2000 character limit per message
                buffer = ""
                for m in msg:
                    if len(buffer) + len(m) >= 1900:
                        await self.bot.say(buffer)
                        await asyncio.sleep(1)
                        buffer = ""
                    buffer += "\n" + m
                if buffer:
                    await self.bot.say(buffer)
        if not count:
            await self.bot.say("No alerts found for this channel.")

    @tt.command(name='cats')
    async def show_cats(self):
        """Show valid categories

        Usage: cats
        """
        cats = [cat for cat in self.cats.keys() if cat not in self._get_config("ignore")]
        await self.bot.say(" ".join(cats))

    async def check_rss(self):
        """Check RSS feed for new items"""
        while self == self.bot.get_cog("TokyoTosho"):
            # Get rss
            result = await self._get_soup(query="rss.php")
            if not result or result["soup"] is None:
                await asyncio.sleep(self._get_config("check_interval"))
                continue
            soup = result["soup"]
            items = soup.find_all("item")

            # Iterate through alerts
            for i, alert in enumerate(self.alerts):
                include = set(alert["INCLUDE"])
                exclude = set([term[1:] for term in alert["EXCLUDE"]])
                cat = set([k for k, v in self.cats.items() if str(v) in alert["CATEGORY"]])
                last_pubdate = alert["LAST_PUBDATE"]

                # Find matches
                new_pubdate = ""
                count = 0
                msg = []
                for item in items:
                    match = True
                    # Skip ignored categories
                    if item.find("category").get_text().lower() in self._get_config("ignore"):
                        continue

                    # Skip items that are older than the last alerted item (assume rss is sorted by date, newest first)
                    pubdate = item.find("pubdate").get_text()
                    if last_pubdate and datetime.strptime(last_pubdate, self.pubdate_format) >= datetime.strptime(pubdate, self.pubdate_format):
                        break

                    # Skip items that do not include all required search terms
                    title = item.find("title").get_text()
                    for term in include:
                        if term.lower() not in title.lower():
                            match = False
                            break
                    if not match:
                        continue

                    # Skip items that include any of the excluded search terms
                    for term in exclude:
                        if term.lower() in title.lower():
                            match = False
                            break
                    if not match:
                        continue

                    # Skip items that do not include at least one of the categories
                    for term in cat:
                        match = False
                        if term.lower() == item.find("category").get_text().lower():
                            match = True
                            break
                    if not match:
                        continue

                    # Get item message
                    description = item.find("description").get_text().split("<br />")
                    description = " | ".join([description[1], description[2], description[4]])
                    if len(description) > self._get_config("comment_length")-30:
                        description = description[:self._get_config("comment_length")-27] + "..."
                    msg.append("**{0}** :: {1}\n{2} | {3} | {4}".format(
                        title,
                        item.find("link").get_text(),
                        item.find("pubdate").get_text(),
                        item.find("category").get_text(),
                        description
                    ))

                    # Update pubdate
                    if not new_pubdate:
                        new_pubdate = pubdate
                    count += 1

                # Alert channels
                if msg:
                    # Split items into chunks of 5 if necessary
                    for channel in alert["CHANNELS"]:
                        channel_obj = self.bot.get_channel(channel)
                        if channel_obj and channel_obj.permissions_for(channel_obj.server.me).send_messages:
                            await self.bot.send_message(channel_obj, "TokyoTosho RSS alert:")
                            # Respect 2000 character limit per message
                            buffer = ""
                            for m in msg:
                                if len(buffer) + len(m) >= 1900:
                                    await self.bot.send_message(channel_obj, buffer)
                                    await asyncio.sleep(1)
                                    buffer = ""
                                buffer += "\n" + m
                            if buffer:
                                await self.bot.send_message(channel_obj, buffer)

                # Update LAST_PUBDATE
                if new_pubdate:
                    self.alerts[i]["LAST_PUBDATE"] = new_pubdate
                    dataIO.save_json(self.alert_path, self.alerts)

                await asyncio.sleep(0.5)

            await asyncio.sleep(self._get_config("check_interval"))

        # end while loop
    # end check_rss

    @staticmethod
    def sanitize(s: str, type: str) -> str:
        """Sanitize discord message"""
        if type == "plain":
            return escape_mass_mentions(s)
        elif type == "inline":
            return s.replace("`", "'")
        elif type == "box":
            return s.replace("```", "'''")


class CloudflareScraper(aiohttp.ClientSession):
    """ Credit https://github.com/pavlodvornikov/aiocfscrape """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @asyncio.coroutine
    def _request(self, method, url, *args, allow_403=False, **kwargs):
        resp = yield from super()._request(method, url, *args, **kwargs)

        # Check if Cloudflare anti-bot is on
        if resp.status == 503 and resp.headers.get("Server") == "cloudflare-nginx":
            return (yield from self.solve_cf_challenge(resp, **kwargs))

        elif resp.status == 403 and resp.headers.get("Server") == "cloudflare-nginx" and not allow_403:
            resp.close()
            raise aiohttp.HttpProcessingError(message='CloudFlare returned HTTP 403. Your IP could be banned on CF '
                                                      'or reCAPTCHA appeared. This error can be disabled with '
                                                      'allow_403=True flag in request parameters e.g. '
                                                      'session.get(url, allow_403=True).', headers=resp.headers)

        # Otherwise, no Cloudflare anti-bot detected
        return resp

    @asyncio.coroutine
    def solve_cf_challenge(self, resp, **kwargs):
        # https://pypi.python.org/pypi/cfscrape has been used as the solution.
        # The code below (with changes) has been inherited from mentioned lib.

        yield from asyncio.sleep(5, loop=self._loop)  # Cloudflare requires a delay before solving the challenge

        body = yield from resp.text()
        parsed_url = urlparse(resp.url)
        domain = parsed_url.netloc
        submit_url = '{}://{}/cdn-cgi/l/chk_jschl'.format(parsed_url.scheme, domain)

        params = kwargs.setdefault("params", {})
        headers = kwargs.setdefault("headers", {})
        headers["Referer"] = resp.url

        try:
            params["jschl_vc"] = re.search(r'name="jschl_vc" value="(\w+)"', body).group(1)
            params["pass"] = re.search(r'name="pass" value="(.+?)"', body).group(1)

            # Extract the arithmetic operation
            js = self.extract_js(body)

        except Exception:
            # Something is wrong with the page.
            # This may indicate Cloudflare has changed their anti-bot
            # technique. If you see this and are running the latest version,
            # please open a GitHub issue so I can update the code accordingly.
            logging.error("Unable to parse Cloudflare anti-bot page. "
                          "Please submit an issue to https://github.com/ritsu/RitsuCogs/issues")
            raise

        # Safely evaluate the Javascript expression
        js = js.replace('return', '')
        params["jschl_answer"] = str(int(js2py.eval_js(js)) + len(domain))
        resp.close()
        return (yield from self._request('GET', submit_url, **kwargs))

    def extract_js(self, body):
        js = re.search(r"setTimeout\(function\(\){\s+(var "
                       "s,t,o,p,b,r,e,a,k,i,n,g,f.+?\r?\n[\s\S]+?a\.value =.+?)\r?\n", body).group(1)
        js = re.sub(r"a\.value = (parseInt\(.+?\)).+", r"\1", js)
        js = re.sub(r"\s{3,}[a-z](?: = |\.).+", "", js)

        # Strip characters that could be used to exit the string context
        # These characters are not currently used in Cloudflare's arithmetic snippet
        js = re.sub(r"[\n\\']", "", js)

        return js.replace("parseInt", "return parseInt")


def check_folders():
    if not os.path.exists(TokyoTosho.base_dir):
        print("Creating " + TokyoTosho.base_dir + " folder...")
        os.makedirs(TokyoTosho.base_dir)


def check_files():
    if not dataIO.is_valid_json(TokyoTosho.config_path):
        print("Creating default " + TokyoTosho.config_path + " ...")
        dataIO.save_json(TokyoTosho.config_path, TokyoTosho.default_config)
    if not dataIO.is_valid_json(TokyoTosho.alert_path):
        print("Creating empty " + TokyoTosho.alert_path + " ...")
        dataIO.save_json(TokyoTosho.alert_path, [])


def setup(bot):
    if soupAvailable:
        check_folders()
        check_files()
        n = TokyoTosho(bot)
        bot.loop.create_task(n.check_rss())
        bot.add_cog(n)
    else:
        raise RuntimeError("You need to run `pip3 install beautifulsoup4`")
