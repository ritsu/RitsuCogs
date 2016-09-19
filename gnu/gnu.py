from discord.ext import commands
from cogs.utils.dataIO import dataIO
from cogs.utils import checks
import os
import re
import aiohttp
import copy
from datetime import timezone

try:  # check if BeautifulSoup4 is installed
    from bs4 import BeautifulSoup

    soupAvailable = True
except:
    soupAvailable = False


class GNU:
    """Some unix-like utilities"""

    base_dir = os.path.join("data", "gnu")
    config_path = os.path.join(base_dir, "config.json")

    def __init__(self, bot):
        self.bot = bot

        # chat log config
        self.config = dataIO.load_json(self.config_path)
        self.config_default = {"active": False, "max_size": 1048576, "log_bot": False}

        # Buffer when resizing log file to avoid too many resize operations
        self.log_buffer = 1024 * 100

        # bot will pause and ask user for input after this number of messages have been sent to channel
        self.more_limit = 4

        # number of seconds to wait for user input
        self.response_timeout = 15

        # max character length of a single message
        self.max_message_length = 1900

        # using a dict in case command and function are different; key = cmd, value = func
        self.command_list = {"grep": "grep", "wc": "wc", "tail": "tail", "cat": "cat", "tac": "tac", "sed": "sed"}

        # used to match url input
        self.url_pattern = re.compile(
            r"^(?:http|ftp)s?://"  # http:// or https://
            r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|"  # domain...
            r"localhost|"  # localhost...
            r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
            r"(?::\d+)?"  # optional port
            r"(?:/?|[/?]\S+)$", re.IGNORECASE)

        # buffered output {author:[lines], ...}
        self.buffer = {}

        self.help_options = (
            "\n\t-p       If input is a URL, this will treat the URL content as (prettified) html instead of a DOM."
            "\n\t-@       Same as -p except source is not passed through BeautifulSoup's prettify()."
            "\n\t-%       Print each line as a separate message; more likely to hit Discord's 5/5 rate limit.")

        self.help_input = (
            "\n\nInput"
            "\n\tURL      If input matches a URL pattern, bot will fetch URL content as input."
            "\n\t         By default, DOM will be parsed from URL content and text elements will be treated as 'lines'"
            "\n\t         Unless -p or -@ options are set."
            "\n\t@chat    If '@chat' is specified as the input, chat log will be used as input."
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
            async with session.get(url, headers={"User-Agent": "Red-DiscordBot"}) as response:
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
                elif re.match(r"[\s\r\n]+", str(element)):
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

    def _get_redirect(self, stdin: list):
        """Set redirect if specified, removes redirect from stdin if found

        :return:  None - Discord
                  List - [api_paste_name, api_paste_expire_date]
        """
        if len(stdin) > 1 and stdin[-2] == ">>":
            # Permanent pastebin
            redirect = {"api_paste_name": stdin.pop(), "api_paste_expire_date": "N"}
            stdin.pop()
            return redirect
        elif len(stdin) > 1 and stdin[-2] == ">":
            # Temporary pastebin
            redirect = {"api_paste_name": stdin.pop(), "api_paste_expire_date": "1D"}
            stdin.pop()
            return redirect
        elif len(stdin) > 0 and len(stdin[-1]) > 2 and stdin[-1][0:2] == ">>":
            # Permanent pastebin
            redirect = {"api_paste_name": stdin.pop()[2:], "api_paste_expire_date": "N"}
            return redirect
        elif len(stdin) > 0 and len(stdin[-1]) > 1 and stdin[-1][0] == ">":
            # Temporary pastebin
            redirect = {"api_paste_name": stdin.pop()[1:], "api_paste_expire_date": "1D"}
            return redirect

        return None

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
            # build line
            if "line_num" in kwargs and kwargs["line_num"] is not None:
                # preserve enough space for "...:"
                if kwargs["num_width"] < 3:
                    kwargs["num_width"] = 3
                line = "{0:>{width}}: {1}".format(kwargs["line_num"], line, width=kwargs["num_width"])
            kwargs["pipe_out"].append(line)
            return lines_said

        # if line is too long, split into multiple lines
        if len(line) > self.max_message_length:
            for i in range(0, len(line), self.max_message_length):
                if i > 0 and "line_num" in kwargs and kwargs["line_num"] is not None:
                    kwargs["line_num"] = "..."
                result = await self._say(line[i:i + self.max_message_length], (count + lines_said), author, comment,
                                         buffer, **kwargs)
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

    async def _pipe(self, ctx, pipe, pipe_out, redirect):
        """ Handle pipe and redirect
        :param ctx:       Context
        :param pipe:      Pipe args
        :param pipe_out:  Piped output
        :param redirect:  Redirect setting
        """
        # if pipe exists, invoke pipe
        if pipe:
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
        elif redirect:
            # return if output is empty
            if not pipe_out:
                await self._say("No output", 0, ctx.message.author, False, False)
                return
            # post to pastebin
            data = {"api_dev_key": self.config["pastebin_api_key"],
                    "api_option": "paste",
                    "api_paste_code": "\n".join(pipe_out),
                    "api_paste_name": redirect["api_paste_name"],
                    "api_paste_expire_date": redirect["api_paste_expire_date"]}
            url = "http://pastebin.com/api/api_post.php"
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=data, headers={"User-Agent": "Red-DiscordBot"}) as response:
                    response_text = await response.text()
                    #response_text = response_text.replace("http://pastebin.com/", "http://pastebin.com/raw/")
                    await self._say("Output to pastebin with the following result: {0}".format(response_text),
                                    0, ctx.message.author, False, False)
            return

    async def _get_chat(self, ctx):
        """Get chat log"""

        # ignore private channels
        if ctx.message.channel.is_private:
            await self.bot.say("Chat log not available for private channels.")
            return None

        cid = ctx.message.channel.id
        sid = ctx.message.server.id

        # Check if logging is enabled for channel
        if cid not in self.config or not self.config[cid]["active"]:
            await self.bot.say("Chat log does not appear to be enabled for this channel. "
                               "Type`{0}clog on` to enable chat log.".format(ctx.prefix))
            return None

        # Get log
        log = ""
        file = os.path.join(self.base_dir, sid, cid)
        if not os.path.isfile(file):
            return log
        with open(file, encoding="utf-8", mode='r') as f:
            log = f.read()
        return log

    @commands.command(pass_context=True, name='pastebin')
    @checks.is_owner()
    async def pastebin(self, ctx, *args):
        """Set pastebin API key

        This is required to redirect output to pastebin for commands like:

        cat something interesting > mypaste
        """

        if not args:
            await self.bot.say("Please specify a key.")
            return

        key = args[0].strip()
        self.config["pastebin_api_key"] = key
        dataIO.save_json(self.config_path, self.config)
        await self.bot.say("Pastebin API key saved.")
        return

    @commands.command(pass_context=True, name='clog')
    @checks.admin_or_permissions()
    async def clog(self, ctx, *args, **kwargs):
        """Manage chat logs"""

        # display help if args is empty
        if not args:
            await self.bot.say("*clog* manages logging options for the current channel.")
            await self.bot.say("```"
                               "\nclog [on|off]      Turn logging on or off for current channel."
                               "\nclog size num      Set the maximum log size for current channel to num MiB."
                               "\nclog bot [on|off]  Set whether or not bot logs its own messages."
                               "\nclog status        Display log settings and status for current channel."
                               "\nclog delete        Delete all logs for current channel."
                               "```")
            return

        # parse arguments
        cid = ctx.message.channel.id
        sid = ctx.message.server.id
        if args[0].lower() == "on":
            self._clog_set(cid, active=True)
            await self.bot.say("Chat log enabled.")
        elif args[0].lower() == "off":
            self._clog_set(cid, active=False)
            await self.bot.say("Chat log disabled.")
        elif args[0].lower() == "size":
            try:
                max_size = int(args[1])
            except:
                await self.bot.say("Please specify an integer for size.")
                return
            if max_size < 1:
                await self.bot.say("Minimum size is 1.")
                return
            max_size *= 1048576
            self._clog_set(cid, max_size=max_size)
            await self.bot.say("Chat log size set to `{0}`".format(self._size(max_size)))
        elif args[0].lower() == "bot":
            if args[1].lower() == "on" or args[1].lower == "true":
                self._clog_set(cid, log_bot=True)
                await self.bot.say("Bot self log enabled.")
            elif args[1].lower() == "off" or args[1].lower == "false":
                self._clog_set(cid, log_bot=False)
                await self.bot.say("Bot self log disabled.")
            else:
                await self.bot.say("Please specify 'on' or 'off'.")
        elif args[0].lower() == "status":
            if cid in self.config:
                c = self.config[cid]
                # Get current log size:
                file = os.path.join(self.base_dir, sid, cid)
                try:
                    size = self._size(os.path.getsize(file))
                except:
                    size = 0
                max_size = self._size(c["max_size"])
                # Display status
                await self.bot.say(
                    "Active: `{0[active]}`, Log bot: `{0[log_bot]}`, Max size: `{1}`, "
                    "Current size: `{2}`".format(c, max_size, size))
            else:
                await self.bot.say("Chat log not setup for this channel.")
        elif args[0].lower() == "delete":
            # Confirm delete
            await self.bot.say("Deleting chat log is permanent! Type 'yes' or 'y' to proceed...")
            answer = await self.bot.wait_for_message(timeout=self.response_timeout, author=ctx.message.author)
            if not answer or answer.content.lower() not in ["yes", "y"]:
                await self.bot.say("No action taken.")
                return -1
            # Delete file
            file = os.path.join(self.base_dir, sid, cid)
            try:
                os.remove(file)
                await self.bot.say("Chat log deleted.")
            except:
                await self.bot.say("Chat log not found.")
        else:
            await self.bot.say("Unknown command")

    @commands.command(pass_context=True, name='grep')
    async def grep(self, ctx, *args, **kwargs):
        """Print lines that contain a match for a pattern"""

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
        stdin = []
        option = set()
        option_num = {'m': 0, 'A': 0, 'B': 0, 'C': 0}
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
                stdin.append(arg)
        self._split_option(option)

        # Only look for redirected stdout if there is no pipe
        if not pipe:
            redirect = self._get_redirect(stdin)
        else:
            redirect = None

        # Prepare stdin
        stdin = " ".join(stdin)

        # set buffer flag
        if '%' in option:
            buffer = False
        else:
            buffer = True

        # set pipe_out
        if pipe or redirect:
            pipe_out = []
        else:
            pipe_out = None

        # try pipe_in if input is empty
        if not stdin and "pipe_in" in kwargs:
            stdin = kwargs["pipe_in"]

        # check arguments
        if not search or not stdin:
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
        # await self.bot.say("`re: " + str(search_pattern) + " - " + search + "`")

        # parse input
        if self.url_pattern.match(stdin):
            # url resource
            if 'p' in option:
                stdin = await self._get_url(stdin, "pretty")
                stdin = stdin.splitlines()
            elif '@' in option:
                stdin = await self._get_url(stdin, "raw")
                stdin = stdin.splitlines()
            else:
                stdin = await self._get_url(stdin, "visible")
        elif stdin.lower() == "@chat":
            # chat log
            stdin = await self._get_chat(ctx)
            if stdin is None:
                return
            stdin = stdin.splitlines()
        else:
            # user input
            stdin = stdin.splitlines()

        # do grep
        match_count = 0  # number of lines matched by search expression
        display_count = 0  # number of lines said to chat
        display_nums = set()  # line numbers of lines that have been said
        line_num = None  # Important that this is set to None at start
        num_width = len(str(len(stdin)))
        for i, line in enumerate(stdin):
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
                ia = (i - option_num['A'] - option_num['C']) if (i - option_num['A'] - option_num['C']) >= 0 else 0
                for a, aline in enumerate(stdin[ia:i]):
                    if (ia + a) not in display_nums:
                        line_num = a + 1 if 'n' in option else None
                        result = await self._say(aline, display_count, ctx.message.author, True, buffer,
                                                 pipe_out=pipe_out, line_num=line_num, num_width=num_width)
                        if result == -1:
                            await self._flush_buffer(display_count, ctx.message.author, True, buffer, False)
                            return
                        display_count += result
                        display_nums.add(ia + a)
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
                for b, bline in enumerate(stdin[(i + 1):ib]):
                    if (i + 1 + b) not in display_nums:
                        line_num = b + 1 if 'n' in option else None
                        result = await self._say(bline, display_count, ctx.message.author, True, buffer,
                                                 pipe_out=pipe_out, line_num=line_num, num_width=num_width)
                        if result == -1:
                            await self._flush_buffer(display_count, ctx.message.author, True, buffer, False)
                            return
                        display_count += result
                        display_nums.add(i + 1 + b)
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
        await self._pipe(ctx, pipe, pipe_out, redirect)

    @commands.command(pass_context=True, name='wc')
    async def wc(self, ctx, *args, **kwargs):
        """Count the number of characters, whitespace-separated words, and newlines"""
        # display help if args is empty
        if not args and "pipe_in" not in kwargs:
            await self.bot.say(
                "*wc* counts the number of characters, whitespace-separated words, and newlines in the given input.")
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
        stdin = []
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
                stdin.append(arg)
        self._split_option(option)

        # Only look for redirected stdout if there is no pipe
        if not pipe:
            redirect = self._get_redirect(stdin)
        else:
            redirect = None

        # Prepare stdin
        stdin = " ".join(stdin)

        # No point in using buffer for wc

        # Set pipe_out
        if pipe or redirect:
            pipe_out = []
        else:
            pipe_out = None

        # try pipe_in if input is empty
        if not stdin and "pipe_in" in kwargs:
            stdin = kwargs["pipe_in"]

        # check arguments
        if not stdin:
            await self.bot.say("Usage: `" + ctx.prefix + "wc [option] [input]`"
                                                         "\n\nType `" + ctx.prefix + "wc` for more information.")
            return

        # parse input
        if self.url_pattern.match(stdin):
            # url resource
            if 'p' in option:
                stdin = await self._get_url(stdin, "pretty")
            elif '@' in option:
                stdin = await self._get_url(stdin, "raw")
            else:
                input_texts = await self._get_url(stdin, "visible")
                stdin = "\n".join([line for line in input_texts])
        elif stdin.lower() == "@chat":
            # chat log
            stdin = await self._get_chat(ctx)
            if stdin is None:
                return
        else:
            # user input
            pass

        # get counts
        lines = len(stdin.splitlines())
        words = len(stdin.split())
        chars = len(stdin)

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

        if pipe or redirect:
            pipe_out = [header, hr, data]
        else:
            line = "\n".join([header, hr, data])
            await self._say(line, 0, ctx.message.author, True, False)

        # handle pipe
        await self._pipe(ctx, pipe, pipe_out, redirect)

    @commands.command(pass_context=True, name='tail')
    async def tail(self, ctx, *args, **kwargs):
        """Prints the last part (10 lines by default) of input"""
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
        stdin = []
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
                stdin.append(arg)
        self._split_option(option)

        # Only look for redirected stdout if there is no pipe
        if not pipe:
            redirect = self._get_redirect(stdin)
        else:
            redirect = None

        # Prepare stdin
        stdin = " ".join(stdin)

        # Set buffer flag
        if '%' in option:
            buffer = False
        else:
            buffer = True

        # Set pipe_out
        if pipe or redirect:
            pipe_out = []
        else:
            pipe_out = None

        # try pipe_in if input is empty
        if not stdin and "pipe_in" in kwargs:
            stdin = kwargs["pipe_in"]

        # check arguments
        if not stdin:
            await self.bot.say("Usage: `" + ctx.prefix + "tail [options] [input]`"
                                                         "\n\nType `" + ctx.prefix + "tail` for more information.")
            return

        # parse input
        if self.url_pattern.match(stdin):
            # url resource
            if 'p' in option:
                stdin = await self._get_url(stdin, "pretty")
                stdin = stdin.splitlines()
            elif '@' in option:
                stdin = await self._get_url(stdin, "raw")
                stdin = stdin.splitlines()
            else:
                stdin = await self._get_url(stdin, "visible")
        elif stdin.lower() == "@chat":
            # chat log
            stdin = await self._get_chat(ctx)
            if stdin is None:
                return
            stdin = stdin.splitlines()
        else:
            # user input
            stdin = stdin.splitlines()

        # determine range
        if option_num:
            if option_num[0] == '+':
                pos = int(option_num[1:]) - 1
            else:
                pos = len(stdin) - int(option_num)
        else:
            pos = len(stdin) - 10
        if pos < 0:
            pos = 0

        # do tail
        display_count = 0
        for line in stdin[pos:]:
            result = await self._say(line, display_count, ctx.message.author, True, buffer,
                                     pipe_out=pipe_out)
            if result == -1:
                await self._flush_buffer(display_count, ctx.message.author, True, buffer, False)
                return
            display_count += result

        # flush buffer
        await self._flush_buffer(display_count, ctx.message.author, True, buffer, True)

        # handle pipe
        await self._pipe(ctx, pipe, pipe_out, redirect)

    @commands.command(pass_context=True, name='cat')
    async def cat(self, ctx, *args, **kwargs):
        """Echoes input to output"""
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
        stdin = []
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
                stdin.append(arg)
        self._split_option(option)

        # Only look for redirected stdout if there is no pipe
        if not pipe:
            redirect = self._get_redirect(stdin)
        else:
            redirect = None

        # Prepare stdin
        stdin = " ".join(stdin)

        # Set buffer flag
        if '%' in option:
            buffer = False
        else:
            buffer = True

        # Set pipe_out
        if pipe or redirect:
            pipe_out = []
        else:
            pipe_out = None

        # try pipe_in if input is empty
        if not stdin and "pipe_in" in kwargs:
            stdin = kwargs["pipe_in"]

        # check arguments
        if not stdin:
            await self.bot.say("Usage: `" + ctx.prefix + "cat [options] [input]`"
                                                         "\n\nType `" + ctx.prefix + "cat` for more information.")
            return

        # parse input
        if self.url_pattern.match(stdin):
            # url resource
            if 'p' in option:
                stdin = await self._get_url(stdin, "pretty")
                stdin = stdin.splitlines()
            elif '@' in option:
                stdin = await self._get_url(stdin, "raw")
                stdin = stdin.splitlines()
            else:
                stdin = await self._get_url(stdin, "visible")
        elif stdin.lower() == "@chat":
            # chat log
            stdin = await self._get_chat(ctx)
            if stdin is None:
                return
            stdin = stdin.splitlines()
        else:
            # user input
            stdin = stdin.splitlines()

        # do cat
        line_b = 0  # line number for 'b' option
        line_n = 0  # line number for 'n' option
        display_count = 0  # number of lines said to chat
        prev_empty = False  # keep track of previous line for 's' option
        line_num = None  # Important that this is set to None at start
        num_width = len(str(len(stdin)))
        for line in stdin:
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
        await self._pipe(ctx, pipe, pipe_out, redirect)

    @commands.command(pass_context=True, name='tac')
    async def tac(self, ctx, *args, **kwargs):
        """Echoes input to output in reverse by line or user specified separator"""
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
        stdin = []
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
                stdin.append(arg)
        self._split_option(option)

        # Only look for redirected stdout if there is no pipe
        if not pipe:
            redirect = self._get_redirect(stdin)
        else:
            redirect = None

        # Prepare stdin
        stdin = " ".join(stdin)

        # Set buffer flag
        if '%' in option:
            buffer = False
        else:
            buffer = True

        # Set pipe_out
        if pipe or redirect:
            pipe_out = []
        else:
            pipe_out = None

        # try pipe_in if input is empty
        if not stdin and "pipe_in" in kwargs:
            stdin = kwargs["pipe_in"]

        # check arguments
        if not stdin:
            await self.bot.say("Usage: `" + ctx.prefix + "tac [options] [input]`"
                                                         "\n\nType `" + ctx.prefix + "tac` for more information.")
            return

        # parse input
        if self.url_pattern.match(stdin):
            # url resource
            if 'p' in option:
                stdin = await self._get_url(stdin, "pretty")
            elif '@' in option:
                stdin = await self._get_url(stdin, "raw")
            else:
                input_texts = await self._get_url(stdin, "visible")
                stdin = "\n".join([line for line in input_texts])
        elif stdin.lower() == "@chat":
            # chat log
            stdin = await self._get_chat(ctx)
            if stdin is None:
                return
        else:
            # user input
            pass

        # split input
        if option_sep:
            if 'r' in option:
                separator = re.compile(r"{0}".format(option_sep))
                stdin = separator.split(stdin)
            else:
                stdin = stdin.split(option_sep)
        else:
            stdin = stdin.splitlines()

        # do cat (on reversed string)
        display_count = 0
        for line in reversed(stdin):
            result = await self._say(line, display_count, ctx.message.author, True, buffer,
                                     pipe_out=pipe_out)
            if result == -1:
                await self._flush_buffer(display_count, ctx.message.author, True, buffer, False)
                return
            display_count += result

        # flush buffer
        await self._flush_buffer(display_count, ctx.message.author, True, buffer, True)

        # handle pipe
        await self._pipe(ctx, pipe, pipe_out, redirect)

    @commands.command(pass_context=True, name='sed')
    async def sed(self, ctx, *args, **kwargs):
        """A simple stream editor"""
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
        stdin = []
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
                stdin.append(arg)
        self._split_option(option)

        # Only look for redirected stdout if there is no pipe
        if not pipe:
            redirect = self._get_redirect(stdin)
        else:
            redirect = None

        # Prepare stdin
        stdin = " ".join(stdin)

        # Set buffer flag
        if '%' in option:
            buffer = False
        else:
            buffer = True

        # Set pipe_out
        if pipe or redirect:
            pipe_out = []
        else:
            pipe_out = None

        # try pipe_in if input is empty
        if not stdin and "pipe_in" in kwargs:
            stdin = kwargs["pipe_in"]

        # check arguments
        if not script:
            await self.bot.say("Script command not found."
                               "\nUsage: `" + ctx.prefix + "sed [options] [script] [input]`"
                                                           "\n\nType `" + ctx.prefix + "sed` for more information.")
            return
        if not stdin:
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
                await self._say("Error trying to create substitution pattern: `{0}`".format(match.group(1)), 0,
                                ctx.message.author, False, False)
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
                await self._say("Extra characters after command: `{0}`".format(command), 0, ctx.message.author, False,
                                False)
                return
        elif command == 'p':
            if len(script) > 1:
                await self._say("Extra characters after command: `{0}`".format(command), 0, ctx.message.author, False,
                                False)
                return

        if command == 's':
            if acis_line[0] != '/' or acis_line.count('/') < 3:
                await self._say("Unknown substitution pattern: `{0}`".format(command), 0, ctx.message.author, False,
                                False)
                return
            sub = re.compile(r"^(.*?)/(?<!\\/)(.*?)/(?<!\\/)(.*)").match(acis_line[1:])
            if len(sub.groups()) != 3:
                await self._say("Unknown substitution pattern: `{0}`".format(command), 0, ctx.message.author, False,
                                False)
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
                await self._say("Error trying to create substitution pattern: `{0}`".format(command), 0,
                                ctx.message.author, False, False)
                return
        elif command == '=':
            if len(script) > 1:
                await self._say("Extra characters after command: `{0}`".format(command), 0, ctx.message.author, False,
                                False)
                return

        # await self.bot.say("command: " + command)

        # parse input
        if self.url_pattern.match(stdin):
            # url resource
            if 'p' in option:
                stdin = await self._get_url(stdin, "pretty")
                if 'g' in option:
                    stdin = [stdin]
                else:
                    stdin = stdin.splitlines()
            elif '@' in option:
                stdin = await self._get_url(stdin, "raw")
                if 'g' in option:
                    stdin = [stdin]
                else:
                    stdin = stdin.splitlines()
            else:
                stdin = await self._get_url(stdin, "visible")
                if 'g' in option:
                    input_string = "\n".join([line for line in stdin])
                    stdin = [input_string]
        elif stdin.lower() == "@chat":
            # chat log
            stdin = await self._get_chat(ctx)
            if stdin is None:
                return
            if 'g' in option:
                stdin = [stdin]
            else:
                stdin = stdin.splitlines()
        else:
            # user input
            if 'g' in option:
                stdin = [stdin]
            else:
                stdin = stdin.splitlines()

        # fix up address
        if address_type in ("range", "step"):
            if address[0] == '$':
                address[0] = len(stdin)
            else:
                address[0] = int(address[0])
            if address[1] == '$':
                address[1] = len(stdin)
            else:
                address[1] = int(address[1])
        elif address_type == "line":
            if address == '$':
                address = len(stdin)
            else:
                address = int(address)
        if (address_type == "range") and (address[0] >= address[1]):
            address_type = "line"
            address = address[0]

        # do sed
        display_count = 0
        sub_match = False
        for i, line in enumerate(stdin):
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
                    result = await self._say(acis_line, display_count, ctx.message.author, True, buffer,
                                             pipe_out=pipe_out)
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
                    result = await self._say(str(line_num), display_count, ctx.message.author, True, buffer,
                                             pipe_out=pipe_out)
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
                        result = await self._say(line, display_count, ctx.message.author, True, buffer,
                                                 pipe_out=pipe_out)
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
                    result = await self._say(acis_line, display_count, ctx.message.author, True, buffer,
                                             pipe_out=pipe_out)
                    if result == -1:
                        await self._flush_buffer(display_count, ctx.message.author, True, buffer, False)
                        return
                    display_count += result

            # reset sub_match
            sub_match = False

        # flush buffer
        await self._flush_buffer(display_count, ctx.message.author, True, buffer, True)

        # handle pipe
        await self._pipe(ctx, pipe, pipe_out, redirect)

    async def message_logger(self, message):
        """Log message - Credit https://github.com/tekulvw/Squid-Plugins"""
        # Do not log if logging is disabled for channel
        if message.channel.id not in self.config or not self.config[message.channel.id]["active"]:
            return
        # Do not log if message from bot and log_bot disabled
        if message.author == self.bot.user and not self.config[message.channel.id]["log_bot"]:
            return
        # Log message
        self.log(message)

    async def message_edit_logger(self, before, after):
        """Log message edits - Credit https://github.com/tekulvw/Squid-Plugins"""
        new_message = copy.deepcopy(after)
        new_content = ("EDIT:\nBefore: {}\nAfter: {}".format(before.clean_content, after.clean_content))
        new_message.content = new_content
        await self.message_logger(new_message)

    def log(self, message):
        """Write log to disk"""
        sid = message.server.id
        cid = message.channel.id

        # Get log file path
        folder = os.path.join(self.base_dir, sid)
        if not os.path.exists(folder):
            os.mkdir(folder)
        file = os.path.join(folder, cid)

        # Resize if needed
        try:
            size = os.path.getsize(file)
            if size > self.config[cid]["max_size"]:
                bytes = self.config[cid]["max_size"] * -1 + self.log_buffer
                with open(file, mode='rb+') as f:
                    f.seek(bytes, os.SEEK_END)
                    data = f.read()
                    f.seek(0)
                    f.write(data)
                    f.truncate()
        except:
            # log file not created yet
            pass

        # Write log
        with open(file, encoding="utf-8", mode='a') as f:
            timestamp = message.timestamp.replace(tzinfo=timezone.utc).astimezone(tz=None)
            timestamp = str(timestamp)[:19]
            message = ("{0} @{1.name}#{1.discriminator}: {2}\n".format(
                timestamp, message.author, message.clean_content))
            f.write(message)

    def _clog_set(self, cid, **kwargs):
        """Set config options and save"""

        if cid not in self.config:
            self.config[cid] = self.config_default

        for k, v in kwargs.items():
            self.config[cid][k] = v
        dataIO.save_json(self.config_path, self.config)

    def _size(self, num):
        for unit in ["Bytes", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB", "ZiB"]:
            if abs(num) < 1024.0:
                return "%3.1f %s" % (num, unit)
            num /= 1024.0
        return "%.1f %s" % (num, "YiB")


def check_folders():
    if not os.path.exists(GNU.base_dir):
        print("Creating " + GNU.base_dir + " folder...")
        os.makedirs(GNU.base_dir)


def check_files():
    if not dataIO.is_valid_json(GNU.config_path):
        print("Creating empty " + GNU.config_path + " ...")
        dataIO.save_json(GNU.config_path, {})


def setup(bot):
    if soupAvailable:
        check_folders()
        check_files()
        n = GNU(bot)
        bot.add_listener(n.message_logger, 'on_message')
        bot.add_listener(n.message_edit_logger, 'on_message_edit')
        bot.add_cog(n)
    else:
        raise RuntimeError("You need to run `pip3 install beautifulsoup4`")
