from discord.ext import commands
import re
import sys
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

    # bot will pause and ask user for input after this number of lines have been sent to channel
    more_limit = 5

    # max character length of a single message to avoid HTTPException: BAD REQUEST (status code: 400)
    max_message_length = 1900

    # using a dict in case command and function are different; key = cmd, value = func
    command_list = {"grep": "grep", "wc": "wc", "tail": "tail", "cat": "cat", "tac": "tac"}

    # used to match url input
    url_pattern = re.compile(
            r'^(?:http|ftp)s?://' # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|' #domain...
            r'localhost|' #localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})' # ...or ip
            r'(?::\d+)?' # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)

    def __init__(self, bot):
        self.bot = bot
        #self.log = fileIO("data/gnu/log.json", "load")
        self.stdin = ""
        self.stdout = ""

    @commands.command(pass_context=True, name='grep')
    async def grep(self, ctx, *args, **kwargs):
        """Print lines that contain a match for a pattern

        Type !grep for more information.
        """

        #await self.bot.say("args: " + str(args) + " : " + str(type(args)))
        #await self.bot.say("kwargs: " + str(kwargs) + " : " + str(type(args)))

        # parse user command
        search = ""
        input = []
        option = set()
        option_num = {"m" : 0}
        pipe = []
        iterator = args.__iter__()
        for arg in iterator:
            if arg == '|':
                while True:
                    try:
                        pipe.append(next(iterator))
                    except:
                        break
            elif arg[0] == '-':
                option.add(arg[1:])
                if 'm' in arg:
                    option_num['m'] = int(next(iterator))
            elif not search:
                search = arg
            else:
                input.append(arg)
        input = " ".join(input)

        # break up combined options
        for opt in list(option):
            if len(opt) > 1:
                for o in opt[:]:
                    option.add(o)
                option.remove(opt)

        # try pipe_in if input is empty
        if not input and "pipe_in" in kwargs:
            input = kwargs["pipe_in"]

        '''
        await self.bot.say("option: " + str(option))
        await self.bot.say("option_num: " + str(option_num))
        await self.bot.say("search: " + search)
        await self.bot.say("input: " + input)
        await self.bot.say("pipe: " + str(pipe))
        '''

        # display help and return if search or input are empty
        if not search or not input:
            await self.bot.say("*grep* prints lines that contain a match for a pattern.")
            await self.bot.say("```grep [options] [pattern] [input]```")
            await self.bot.say("```"
                               "\nMatching Options"
                               "\n\t-i      Ignore case distinctions, so that characters that differ only in case match each other."
                               "\n\t-w      Select only those lines containing matches that form whole words."
                               "\n\t-v      Invert the sense of matching, to select non-matching lines."
                               "\n\t-r      Treats search string as a regex pattern; other Matching Options are ignored."
                               "\n\nInput Options"
                               "\n\t-p      If input is a URL, this will treat the URL content as plain text instead of a DOM"
                               "\n\nOutput Options"
                               "\n\t-c      Suppress normal output; instead print a count of matching lines for each input file."
                               "\n\t-n      Prefix each line of output with its line number."
                               "\n\t-m num  Stop reading from input after num matching lines."
                               "\n\nInput"
                               "\n\tURL     If input matches a URL pattern, bot will fetch URL content as input."
                               "\n\t        By default, DOM will be parsed from URL content and text elements will be treated as \"lines\""
                               "\n\t        If -p option is set, URL content will be treated as plain text."
                               "\n\t@chat   If '@chat' is specified as the input, will search in chat log."
                               "\n\t        Logging must be activated in the channel for this to work."
                               "\n\t<input> If none of the previous inputs are detected, remaining text is treated as input."
                               "\n\t        To preserve whitespace (including newlines), enclose entire input in quotes."
                               "```")
            return

        # prepare search regex
        if 'r' in option:
            search_pattern = re.compile(r"{0}".format(search))
        else:
            search = re.escape(search)
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
        if GNU.url_pattern.match(input):
            #await self.bot.say("Querying `" + input + "`")
            async with aiohttp.ClientSession() as session:
                async with session.get(input) as response:
                    response_text = await response.text()
                    if 'p' in option:
                        # plain text url content
                        input = response_text.splitlines()
                    else:
                        # parse DOM
                        def visible(element):
                            if element.parent.name in ['style', 'script', '[document]', 'head', 'title']:
                                return False
                            elif re.match('<!--.*-->', str(element)):
                                return False
                            return True
                        soup = BeautifulSoup(response_text, "html.parser")
                        texts = soup.findAll(text=True)
                        input = filter(visible, texts)
        elif input.lower() == "@chat":
            # handle chat log input
            await self.bot.say("Sorry, @chat is not supported at this time.")
            return
        else:
            # user input
            input = input.splitlines()

        # do grep
        pipe_out = []
        found = 0
        lines_displayed = 0
        for i, line in enumerate(input):
            #await self.bot.say(str(i) + ": " + line)
            # look for match
            match = search_pattern.search(line)
            if match:
                # record match
                found += 1

                # suppress output if c option set
                if 'c' not in option:
                    # if line is too long, truncate to avoid discord error
                    if len(line) > GNU.max_message_length and not pipe:
                        start = match.start(0)
                        end = match.start(0) + GNU.max_message_length
                        if end > len(line):
                            start -= (end - len(line))
                            end = len(line)
                        line = line[start:end]

                    # flood prevention
                    if lines_displayed > 0 and lines_displayed % GNU.more_limit == 0:
                        await self.bot.say("Type 'more' or 'm' to continue...")
                        answer = await self.bot.wait_for_message(timeout=15, author=ctx.message.author)
                        if not answer or answer.content.lower() not in ["more", "m"]:
                            await self.bot.say("Stopping with " + str(found) + " matching lines found.")
                            return

                    # generate output
                    if 'n' in option:
                        out = "{0:>6}: {1}".format(i, line)
                    else:
                        out = line
                    # print output
                    if pipe:
                        pipe_out.append(out.strip("\n"))
                    else:
                        await self.bot.say("```{0}```".format(out))
                        lines_displayed += 1

                # stop if m option set and limit reached
                if 'm' in option and found >= option_num['m']:
                    break

        # output for c option
        if 'c' in option:
            out = str(found)
            if pipe:
                pipe_out.append(out)
            else:
                await self.bot.say("```{0}```".format(out))

        # print summary
        if not pipe:
            if found == 1:
                await self.bot.say(str(found) + " matching line found.")
            else:
                await self.bot.say(str(found) + " matching lines found.")

        # handle pipe
        if pipe:
            cmd = pipe[0]
            if cmd[0] != ctx.prefix:
                await self.bot.say("```{0}: command prefix missing```".format(cmd))
                return
            elif cmd[1:] not in GNU.command_list.keys():
                await self.bot.say("```{0}: command not found```".format(cmd))
                return
            func = getattr(GNU, GNU.command_list[cmd[1:]])
            if len(pipe) > 1:
                await ctx.invoke(func, *pipe[1:], pipe_in="\n".join(pipe_out))
            else:
                await ctx.invoke(func, pipe_in="\n".join(pipe_out))

    @commands.command(pass_context=True, name='wc')
    async def wc(self, ctx, *args, **kwargs):
        """Count the number of characters, whitespace-separated words, and newlines

        Type !wc for more information.
        """

        # parse user command
        input = []
        option = set()
        pipe = []
        iterator = args.__iter__()
        for arg in iterator:
            if arg == '|':
                while True:
                    try:
                        pipe.append(next(iterator))
                    except:
                        break
            elif arg[0] == '-':
                # assume no combined options, since all options are exclusive
                option.add(arg[1:])
            else:
                input.append(arg)
        input = " ".join(input)

        # try pipe_in if input is empty
        if not input and "pipe_in" in kwargs:
            input = kwargs["pipe_in"]

        # display help if input is empty
        if not input:
            await self.bot.say("*wc* counts the number of characters, whitespace-separated words, and newlines in the given input.")
            await self.bot.say("```wc [option] [input]```")
            await self.bot.say("```"
                               "\nOptions"
                               "\n\t-m      Print only the character counts."
                               "\n\t-w      Print only the word counts."
                               "\n\t-l      Print only the newline counts."
                               "\n\nInput"
                               "\n\tURL     If input matches a URL pattern, will attempt to fetch URL content."
                               "\n\t        URL content is treated as plain text; DOM is never parsed."
                               "\n\t@chat   If '@chat' is specified as the input, will search in chat log."
                               "\n\t        Logging must be activated in the channel for this to work."
                               "\n\t<input> If none of the previous inputs are detected, remaining text is treated as input."
                               "\n\t        To preserve whitespace (including newlines), enclose entire input in quotes."
                               "```")
            return

        # handle various types of input
        if GNU.url_pattern.match(input):
            #await self.bot.say("Querying `" + input + "`")
            async with aiohttp.ClientSession() as session:
                async with session.get(input) as response:
                    input = await response.text()

        elif input.lower() == "@chat":
            # handle chat log input
            await self.bot.say("Sorry, @chat is not supported at this time.")
            return
        else:
            # user input
            pass

        # get counts
        lines = len(input.splitlines())
        words = len(input.split())
        chars = len(input)

        # output
        header = ""
        data = ""
        hr = ": "
        if 'm' in option:
            header = "characters"
            data = str(chars)
        elif 'w' in option:
            header = "words"
            data = str(words)
        elif 'l' in option:
            header = "lines"
            data = str(lines)
        else:
            header = "{0:<10}{1:<10}{2:<10}".format("char", "words", "lines")
            hr = "-" * 30
            data = "{0:<10}{1:<10}{2:<10}".format(chars, words, lines)

        pipe_out = []
        if pipe:
            pipe_out = [header, hr, data]
        else:
            await self.bot.say("```" + "\n".join([header, hr, data]) + "```")

        # handle pipe
        if pipe:
            cmd = pipe[0]
            if cmd[0] != ctx.prefix:
                await self.bot.say("```{0}: command prefix missing```".format(cmd))
                return
            elif cmd[1:] not in GNU.command_list.keys():
                await self.bot.say("```{0}: command not found```".format(cmd))
                return
            func = getattr(GNU, GNU.command_list[cmd[1:]])
            if len(pipe) > 1:
                await ctx.invoke(func, *pipe[1:], pipe_in="\n".join(pipe_out))
            else:
                await ctx.invoke(func, pipe_in="\n".join(pipe_out))

    @commands.command(pass_context=True, name='tail')
    async def tail(self, ctx, *args, **kwargs):
        """Prints the last part (10 lines by default) of input

        Type !tail for more information.
        """

        # parse user command
        input = []
        option = set()
        option_num = ""
        pipe = []
        iterator = args.__iter__()
        for arg in iterator:
            if arg == '|':
                while True:
                    try:
                        pipe.append(next(iterator))
                    except:
                        break
            elif arg[0] == '-':
                option.add(arg[1:])
                if 'n' in arg:
                    option_num = next(iterator)
            else:
                input.append(arg)
        input = " ".join(input)

        # break up combined options
        for opt in list(option):
            if len(opt) > 1:
                for o in opt[:]:
                    option.add(o)
                option.remove(opt)

        # try pipe_in if input is empty
        if not input and "pipe_in" in kwargs:
            input = kwargs["pipe_in"]

        # display help if input is empty
        if not input:
            await self.bot.say("*tail* prints the last part (10 lines by default) of input")
            await self.bot.say("```tail [options] [input]```")
            await self.bot.say("```"
                               "\nOptions"
                               "\n\t-n [+]num   Output the last num lines. However, if num is prefixed with a '+'"
                               "\n\t            start printing with line num from the start of input, instead of from the end."
                               "\n\t-p          If input is a URL, this will treat the URL content as plain text instead of a DOM"
                               "\n\nInput"
                               "\n\tURL     If input matches a URL pattern, will attempt to fetch URL content."
                               "\n\t        By default, DOM will be parsed from URL content and text elements will be treated as \"lines\""
                               "\n\t        If -p option is set, URL content will be treated as plain text."
                               "\n\t@chat   If '@chat' is specified as the input, will search in chat log."
                               "\n\t        Logging must be activated in the channel for this to work."
                               "\n\t<input> If none of the previous inputs are detected, remaining text is treated as input."
                               "\n\t        To preserve whitespace (including newlines), enclose entire input in quotes."
                               "```")
            return

        if GNU.url_pattern.match(input):
            #await self.bot.say("Querying `" + input + "`")
            async with aiohttp.ClientSession() as session:
                async with session.get(input) as response:
                    response_text = await response.text()
                    if 'p' in option:
                        # plain text url content
                        input = response_text.splitlines()
                    else:
                        # parse DOM
                        def visible(element):
                            if element.parent.name in ['style', 'script', '[document]', 'head', 'title']:
                                return False
                            elif re.match('<!--.*-->', str(element)):
                                return False
                            return True
                        soup = BeautifulSoup(response_text, "html.parser")
                        texts = soup.findAll(text=True)
                        input_texts = filter(visible, texts)
                        input = [line for line in input_texts]
        elif input.lower() == "@chat":
            # handle chat log input
            await self.bot.say("Sorry, @chat is not supported at this time.")
            return
        else:
            # user input
            input = input.splitlines()

        # determine range
        if option_num:
            if option_num[0] == '+':
                pos = int(option_num[1:]) - 1
            else:
                pos = len(input) - int(option_num)
        else:
            pos = len(input) - 10
        if pos < 0:
            pos = 0

        # do tail
        pipe_out = []
        lines_displayed = 0
        for line in input[pos:]:
            # truncate messages that are too long
            if len(line) > GNU.max_message_length and not pipe:
                line = line[:(GNU.max_message_length - 12)] + " [TRUNCATED]"
            # flood prevention
            if lines_displayed > 0 and lines_displayed % GNU.more_limit == 0:
                await self.bot.say("Type 'more' or 'm' to continue...")
                answer = await self.bot.wait_for_message(timeout=15, author=ctx.message.author)
                if not answer or answer.content.lower() not in ["more", "m"]:
                    await self.bot.say("Command output stopped.")
                    return
            # display output
            if pipe:
                pipe_out.append(line.strip("\n"))
            else:
                await self.bot.say("```{0}```".format(line))
                lines_displayed += 1

        # handle pipe
        if pipe:
            cmd = pipe[0]
            if cmd[0] != ctx.prefix:
                await self.bot.say("```{0}: command prefix missing```".format(cmd))
                return
            elif cmd[1:] not in GNU.command_list.keys():
                await self.bot.say("```{0}: command not found```".format(cmd))
                return
            func = getattr(GNU, GNU.command_list[cmd[1:]])
            if len(pipe) > 1:
                await ctx.invoke(func, *pipe[1:], pipe_in="\n".join(pipe_out))
            else:
                await ctx.invoke(func, pipe_in="\n".join(pipe_out))


    @commands.command(pass_context=True, name='cat')
    async def cat(self, ctx, *args, **kwargs):
        """Echoes input to output

        Type !cat for more information.
        """

        # parse user command
        input = []
        option = set()
        pipe = []
        iterator = args.__iter__()
        for arg in iterator:
            if arg == '|':
                while True:
                    try:
                        pipe.append(next(iterator))
                    except:
                        break
            elif arg[0] == '-':
                option.add(arg[1:])
            else:
                input.append(arg)
        input = " ".join(input)

        # break up combined options
        for opt in list(option):
            if len(opt) > 1:
                for o in opt[:]:
                    option.add(o)
                option.remove(opt)

        # try pipe_in if input is empty
        if not input and "pipe_in" in kwargs:
            input = kwargs["pipe_in"]

        # display help if input is empty
        if not input:
            await self.bot.say("*cat* echoes the contents of the input")
            await self.bot.say("```cat [options] [input]```")
            await self.bot.say("```"
                               "\nOptions"
                               "\n\t-b      Number all nonempty output lines, starting with 1."
                               "\n\t-n      Number all output lines, starting with 1. This option is ignored if -b is in effect."
                               "\n\t-s      Suppress repeated adjacent blank lines; output just one empty line instead of several."
                               "\n\t-p      If input is a URL, this will treat the URL content as plain text instead of a DOM"
                               "\n\nInput"
                               "\n\tURL     If input matches a URL pattern, will attempt to fetch URL content."
                               "\n\t        By default, DOM will be parsed from URL content and text elements will be treated as \"lines\""
                               "\n\t        If -p option is set, URL content will be treated as plain text."
                               "\n\t@chat   If '@chat' is specified as the input, will search in chat log."
                               "\n\t        Logging must be activated in the channel for this to work."
                               "\n\t<input> If none of the previous inputs are detected, remaining text is treated as input."
                               "\n\t        To preserve whitespace (including newlines), enclose entire input in quotes."
                               "```")
            return

        if GNU.url_pattern.match(input):
            #await self.bot.say("Querying `" + input + "`")
            async with aiohttp.ClientSession() as session:
                async with session.get(input) as response:
                    response_text = await response.text()
                    if 'p' in option:
                        # plain text url content
                        input = response_text.splitlines()
                    else:
                        # parse DOM
                        def visible(element):
                            if element.parent.name in ['style', 'script', '[document]', 'head', 'title']:
                                return False
                            elif re.match('<!--.*-->', str(element)):
                                return False
                            return True
                        soup = BeautifulSoup(response_text, "html.parser")
                        texts = soup.findAll(text=True)
                        input = filter(visible, texts)
        elif input.lower() == "@chat":
            # handle chat log input
            await self.bot.say("Sorry, @chat is not supported at this time.")
            return
        else:
            # user input
            input = input.splitlines()

        # do cat
        pipe_out = []
        prev_empty = False
        line_b = 0
        line_n = 0
        lines_displayed = 0
        for line in input:
            #await self.bot.say(str(i) + ": " + line)
            # skip line if 's' is set, previous line was empty, and this line is empty
            if 's' in option and prev_empty and not line.strip():
                continue
            # increment line counters
            line_n += 1
            if line.strip():
                line_b += 1
            # set output
            if 'b' in option and line.strip():
                out = "{0:>6}: {1}".format(line_b, line)
            elif 'n' in option:
                out = "{0:>6}: {1}".format(line_n, line)
            else:
                out = line
            # truncate messages that are too long
            if len(out) > GNU.max_message_length and not pipe:
                out = out[:(GNU.max_message_length - 12)] + " [TRUNCATED]"
            # flood prevention
            if lines_displayed > 0 and lines_displayed % GNU.more_limit == 0:
                await self.bot.say("Type 'more' or 'm' to continue...")
                answer = await self.bot.wait_for_message(timeout=15, author=ctx.message.author)
                if not answer or answer.content.lower() not in ["more", "m"]:
                    await self.bot.say("Command output stopped.")
                    return
            # display output
            if pipe:
                pipe_out.append(out.strip("\n"))
            else:
                await self.bot.say("```{0}```".format(out))
                lines_displayed += 1
            # set prev_empty
            if not line.strip():
                prev_empty = True
            else:
                prev_empty = False

        # let user know end of file has been reached (maybe superfluous)
        if not pipe:
            #await self.bot.say("Done.")
            pass

        # handle pipe
        if pipe:
            cmd = pipe[0]
            if cmd[0] != ctx.prefix:
                await self.bot.say("```{0}: command prefix missing```".format(cmd))
                return
            elif cmd[1:] not in GNU.command_list.keys():
                await self.bot.say("```{0}: command not found```".format(cmd))
                return
            func = getattr(GNU, GNU.command_list[cmd[1:]])
            if len(pipe) > 1:
                await ctx.invoke(func, *pipe[1:], pipe_in="\n".join(pipe_out))
            else:
                await ctx.invoke(func, pipe_in="\n".join(pipe_out))


    @commands.command(pass_context=True, name='tac')
    async def tac(self, ctx, *args, **kwargs):
        """Echoes input to output in reverse by line or user specified separator

        Type !tac for more information.
        """

        # parse user command
        input = []
        option = set()
        option_sep = ""
        pipe = []
        iterator = args.__iter__()
        for arg in iterator:
            if arg == '|':
                while True:
                    try:
                        pipe.append(next(iterator))
                    except:
                        break
            elif arg[0] == '-':
                option.add(arg[1:])
                if 's' in arg:
                    option_sep = next(iterator)
            else:
                input.append(arg)
        input = " ".join(input)

        # break up combined options
        for opt in list(option):
            if len(opt) > 1:
                for o in opt[:]:
                    option.add(o)
                option.remove(opt)

        # try pipe_in if input is empty
        if not input and "pipe_in" in kwargs:
            input = kwargs["pipe_in"]

        # display help if input is empty
        if not input:
            await self.bot.say("*tac* echoes input to output in reverse by line or user specified separator")
            await self.bot.say("```tac [options] [input]```")
            await self.bot.say("```"
                               "\nOptions"
                               "\n\t-s sep  Use \"sep\" as the record separator, instead of newline."
                               "\n\t-r      Treat the separator string as a regular expression."
                               "\n\t-p      If input is a URL, this will treat the URL content as plain text instead of a DOM"
                               "\n\nInput"
                               "\n\tURL     If input matches a URL pattern, will attempt to fetch URL content."
                               "\n\t        By default, DOM will be parsed from URL content and text elements will be treated as \"lines\""
                               "\n\t        If -p option is set, URL content will be treated as plain text."
                               "\n\t@chat   If '@chat' is specified as the input, will search in chat log."
                               "\n\t        Logging must be activated in the channel for this to work."
                               "\n\t<input> If none of the previous inputs are detected, remaining text is treated as input."
                               "\n\t        To preserve whitespace (including newlines), enclose entire input in quotes."
                               "```")
            return

        if GNU.url_pattern.match(input):
            #await self.bot.say("Querying `" + input + "`")
            async with aiohttp.ClientSession() as session:
                async with session.get(input) as response:
                    response_text = await response.text()
                    if 'p' in option:
                        # plain text url content
                        input = response_text
                    else:
                        # parse DOM
                        def visible(element):
                            if element.parent.name in ['style', 'script', '[document]', 'head', 'title']:
                                return False
                            elif re.match('<!--.*-->', str(element)):
                                return False
                            return True
                        soup = BeautifulSoup(response_text, "html.parser")
                        texts = soup.findAll(text=True)
                        input_texts = filter(visible, texts)
                        input = "\n".join([line for line in input_texts])
        elif input.lower() == "@chat":
            # handle chat log input
            await self.bot.say("Sorry, @chat is not supported at this time.")
            return
        else:
            # user input
            pass

        # split input
        if option_sep:
            if 'r' in option:
                separator = re.compile(r"{0}".format(option_sep))
                input = separator.split(input)
            else:
                input = input.split(option_sep)
        else:
            input = input.splitlines()

        # do cat (on reversed string)
        pipe_out = []
        lines_displayed = 0
        for line in reversed(input):
            #await self.bot.say(str(i) + ": " + line)
            # truncate messages that are too long
            if len(line) > GNU.max_message_length and not pipe:
                line = line[:(GNU.max_message_length - 12)] + " [TRUNCATED]"
            # flood prevention
            if lines_displayed > 0 and lines_displayed % GNU.more_limit == 0:
                await self.bot.say("Type 'more' or 'm' to continue...")
                answer = await self.bot.wait_for_message(timeout=15, author=ctx.message.author)
                if not answer or answer.content.lower() not in ["more", "m"]:
                    await self.bot.say("Command output stopped.")
                    return
            # display output
            if pipe:
                pipe_out.append(line.strip("\n"))
            else:
                await self.bot.say("```{0}```".format(line))
                lines_displayed += 1

        # let user know end of file has been reached (maybe superfluous)
        if not pipe:
            #await self.bot.say("Done.")
            pass

        # handle pipe
        if pipe:
            cmd = pipe[0]
            if cmd[0] != ctx.prefix:
                await self.bot.say("```{0}: command prefix missing```".format(cmd))
                return
            elif cmd[1:] not in GNU.command_list.keys():
                await self.bot.say("```{0}: command not found```".format(cmd))
                return
            func = getattr(GNU, GNU.command_list[cmd[1:]])
            if len(pipe) > 1:
                await ctx.invoke(func, *pipe[1:], pipe_in="\n".join(pipe_out))
            else:
                await ctx.invoke(func, pipe_in="\n".join(pipe_out))



def setup(bot):
    if soupAvailable:
        n = GNU(bot)
        bot.add_cog(n)
    else:
        raise RuntimeError("You need to run `pip3 install beautifulsoup4`")
