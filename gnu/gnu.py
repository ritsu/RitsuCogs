from discord.ext import commands
import re
import aiohttp
from cogs.utils import checks

try: # check if BeautifulSoup4 is installed
	from bs4 import BeautifulSoup
	soupAvailable = True
except:
	soupAvailable = False

class GNU:
    """Some unix-like utilities"""

    # TODO: pastebin integration for redirect output
    # TODO: chat log input

    def __init__(self, bot):
        self.bot = bot

        # bot will pause and ask user for input after this number of lines have been sent to channel
        self.more_limit = 4

        # number of seconds to wait for user input
        self.response_timeout = 15

        # max character length of a single message to avoid HTTPException: BAD REQUEST (status code: 400)
        self.max_message_length = 1900

        # using a dict in case command and function are different; key = cmd, value = func
        self.command_list = {"grep": "grep", "wc": "wc", "tail": "tail", "cat": "cat", "tac": "tac", "sed": "sed"}

        # used to match url input
        self.url_pattern = re.compile(
                r'^(?:http|ftp)s?://' # http:// or https://
                r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|' #domain...
                r'localhost|' #localhost...
                r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})' # ...or ip
                r'(?::\d+)?' # optional port
                r'(?:/?|[/?]\S+)$', re.IGNORECASE)

        # buffered output {author:[lines], ...}
        self.buffer = {}

        self.help_options = (
            "\n\t-p       If input is a URL, this will treat the URL content as (prettified) html instead of a DOM."
            "\n\t-@       Same as -p except source is not passed through BeautifulSoup's prettify()."
            "\n\t-%       Print each line as a separate message; more likely to hit Discord's 5/5 rate limit.")

        self.help_input = (
            "\n\nInput"
            "\n\tURL      If input matches a URL pattern, bot will fetch URL content as input."
            "\n\t         By default, DOM will be parsed from URL content and text elements will be treated as \"lines\""
            "\n\t         If -p option is set, URL content will be treated as plain text."
            "\n\t@chat    If '@chat' is specified as the input, will search in chat log."
            "\n\t         Logging must be activated in the channel for this to work."
            "\n\t<input>  If none of the previous inputs are detected, remaining text is treated as input."
            "\n\t         To preserve whitespace (including newlines), enclose entire input in quotes.")

    async def _get_url(self, url: str, fmt: str):
        """ Returns content from url resource
        :param url:    valid url string
        :param fmt:    raw, soup, pretty, visible
        :return:       raw      string containing response text
                       soup     BeautifulSoup object
                       pretty   string containing soup.prettify()
                       visible  list of NavigableString objects of visible html elements
        """
        # get url response text
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers = {"User-Agent": "Red-DiscordBot"}) as response:
                response_text = await response.text()

        # build output
        if fmt == "raw":
            return response_text
        elif fmt == "soup":
            soup = BeautifulSoup(response_text, "html.parser")
            return soup
        elif fmt == "pretty":
            soup = BeautifulSoup(response_text, "html.parser")
            return soup.prettify()
        elif fmt == "visible":
            def visible(element):
                if element.parent.name in ['style', 'script', '[document]', 'head', 'title']:
                    return False
                elif re.match('<!--.*-->', str(element)):
                    return False
                elif re.match(r"[\s\r\n]+",str(element)):
                    return False
                return True
            soup = BeautifulSoup(response_text, "html.parser")
            texts = soup.findAll(text=True)
            visible = [text for text in filter(visible, texts)]
            return visible
        else:
            return "Error: Unrecognized format"

    def _split_option(self, option: set):
        """Splits multi-character options into single characters"""
        for opt in list(option):
            if len(opt) > 1:
                for o in opt[:]:
                    option.add(o)
                option.remove(opt)

    async def _flush_buffer(self, count, author, comment, buffer, say):
        """Flush buffer
        :param count:     number of lines said so far by command
        :param author:    author of command that invoked this
        :param comment:   say line in comment block; ignored if pipe_out is set
        :param buffer:    if true, flush buffer; otherwise, do nothing
        :param say:       if true, content in buffer is sent to chat; otherwise, content is discarded
        """
        if buffer and author in self.buffer.keys() and self.buffer[author]:
            if say:
                bufout = "\n".join(self.buffer[author])
                await self._say(bufout, count, author, comment, False)
            self.buffer[author] = []
        return

    async def _say(self, line: str, count: int, author: int, comment: bool, buffer: bool, **kwargs) -> int:
        """Say line in channel or to pipe
        :param line:      line to say
        :param count:     number of lines said so far by command
        :param author:    author of command that invoked this
        :param comment:   say line in comment block; ignored if pipe_out is set
        :param buffer:    if true, output is buffered and flushed only when necessary
        :kwarg line_num:  if specified AND is NOT None, prepend line_num to line
        :kwarg num_width: used to determine line_num spacing; required if line_num is set
        :kwarg pipe_out:  if specified AND is type list, append to pipe_out instead of saying to channel
        :return:          number of lines said to channel; -1 if output stopped
        """
        lines_said = 0
        # handle pipe
        if "pipe_out" in kwargs and isinstance(kwargs["pipe_out"], list):
            kwargs["pipe_out"].append(line)
            return lines_said

        # if line is too long, split into multiple lines
        if len(line) > self.max_message_length:
            for i in range(0, len(line), self.max_message_length):
                if i > 0 and "line_num" in kwargs and kwargs["line_num"] is not None:
                    kwargs["line_num"] = "..."
                result = await self._say(line[i:i+self.max_message_length], (count + lines_said), author, comment, buffer, **kwargs)
                if result == -1:
                    # user failed ro respond to flood protection
                    return result
                lines_said += result
            return lines_said

        # build line
        if "line_num" in kwargs and kwargs["line_num"] is not None:
            # preserve enough space for "...:"
            if kwargs["num_width"] < 3:
                kwargs["num_width"] = 3
            line = "{0:>{width}}: {1}".format(kwargs["line_num"], line, width=kwargs["num_width"])

        # handle buffer
        if buffer:
            if "num_width" in kwargs:
                pad = kwargs["num_width"] + 2
            else:
                pad = 1
            if author not in self.buffer.keys():
                # empty buffer
                self.buffer[author] = [line]
                return 0
            elif sum(len(s) + pad for s in self.buffer[author]) + len(line) < self.max_message_length:
                # space available in buffer
                self.buffer[author].append(line)
                return 0
            else:
                # flush buffer and save line to emptied buffer
                bufout = "\n".join(self.buffer[author])
                self.buffer[author] = [line]
                line = bufout

        # flood prevention
        if count > 0 and count % self.more_limit == 0:
            await self.bot.say("Type 'more' or 'm' to continue...")
            answer = await self.bot.wait_for_message(timeout=self.response_timeout, author=author)
            if not answer or answer.content.lower() not in ["more", "m"]:
                await self.bot.say("Output stopped.")
                return -1

        # escape comment string
        line = line.replace("```", "\\`\\`\\`")

        # say line
        if comment:
            await self.bot.say("```\n{0}\n```".format(line))
        else:
            await self.bot.say(line)
        return 1

    async def _pipe(self, ctx, pipe, pipe_out):
        """ Handle pipe
        :param ctx:       Context
        :param pipe:      Pipe args
        :param pipe_out:  Piped output
        """
        if not pipe:
            return

        # get next command
        cmd = pipe[0]

        # let's be lenient
        if cmd[0] == ctx.prefix:
            cmd = cmd[1:]

        # check if command is valid
        if cmd not in self.command_list.keys():
            await self._say("{0}: command not found".format(cmd), 0, ctx.message.author, True, False)
            return

        # get function for command
        func = getattr(GNU, self.command_list[cmd])

        # invoke command
        if len(pipe) > 1:
            await ctx.invoke(func, *pipe[1:], pipe_in="\n".join(pipe_out))
        else:
            await ctx.invoke(func, pipe_in="\n".join(pipe_out))

        return

    @commands.command(pass_context=True, name='grep')
    async def grep(self, ctx, *args, **kwargs):
        """Print lines that contain a match for a pattern

        Type !grep for more information.
        """
        # display help if args is empty
        if not args and "pipe_in" not in kwargs:
            await self.bot.say("*grep* prints lines that contain a match for a pattern.")
            await self.bot.say("```grep [options] [pattern] [input]```")
            await self.bot.say("```"
                               "\nMatching Options"
                               "\n\t-i       Ignore case distinctions, so that characters that differ only in case match each other."
                               "\n\t-w       Select only those lines containing matches that form whole words."
                               "\n\t-v       Invert the sense of matching, to select non-matching lines."
                               "\n\t-r       Treats search string as a regex pattern; other Matching Options are ignored."
                               "\n\nOutput Options"
                               "\n\t-c       Suppress normal output; instead print a count of matching lines for each input file."
                               "\n\t-n       Prefix each line of output with its line number."
                               "\n\t-m num   Stop reading from input after num matching lines."
                               "\n\t-A num   Print num lines of trailing context after matching lines."
                               "\n\t-B num   Print num lines of leading context before matching lines."
                               "\n\t-C num   Print num lines of leading and trailing context."
                               "\n\nOther Options"
                               + self.help_options + self.help_input +
                               "```")
            return

        # parse user command
        search = ""
        input = []
        option = set()
        option_num = {"m" : 0, "A": 0, "B": 0, "C": 0}
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
                if 'A' in arg:
                    option_num['A'] = int(next(iterator))
                if 'B' in arg:
                    option_num['B'] = int(next(iterator))
                if 'C' in arg:
                    option_num['C'] = int(next(iterator))
            elif not search:
                search = arg
            else:
                input.append(arg)
        input = " ".join(input)
        self._split_option(option)

        # set buffer flag
        if '%' in option:
            buffer = False
        else:
            buffer = True

        # set pipe_out
        if pipe:
            pipe_out = []
        else:
            pipe_out = None

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

        # check arguments
        if not search or not input:
            await self.bot.say("Usage: `" + ctx.prefix + "grep [options] [pattern] [input]`"
                               "\n\nType `" + ctx.prefix + "grep` for more information.")
            return

        # prepare search regex
        if 'r' in option:
            search_pattern = re.compile(r"{0}".format(search))
        else:
            search = re.escape(search)
            if 'w' in option:
                search = "\\b" + search + "\\b"
            if 'i' in option:
                search_pattern = re.compile(r"{0}".format(search), re.IGNORECASE)
            else:
                search_pattern = re.compile(r"{0}".format(search))
        #await self.bot.say("`re: " + str(search_pattern) + " - " + search + "`")

        # parse input
        if self.url_pattern.match(input):
            # url resource
            if 'p' in option:
                input = await self._get_url(input, "pretty")
                input = input.splitlines()
            elif '@' in option:
                input = await self._get_url(input, "raw")
                input = input.splitlines()
            else:
                input = await self._get_url(input, "visible")
        elif input.lower() == "@chat":
            # chat log
            await self.bot.say("Sorry, @chat is not supported at this time.")
            return
        else:
            # user input
            input = input.splitlines()

        # do grep
        match_count = 0        # number of lines matched by search expression
        display_count = 0      # number of lines said to chat
        display_nums = set()   # line numbers of lines that have been said
        line_num = None        # Important that this is set to None at start
        num_width = len(str(len(input)))
        for i, line in enumerate(input):
            # look for match
            match = search_pattern.search(line)
            if 'v' in option and match:
                continue
            elif 'v' not in option and not match:
                continue
            # record match
            match_count += 1
            # suppress output if c option set
            if 'c' in option:
                continue
            # display previous context if necessary
            if 'A' in option or 'C' in option:
                ia = (i-option_num['A']-option_num['C']) if (i-option_num['A']-option_num['C']) >= 0 else 0
                for a, aline in enumerate(input[ia:i]):
                    if (ia+a) not in display_nums:
                        line_num = a + 1 if 'n' in option else None
                        result = await self._say(aline, display_count, ctx.message.author, True, buffer,
                                                 pipe_out=pipe_out, line_num=line_num, num_width=num_width)
                        if result == -1:
                            await self._flush_buffer(display_count, ctx.message.author, True, buffer, False)
                            return
                        display_count += result
                        display_nums.add(ia+a)
            # display line
            line_num = i + 1 if 'n' in option else None
            if i not in display_nums:
                result = await self._say(line, display_count, ctx.message.author, True, buffer,
                                         pipe_out=pipe_out, line_num=line_num, num_width=num_width)
                if result == -1:
                    await self._flush_buffer(display_count, ctx.message.author, True, buffer, False)
                    return
                display_count += result
                display_nums.add(i)
            # display additional context if necessary
            if 'B' in option or 'C' in option:
                ib = i + option_num['B'] + option_num['C'] + 1
                for b, bline in enumerate(input[(i+1):ib]):
                    if (i+1+b) not in display_nums:
                        line_num = b + 1 if 'n' in option else None
                        result = await self._say(bline, display_count, ctx.message.author, True, buffer,
                                                 pipe_out=pipe_out, line_num=line_num, num_width=num_width)
                        if result == -1:
                            await self._flush_buffer(display_count, ctx.message.author, True, buffer, False)
                            return
                        display_count += result
                        display_nums.add(i+1+b)
            # stop if m option set and limit reached
            if 'm' in option and match_count >= option_num['m']:
                break

        # output for c option
        if 'c' in option:
            result = await self._say(str(match_count), display_count, ctx.message.author, True,
                                     pipe_out=pipe_out, line_num=line_num, num_width=num_width)
            if result == -1:
                await self._flush_buffer(display_count, ctx.message.author, True, buffer, False)
                return

        # flush buffer
        await self._flush_buffer(display_count, ctx.message.author, True, buffer, True)

        # handle pipe
        await self._pipe(ctx, pipe, pipe_out)

    @commands.command(pass_context=True, name='wc')
    async def wc(self, ctx, *args, **kwargs):
        """Count the number of characters, whitespace-separated words, and newlines

        Type !wc for more information.
        """
        # display help if args is empty
        if not args and "pipe_in" not in kwargs:
            await self.bot.say("*wc* counts the number of characters, whitespace-separated words, and newlines in the given input.")
            await self.bot.say("```wc [option] [input]```")
            await self.bot.say("```"
                               "\nOptions"
                               "\n\t-m       Print only the character counts."
                               "\n\t-w       Print only the word counts."
                               "\n\t-l       Print only the newline counts."
                               + self.help_options + self.help_input +
                               "```")
            return

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
        self._split_option(option)

        # no point in using buffer for wc

        # set pipe_out
        if pipe:
            pipe_out = []
        else:
            pipe_out = None

        # try pipe_in if input is empty
        if not input and "pipe_in" in kwargs:
            input = kwargs["pipe_in"]

        # check arguments
        if not input:
            await self.bot.say("Usage: `" + ctx.prefix + "wc [option] [input]`"
                               "\n\nType `" + ctx.prefix + "wc` for more information.")
            return

        # parse input
        if self.url_pattern.match(input):
            # url resource
            if 'p' in option:
                input = await self._get_url(input, "pretty")
            elif '@' in option:
                input = await self._get_url(input, "raw")
            else:
                input_texts = await self._get_url(input, "visible")
                input = "\n".join([line for line in input_texts])
        elif input.lower() == "@chat":
            # chat log
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

        if pipe:
            pipe_out = [header, hr, data]
        else:
            line = "\n".join([header, hr, data])
            await self._say(line, 0, ctx.message.author, True, False)

        # handle pipe
        await self._pipe(ctx, pipe, pipe_out)

    @commands.command(pass_context=True, name='tail')
    async def tail(self, ctx, *args, **kwargs):
        """Prints the last part (10 lines by default) of input

        Type !tail for more information.
        """
        # display help if args is empty
        if not args and "pipe_in" not in kwargs:
            await self.bot.say("*tail* prints the last part (10 lines by default) of input.")
            await self.bot.say("```tail [options] [input]```")
            await self.bot.say("```"
                               "\nOptions"
                               "\n\t-n [+]N  Output the last N lines. However, if N is prefixed with a '+',"
                               "\n\t         start printing with line N from the start of input, instead of from the end."
                               + self.help_options + self.help_input +
                               "```")
            return

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
        self._split_option(option)

        # set buffer flag
        if '%' in option:
            buffer = False
        else:
            buffer = True

        # set pipe_out
        if pipe:
            pipe_out = []
        else:
            pipe_out = None

        # try pipe_in if input is empty
        if not input and "pipe_in" in kwargs:
            input = kwargs["pipe_in"]

        # check arguments
        if not input:
            await self.bot.say("Usage: `" + ctx.prefix + "tail [options] [input]`"
                               "\n\nType `" + ctx.prefix + "tail` for more information.")
            return

        # parse input
        if self.url_pattern.match(input):
            # url resource
            if 'p' in option:
                input = await self._get_url(input, "pretty")
                input = input.splitlines()
            elif '@' in option:
                input = await self._get_url(input, "raw")
                input = input.splitlines()
            else:
                input = await self._get_url(input, "visible")
        elif input.lower() == "@chat":
            # chat log
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
        display_count = 0
        for line in input[pos:]:
            result = await self._say(line, display_count, ctx.message.author, True, buffer,
                                     pipe_out=pipe_out)
            if result == -1:
                await self._flush_buffer(display_count, ctx.message.author, True, buffer, False)
                return
            display_count += result

        # flush buffer
        await self._flush_buffer(display_count, ctx.message.author, True, buffer, True)

        # handle pipe
        await self._pipe(ctx, pipe, pipe_out)

    @commands.command(pass_context=True, name='cat')
    async def cat(self, ctx, *args, **kwargs):
        """Echoes input to output

        Type !cat for more information.
        """
        # display help if args is empty
        if not args and "pipe_in" not in kwargs:
            await self.bot.say("*cat* echoes the contents of the input.")
            await self.bot.say("```cat [options] [input]```")
            await self.bot.say("```"
                               "\nOptions"
                               "\n\t-b       Number all nonempty output lines, starting with 1."
                               "\n\t-n       Number all output lines, starting with 1. This option is ignored if -b is in effect."
                               "\n\t-s       Suppress repeated adjacent blank lines; output just one empty line instead of several."
                               + self.help_options + self.help_input +
                               "```")
            return

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
        self._split_option(option)

        # set buffer flag
        if '%' in option:
            buffer = False
        else:
            buffer = True

        # set pipe_out
        if pipe:
            pipe_out = []
        else:
            pipe_out = None

        # try pipe_in if input is empty
        if not input and "pipe_in" in kwargs:
            input = kwargs["pipe_in"]

        # check arguments
        if not input:
            await self.bot.say("Usage: `" + ctx.prefix + "cat [options] [input]`"
                               "\n\nType `" + ctx.prefix + "cat` for more information.")
            return

        # parse input
        if self.url_pattern.match(input):
            # url resource
            if 'p' in option:
                input = await self._get_url(input, "pretty")
                input = input.splitlines()
            elif '@' in option:
                input = await self._get_url(input, "raw")
                input = input.splitlines()
            else:
                input = await self._get_url(input, "visible")
        elif input.lower() == "@chat":
            # chat log
            await self.bot.say("Sorry, @chat is not supported at this time.")
            return
        else:
            # user input
            input = input.splitlines()

        # do cat
        line_b = 0             # line number for 'b' option
        line_n = 0             # line number for 'n' option
        display_count = 0      # number of lines said to chat
        prev_empty = False     # keep track of previous line for 's' option
        line_num = None        # Important that this is set to None at start
        num_width = len(str(len(input)))
        for line in input:
            # skip line if 's' is set, previous line was empty, and this line is empty
            if 's' in option and prev_empty and not line.strip():
                continue
            # increment line counters
            line_n += 1
            if line.strip():
                line_b += 1
            # set line number
            if 'b' in option and line.strip():
                line_num = line_b
            elif 'n' in option:
                line_num = line_n
            # do output
            result = await self._say(line, display_count, ctx.message.author, True, buffer,
                                     pipe_out=pipe_out, line_num=line_num, num_width=num_width)
            if result == -1:
                await self._flush_buffer(display_count, ctx.message.author, True, buffer, False)
                return
            display_count += result
            # set prev_empty
            if not line.strip():
                prev_empty = True
            else:
                prev_empty = False

        # flush buffer
        await self._flush_buffer(display_count, ctx.message.author, True, buffer, True)

        # handle pipe
        await self._pipe(ctx, pipe, pipe_out)

    @commands.command(pass_context=True, name='tac')
    async def tac(self, ctx, *args, **kwargs):
        """Echoes input to output in reverse by line or user specified separator

        Type !tac for more information.
        """
        # display help if args is empty
        if not args and "pipe_in" not in kwargs:
            await self.bot.say("*tac* echoes input to output in reverse by line or user specified separator.")
            await self.bot.say("```tac [options] [input]```")
            await self.bot.say("```"
                               "\nOptions"
                               "\n\t-s sep   Use \"sep\" as the record separator, instead of newline."
                               "\n\t-r       Treat the separator string as a regular expression."
                               + self.help_options + self.help_input +
                               "```")
            return

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
        self._split_option(option)

        # set buffer flag
        if '%' in option:
            buffer = False
        else:
            buffer = True

        # set pipe_out
        if pipe:
            pipe_out = []
        else:
            pipe_out = None

        # try pipe_in if input is empty
        if not input and "pipe_in" in kwargs:
            input = kwargs["pipe_in"]

        # check arguments
        if not input:
            await self.bot.say("Usage: `" + ctx.prefix + "tac [options] [input]`"
                               "\n\nType `" + ctx.prefix + "tac` for more information.")
            return

        # parse input
        if self.url_pattern.match(input):
            # url resource
            if 'p' in option:
                input = await self._get_url(input, "pretty")
            elif '@' in option:
                input = await self._get_url(input, "raw")
            else:
                input_texts = await self._get_url(input, "visible")
                input = "\n".join([line for line in input_texts])
        elif input.lower() == "@chat":
            # chat log
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
        display_count = 0
        for line in reversed(input):
            result = await self._say(line, display_count, ctx.message.author, True, buffer,
                                     pipe_out=pipe_out)
            if result == -1:
                await self._flush_buffer(display_count, ctx.message.author, True, buffer, False)
                return
            display_count += result

        # flush buffer
        await self._flush_buffer(display_count, ctx.message.author, True, buffer, True)

        # handle pipe
        await self._pipe(ctx, pipe, pipe_out)

    @commands.command(pass_context=True, name='sed')
    async def sed(self, ctx, *args, **kwargs):
        """A simple stream editor

        Type !sed for more information.
        """
        if not args and "pipe_in" not in kwargs:
            await self.bot.say("*sed* is a simple stream editor.")
            await self.bot.say("```sed [options] [script] [input]```")
            await self.bot.say("```"
                               "\nOptions"
                               "\n\t-g       Process entire input as a single string, rather than line by line."
                               "\n\t-n       Disable automatic printing; only produce output when explicitly told to."
                               + self.help_options +
                               "\n\nScript Address"
                               "\n\t/.../    Returns lines that match the regular expression."
                               "\n\tA        Returns line number A."
                               "\n\tA,B      Returns lines from A to B."
                               "\n\tA~N      Returns every Nth line, starting from A"
                               "\n\nScript Command"
                               "\n\ta...     Append after each line."
                               "\n\tc...     Change lines with new line."
                               "\n\td        Delete lines."
                               "\n\ti...     Insert before each line."
                               "\n\tp        Print line."
                               "\n\ts/././   Substitute with regular expression pattern."
                               "\n\t=        Print line number."
                               "\n\nScript Pattern Flag"
                               "\n\t/i       Ignore case"
                               "\n\t/p       Print (mostly used when -n option is active)"
                               + self.help_input +
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

        # set buffer flag
        if '%' in option:
            buffer = False
        else:
            buffer = True

        # set pipe_out
        if pipe:
            pipe_out = []
        else:
            pipe_out = None

        # try pipe_in if input is empty
        if not input and "pipe_in" in kwargs:
            input = kwargs["pipe_in"]

        # check arguments
        if not script:
            await self.bot.say("Script command not found."
                               "\nUsage: `" + ctx.prefix + "sed [options] [script] [input]`"
                               "\n\nType `" + ctx.prefix + "sed` for more information.")
            return
        if not input:
            await self.bot.say("Input not found."
                               "\nUsage: `" + ctx.prefix + "sed [options] [script] [input]`"
                               "\n\nType `" + ctx.prefix + "sed` for more information.")
            return

        # get address
        address_type = ""
        address = ""
        if script[0] == '/':
            address_type = "regex"
            match = re.compile(r"^/(.*?)/(?<!\\/)i?", re.IGNORECASE).match(script)
            # get regex for address range
            try:
                if match.group(0)[-1].lower() == 'i':
                    address = re.compile(r"{0}".format(match.group(1)), re.IGNORECASE)
                else:
                    address = re.compile(r"{0}".format(match.group(1)))
            except:
                await self._say("Error trying to create substitution pattern: `{0}`".format(match.group(1)), 0, ctx.message.author, False, False)
                return
            # shift script
            script = script[match.end():]
        elif re.compile(r"^[$\d]").match(script):
            match = re.compile(r"^[$\d]+[,~]?[$\d]*").match(script)
            # get tuple for address range
            if ',' in match.group(0):
                address_type = "range"
                address = [match.group(0)[:match.group(0).index(',')], match.group(0)[match.group(0).index(',') + 1:]]
            elif '~' in match.group(0):
                address_type = "step"
                address = [match.group(0)[:match.group(0).index('~')], match.group(0)[match.group(0).index('~') + 1:]]
            else:
                address_type = "line"
                address = match.group(0)
            # shift script
            script = script[match.end():]
        else:
            address_type = "blank"
            address = "all"

        # check script again
        if not script:
            await self.bot.say("Script command not found."
                               "\nUsage: `" + ctx.prefix + "sed [options] [script] [input]`"
                               "\n\nType `" + ctx.prefix + "sed` for more information.")
            return

        # get command
        sed_commands = {'a', 'c', 'd', 'i', 'p', 's', '='}
        script = script.strip()
        command = script[0]
        if command not in sed_commands:
            await self._say("Unknown command: `{0}`".format(command), 0, ctx.message.author, False, False)
            return

        if command in ('a', 'c', 'i', 's'):
            if len(script) < 2:
                await self._say("Expected characters after: `{0}`".format(command), 0, ctx.message.author, False, False)
                return
            acis_line = script[1:]
        elif command == 'd':
            if len(script) > 1:
                await self._say("Extra characters after command: `{0}`".format(command), 0, ctx.message.author, False, False)
                return
        elif command == 'p':
            if len(script) > 1:
                await self._say("Extra characters after command: `{0}`".format(command), 0, ctx.message.author, False, False)
                return

        if command == 's':
            if acis_line[0] != '/' or acis_line.count('/') < 3:
                await self._say("Unknown substitution pattern: `{0}`".format(command), 0, ctx.message.author, False, False)
                return
            sub = re.compile(r"^(.*?)/(?<!\\/)(.*?)/(?<!\\/)(.*)").match(acis_line[1:])
            if len(sub.groups()) != 3:
                await self._say("Unknown substitution pattern: `{0}`".format(command), 0, ctx.message.author, False, False)
                return
            if sub.groups()[2].lower() not in ("i", "p", ""):
                await self._say("Unrecognized pattern flag: `{0}`".format(command), 0, ctx.message.author, False, False)
                return
            sub_flag = sub.groups()[2].lower()
            sub_replace = sub.groups()[1]
            try:
                if sub_flag.lower() == 'i':
                    sub_search = re.compile(sub.groups()[0], re.IGNORECASE)
                else:
                    sub_search = re.compile(sub.groups()[0], re.IGNORECASE)
            except:
                await self._say("Error trying to create substitution pattern: `{0}`".format(command), 0, ctx.message.author, False, False)
                return
        elif command == '=':
            if len(script) > 1:
                await self._say("Extra characters after command: `{0}`".format(command), 0, ctx.message.author, False, False)
                return

        #await self.bot.say("command: " + command)

        # parse input
        if self.url_pattern.match(input):
            # url resource
            if 'p' in option:
                input = await self._get_url(input, "pretty")
                if 'g' in option:
                    input = [input]
                else:
                    input = input.splitlines()
            elif '@' in option:
                input = await self._get_url(input, "raw")
                if 'g' in option:
                    input = [input]
                else:
                    input = input.splitlines()
            else:
                input = await self._get_url(input, "visible")
                if 'g' in option:
                    input_string = "\n".join([line for line in input])
                    input = [input_string]
        elif input.lower() == "@chat":
            # chat log
            await self.bot.say("Sorry, @chat is not supported at this time.")
            return
        else:
            # user input
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
            if address[1] == '$':
                address[1] = len(input)
            else:
                address[1] = int(address[1])
        elif address_type == "line":
            if address == '$':
                address = len(input)
            else:
                address = int(address)
        if (address_type == "range") and (address[0] >= address[1]):
            address_type = "line"
            address = address[0]

        # do sed
        display_count = 0
        sub_match= False
        for i, line in enumerate(input):
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

            # match operations before echo line
            if match:
                # insert
                if command == 'i':
                    result = await self._say(acis_line, display_count, ctx.message.author, True, buffer, pipe_out=pipe_out)
                    if result == -1:
                        await self._flush_buffer(display_count, ctx.message.author, True, buffer, False)
                        return
                    display_count += result
                # print
                elif command == 'p':
                    result = await self._say(line, display_count, ctx.message.author, True, buffer, pipe_out=pipe_out)
                    if result == -1:
                        await self._flush_buffer(display_count, ctx.message.author, True, buffer, False)
                        return
                    display_count += result
                # print line
                elif command == '=':
                    result = await self._say(str(line_num), display_count, ctx.message.author, True, buffer, pipe_out=pipe_out)
                    if result == -1:
                        await self._flush_buffer(display_count, ctx.message.author, True, buffer, False)
                        return
                    display_count += result
                # change
                elif command == 'c':
                    if address_type == "range" and line_num != address[0]:
                        line = ''
                    else:
                        line = acis_line
                # substitute
                elif command == 's':
                    if sub_search.search(line):
                        sub_match = True
                        line = re.sub(sub_search, sub_replace, line)

            # echo line
            if match:
                # delete
                if command == 'd':
                    pass
                # silent option - only print if s/././ matched and /p flag set
                elif 'n' in option:
                    # print substituted line
                    if sub_match and sub_flag == 'p':
                        result = await self._say(line, display_count, ctx.message.author, True, buffer, pipe_out=pipe_out)
                        if result == -1:
                            await self._flush_buffer(display_count, ctx.message.author, True, buffer, False)
                            return
                        display_count += result
                    else:
                        # do not print anything
                        pass
                else:
                    # normal echo
                    result = await self._say(line, display_count, ctx.message.author, True, buffer, pipe_out=pipe_out)
                    if result == -1:
                        await self._flush_buffer(display_count, ctx.message.author, True, buffer, False)
                        return
                    display_count += result
            else:
                # silent option
                if 'n' in option:
                    # do not print anything
                    pass
                else:
                    # normal echo
                    result = await self._say(line, display_count, ctx.message.author, True, buffer, pipe_out=pipe_out)
                    if result == -1:
                        await self._flush_buffer(display_count, ctx.message.author, True, buffer, False)
                        return
                    display_count += result

            # match operations after echo line
            if match:
                # append
                if command == 'a':
                    result = await self._say(acis_line, display_count, ctx.message.author, True, buffer, pipe_out=pipe_out)
                    if result == -1:
                        await self._flush_buffer(display_count, ctx.message.author, True, buffer, False)
                        return
                    display_count += result

            # reset sub_match
            sub_match = False

        # flush buffer
        await self._flush_buffer(display_count, ctx.message.author, True, buffer, True)

        # handle pipe
        await self._pipe(ctx, pipe, pipe_out)


def setup(bot):
    if soupAvailable:
        n = GNU(bot)
        bot.add_cog(n)
    else:
        raise RuntimeError("You need to run `pip3 install beautifulsoup4`")
