from discord.ext import commands
import re
import aiohttp

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
    command_list = {"grep": "grep", "wc": "wc", "tail": "tail", "cat": "cat", "tac": "tac", "sed": "sed"}

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
        dom_source = False
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
                        dom_source = True
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
            # strip extra whitespace and newlines from dom sources
            if dom_source:
                line = line.strip()

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
                        pipe_out.append(out)
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
        dom_source = False
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
                        dom_source = True
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
            await self.bot.say("*tail* prints the last part (10 lines by default) of input.")
            await self.bot.say("```tail [options] [input]```")
            await self.bot.say("```"
                               "\nOptions"
                               "\n\t-n [+]num   Output the last num lines. However, if num is prefixed with a '+',"
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

        dom_source = False
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
                        dom_source = True
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
            # strip extra whitespace and newlines from dom sources
            if dom_source:
                line = line.strip()

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
                pipe_out.append(line)
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
            await self.bot.say("*cat* echoes the contents of the input.")
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

        dom_source = False
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
                        dom_source = True
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
            # strip extra whitespace and newlines from dom sources
            if dom_source:
                line = line.strip()

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
                pipe_out.append(out)
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
            await self.bot.say("*tac* echoes input to output in reverse by line or user specified separator.")
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

        dom_source = False
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
                        dom_source = True
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
            # strip extra whitespace and newlines from dom sources
            if dom_source:
                line = line.strip()

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
                pipe_out.append(line)
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

    @commands.command(pass_context=True, name='sed')
    async def sed(self, ctx, *args, **kwargs):
        """A simple stream editor

        Type !sed for more information.
        """

        if not args:
            await self.bot.say("*sed* is a simple stream editor.")
            await self.bot.say("```sed [options] [script] [input]```")
            await self.bot.say("```"
                               "\nOptions"
                               "\n\t-g      Process entire input as a single string, rather than line by line."
                               "\n\t-n      Disable automatic printing; only produce output when explicitly told to."
                               "\n\nScript Address"
                               "\n\t/.*/    Returns lines that match the regular expression."
                               "\n\tA       Returns line number A."
                               "\n\tA,B     Returns lines from A to B."
                               "\n\tA~N     Returns every Nth line, starting from A"
                               "\n\nScript Command"
                               "\n\ta...    Append after each line."
                               "\n\tc...    Change lines with new line."
                               "\n\td       Delete lines."
                               "\n\ti...    Insert before each line."
                               "\n\tp       Print line."
                               "\n\ts/././  Substitute with regular expression pattern."
                               "\n\t=       Print line number."
                               "\n\nScript Pattern Flag"
                               "\n\t/I      Ignore case"
                               "\n\t/p      Print (mostly used when -n option is active)"
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

        # parse input
        option = set()
        script = ""
        input = []
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
            elif not script:
                script = arg
            else:
                input.append(arg)
        input = " ".join(input)

        if not script:
            await self.bot.say("Command not found.")
            return

        # try pipe_in if input is empty
        if not input and "pipe_in" in kwargs:
            input = kwargs["pipe_in"]

        if not input:
            await self.bot.say("Input not found.")
            return

        # get address
        address_type = ""
        address = ""
        if script[0] == '/':
            address_type = "regex"
            match = re.compile(r"^/(.*?)/(?<!\\/)i?", re.IGNORECASE).match(script)
            # get regex for address range
            if match.group(0)[-1].lower() == 'i':
                address = re.compile(r"{0}".format(match.group(1)), re.IGNORECASE)
            else:
                address = re.compile(r"{0}".format(match.group(1)))
            # shift script
            script = script[match.end():]
        elif re.compile(r"^[$\d]").match(script):
            match = re.compile(r"^[$\d]+[,~]?[$\d]*").match(script)
            # get tuple for address range
            if ',' in match.group(0):
                address_type = "range"
                address = (match.group(0)[:match.group(0).index(',')], match.group(0)[match.group(0).index(',') + 1:])
            elif '~' in match.group(0):
                address_type = "step"
                address = (match.group(0)[:match.group(0).index('~')], match.group(0)[match.group(0).index('~') + 1:])
            else:
                address_type = "line"
                address = match.group(0)
            # shift script
            script = script[match.end():]
        else:
            address_type = "blank"
            address = "all"

        # get command
        sed_commands = {'a', 'c', 'd', 'i', 'p', 's', '='}
        script = script.strip()
        command = script[0]
        if command not in sed_commands:
            await self.bot.say("Unknown command: `{0}`".format(command))
            return

        if command in ('a', 'c', 'i', 's'):
            if len(script) < 2:
                await self.bot.say("Expected characters after: `{0}`".format(command))
                return
            acis_line = script[1:]
        elif command == 'd':
            if len(script) > 1:
                await self.bot.say("Extra characters after command: `{0}`".format(command))
                return
        elif command == 'p':
            if len(script) > 1:
                await self.bot.say("Extra characters after command: `{0}`".format(command))
                return

        if command == 's':
            if acis_line[0] != '/' or acis_line.count('/') < 3:
                await self.bot.say("Unknown substitution pattern: `{0}`".format(acis_line))
                return
            sub = re.compile(r"^(.*?)/(?<!\\/)(.*?)/(?<!\\/)(.*)").match(acis_line[1:])
            if len(sub.groups()) != 3:
                await self.bot.say("Unknown substitution pattern: `{0}`".format(acis_line))
                return
            if sub.groups()[2].lower() not in ("i", "p", ""):
                await self.bot.say("Unrecognized pattern flag: `{0}`".format(sub.groups()[2]))
                return
            sub_flag = sub.groups()[2].lower()
            sub_replace = sub.groups()[1]
            try:
                if sub_flag.lower() == 'i':
                    sub_search = re.compile(sub.groups()[0], re.IGNORECASE)
                else:
                    sub_search = re.compile(sub.groups()[0], re.IGNORECASE)
            except:
                await self.bot.say("Error trying to create substitution pattern: `{0}`".format(sub.groups()[0]))
                return
        elif command == '=':
            if len(script) > 1:
                await self.bot.say("Extra characters after command: `{0}`".format(command))
                return

        #await self.bot.say("command: " + command)

        dom_source = False
        if GNU.url_pattern.match(input):
            #await self.bot.say("Querying `" + input + "`")
            async with aiohttp.ClientSession() as session:
                async with session.get(input) as response:
                    response_text = await response.text()
                    if 'p' in option:
                        # plain text url content
                        if 'g' in option:
                            input = [response_text]
                        else:
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
                        dom_source = True
                        if 'g' in option:
                            input_string = "\n".join([line for line in input])
                            input = [input_string]
        elif input.lower() == "@chat":
            # handle chat log input
            await self.bot.say("Sorry, @chat is not supported at this time.")
            return
        else:
            # user input or pipe
            if 'g' in option:
                input = [input]
            else:
                input = input.splitlines()

        # fix up address
        if address_type in ("range", "step"):
            if address[0] == '$':
                address[0] = len(input)
            else:
                address[0] = int(address[0])
        elif address_type == "line":
            if address == '$':
                address = len(input)
            else:
                address = int(address)
        if (address_type == "range") and (address[0] >= address[1]):
            address_type = "line"
            address = address[0]

        # do sed
        pipe_out = []
        lines_displayed = 0
        for i, line in enumerate(input):
            # strip extra whitespace and newlines from dom sources
            if dom_source:
                line = line.strip()

            line_num = i + 1
            # determine if match
            match = False
            if address_type == "blank":
                match = True
            elif address_type == "range":
                if line_num >= address[0] and line_num <= address[1]:
                    match = True
            elif address_type == "step":
                if line_num >= address[0] and ((line_num - address[0]) % address[1]) == 0:
                    match = True
            elif address_type == "line":
                if line_num == address:
                    match = True
            elif address_type == "regex":
                if address.search(line):
                    match = True

            # build out
            out = []
            if match:
                # insert
                if command == 'i':
                    out.append(acis_line)
                # print
                elif command == 'p':
                    out.append(line)
                # print line
                elif command == '=':
                    out.append(line_num)
                # change
                elif command == 'c':
                    if address_type == "range" and line_num != address[0]:
                        line = ''
                    else:
                        line = acis_line
                # substitute
                elif command == 's':
                    try:
                        line = re.sub(sub_search, sub_replace, line)
                    except:
                        await self.bot.say("Error duing substitution on line {}".format(line_num))

            # silent option
            if 'n' in option and not (command == 's' and sub_flag == 'p'):
                pass
            # echo line
            else:
                out.append(line)

            if match:
                # append
                if command == 'a':
                    out.append(acis_line)
                # delete
                elif command == 'd':
                    out = []

            for s in out:
                # truncate messages that are too long
                if len(s) > GNU.max_message_length and not pipe:
                    s = s[:(GNU.max_message_length - 12)] + " [TRUNCATED]"
                # flood prevention
                if lines_displayed > 0 and lines_displayed % GNU.more_limit == 0:
                    await self.bot.say("Type 'more' or 'm' to continue...")
                    answer = await self.bot.wait_for_message(timeout=15, author=ctx.message.author)
                    if not answer or answer.content.lower() not in ["more", "m"]:
                        await self.bot.say("Command output stopped.")
                        return
                # display output
                if s:
                    if pipe:
                        pipe_out.append(s)
                    else:
                        await self.bot.say("```{0}```".format(s))
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


def setup(bot):
    if soupAvailable:
        n = GNU(bot)
        bot.add_cog(n)
    else:
        raise RuntimeError("You need to run `pip3 install beautifulsoup4`")
