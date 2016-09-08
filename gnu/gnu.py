from discord.ext import commands
import re
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

class GNU:
    """Some unix-like utilities"""

    more_limit = 5

    def __init__(self, bot):
        self.bot = bot
        #self.log = fileIO("data/gnu/log.json", "load")
        self.stdin = ""
        self.stdout = ""

    @commands.command(pass_context=True, name='grep')
    async def grep(self, ctx, *query: str):
        """Print lines that contain a match for a pattern

        Type !grep for more information.
        """

        # display help if no arguments passed
        if not query:
            await self.bot.say("*grep* prints lines that contain a match for a pattern.")
            await self.bot.say("```grep <options> <pattern> <input>```")
            await self.bot.say("```"
                               "\nMatching Options"
                               "\n\t-i      Ignore case distinctions, so that characters that differ only in case match each other."
                               "\n\t-w      Select only those lines containing matches that form whole words."
                               "\n\t-v      Invert the sense of matching, to select non-matching lines."
                               "\n\t-r      Treats search string as a regex pattern; other Matching Options are ignored."
                               "\n\nOutput Options"
                               "\n\t-c      Suppress normal output; instead print a count of matching lines for each input file."
                               "\n\t-n      Prefix each line of output with its line number."
                               "\n\t-m num  Stop reading from input after num matching lines."
                               "\n\nInput"
                               "\n\tURL     If input matches a URL pattern, will attempt to fetch URL content."
                               "\n\t        DOM text elements correspond to 'lines' in this context."
                               "\n\t@chat   If '@chat' is specified as the input, will search in chat log."
                               "\n\t        Logging must be activated in the channel for this to work."
                               "\n\t<input> If none of the previous inputs are detected, remaining text is treated as raw input."
                               "\n\t        Note: Discord chat messages are treated as a single line even if they include linebreaks."
                               "```")
            return

        # parse user command
        search = ""
        input = ""
        option = set()
        option_num = {"m" : 0}
        iterator = query.__iter__()
        for q in iterator:
            if q[0] == '-':
                option.add(q[1:])
                if 'm' in q[:]:
                    option_num['m'] = int(next(iterator))
            elif not search:
                search = q
            else:
                if input:
                    input += ' '
                input += q

        # break up combined options
        for opt in list(option):
            if len(opt) > 1:
                for o in opt[:]:
                    option.add(o)
                option.remove(opt)

        #await self.bot.say("option: " + str(option))
        #await self.bot.say("option_num: " + str(option_num))
        #await self.bot.say("search: " + search)
        #await self.bot.say("input: " + input)

        # prepare search regex
        if 'r' in option:
            search_pattern = re.compile(r"{0}".format(search))
        else:
            re.escape(search)
            if 'w' in option:
                search = "\\b" + search + "\\b"
            if 'v' in option:
                search = "^((?!" + search + ").)*$"
            if 'i' in option:
                search_pattern = re.compile(r"{0}".format(search), re.IGNORECASE)
            else:
                search_pattern = re.compile(r"{0}".format(search))
        #await self.bot.say("`re: " + str(search_pattern) + " - " + search + "`")

        # handle various types of input
        url_pattern = re.compile(
                r'^(?:http|ftp)s?://' # http:// or https://
                r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|' #domain...
                r'localhost|' #localhost...
                r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})' # ...or ip
                r'(?::\d+)?' # optional port
                r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        if url_pattern.match(input):
            #await self.bot.say("Querying `" + input + "`")
            async with aiohttp.ClientSession() as session:
                async with session.get(input) as response:
                    soup = BeautifulSoup(await response.text(), "html.parser")

            texts = soup.findAll(text=True)

            def visible(element):
                if element.parent.name in ['style', 'script', '[document]', 'head', 'title']:
                    return False
                elif re.match('<!--.*-->', str(element)):
                    return False
                return True

            input = filter(visible, texts)
        elif input.lower() == "@chat":
            # handle chat log input
            await self.bot.say("Sorry, @chat is not supported at this time.")
            return
        else:
            input = input.splitlines()

        found = 0
        empty = 0
        for i, line in enumerate(input):
            #await self.bot.say(str(i) + ": " + line)
            if len(line) <= 1:
                empty += 1
                continue # debatable whether this should be here or not

            # do output
            if search_pattern.search(line):
                if 'c' in option:
                    # supress output
                    pass
                elif 'n' in option:
                    await self.bot.say("```{0:>6}: {1}```".format(i, line))
                else:
                    await self.bot.say("```{0}```".format(line))
                found += 1
                if 'm' in option and found >= option_num['m']:
                    break
                if found % GNU.more_limit == 0:
                    await self.bot.say("Type 'more' or 'm' to continue...")
                    answer = await self.bot.wait_for_message(timeout=15,
                                                             author=ctx.message.author)
                    if not answer or answer.content.lower() not in ["more", "m"]:
                        await self.bot.say("Stopping with " + str(found) + " matching lines found.")
                        return

        if found == 1:
            await self.bot.say(str(found) + " matching line found.")
        else:
            await self.bot.say(str(found) + " matching lines found.")
        #await self.bot.say(str(i) + " lines, " + str(empty) + " empty")

def setup(bot):
    if soupAvailable:
        n = GNU(bot)
        bot.add_cog(n)
    else:
        raise RuntimeError("You need to run `pip3 install beautifulsoup4`")
