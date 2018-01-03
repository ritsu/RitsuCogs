# RitsuCogs

A small collection of cogs for [Red-DiscordBot](https://github.com/Cog-Creators/Red-DiscordBot). If you need 
help or have questions that are not answered here, visit the official 
[Red Cogs Support server](a href="https://discord.gg/SzUq8fy") and mention _@kagami#6142_.

## Quick start
1. Install repo: ```[p]cog repo add RitsuCogs https://github.com/ritsu/RitsuCogs```
2. Install cog:  ```[p]cog install RitsuCogs COGNAME```

## Contents
- [What's new](#whats-new)
- [CommnandSearch](#commandsearch)
- [GNU](#gnu)
- [Helpless](#helpless)
- [Pick](#pick)
- [SysInfo](#sysinfo)
- [Tokyotosho](#tokyotosho)

## What's new
- 2018-01-03: New year, new README. Also added [helpless](#helpless) which filters help messages based on 
[Squid-Plugins Permissions](https://github.com/tekulvw/Squid-Plugins).


## CommandSearch
Lets you search for commands on your bot.

### Commands
- **cmds** lists all commands on your bot that contain `search_string`. 
    ```
    [p]commandsearch|cmds|coms <search_string>
    ```

## GNU
An attempt to emulate some common GNU utilities. 

### Input and Output
All commands accept input from the following:

- Website content if a valid URL is specified
- Chat log if @chat is specified (Chat log must be enabled for the channel, e.g. `!clog on`)
- Any text following the command if none of the above are detected.

The following options for input and output apply to all non-administrative commands:

```
Global Options
    -p       If input is a URL, this will treat the URL content as (prettified) html instead of a DOM.
    -@       Same as -p except source is not passed through BeautifulSoup's prettify().
    -%       Print each line as a separate message; more likely to hit Discord's 5/5 rate limit.
```

Chat log options can be configured with the <b>clog</b> command.

### Pipes
Output from one GNU command can be piped to the input of another GNU command. Does not work with non-GNU commands.

```[p]sed "s/^.{0,20}$//" http://news.google.com | grep -i apple | sed s/apple/Orange/i | tail -n 5```

Prefix is optional for commands that appear after a pipe. 

### Redirected output
Output can be redirected to [pastebin](http://pastebin.com/) instead of Discord chat with one of the following:

- `> paste_title` creates a 24 hr pastebin  
- `>> paste_title` creates a permanent pastebin  

A link to the generated pastebin will be posted in chat. When used with pipes, the redirect must appear at the end.

```[p]cat -b http://news.google.com | grep -rm 10 .{40,} > somenews```

A <a href="http://pastebin.com/api">pastebin API key</a> is required for this feature. Save the API key with the command:

```[p]pastebin [api_key]```

### Commands
- **grep** prints lines that contain a match for a pattern.
    ```
    grep [options] [pattern] [input]
    
    Matching Options
        -i       Ignore case distinctions, so that characters that differ only in case match each other.
        -w       Select only those lines containing matches that form whole words.
        -v       Invert the sense of matching, to select non-matching lines.
        -r       Treats search string as a regex pattern; other Matching Options are ignored.
    
    Output Options
        -c       Suppress normal output; instead print a count of matching lines for each input file.
        -n       Prefix each line of output with its line number.
        -m num   Stop reading from input after num matching lines.
        -A num   Print num lines of trailing context after matching lines.
        -B num   Print num lines of leading context before matching lines.
        -C num   Print num lines of leading and trailing context.
    ```

- **sed** is a simple stream editor.
    ```
    sed [options] [script] [input]
    
    Options
        -g       Process entire input as a single string, rather than line by line.
        -n       Disable automatic printing; only produce output when explicitly told to.
    
    Script Address
        /.../    Returns lines that match the regular expression.
        A        Returns line number A.
        A,B      Returns lines from A to B.
        A~N      Returns every Nth line, starting from A
    
    Script Command
        a...     Append after each line.
        c...     Change lines with new line.
        d        Delete lines.
        i...     Insert before each line.
        p        Print line.
        s/././   Substitute with regular expression pattern.
        =        Print line number.
    
    Script Pattern Flag
        /i       Ignore case
        /p       Print (mostly used when -n option is active)
    ```

- **wc** counts the number of characters, whitespace-separated words, and newlines in the given input.
    ```
    wc [option] [input]
    
    Options
        -m      Print only the character counts.
        -w      Print only the word counts.
        -l      Print only the newline counts.
    ```

- **cat** echoes the contents of the input.
    ```
    cat [options] [input]
    
    Options
        -b      Number all nonempty output lines, starting with 1.
        -n      Number all output lines, starting with 1. This option is ignored if -b is in effect.
        -s      Suppress repeated adjacent blank lines; output just one empty line instead of several.
    ```

- **tac** echoes input to output in reverse by line or user specified separator.
    ```
    tac [options] [input]
    
    Options
        -s sep  Use "sep" as the record separator, instead of newline.
        -r      Treat the separator string as a regular expression.
    ```

- **tail** prints the last part (10 lines by default) of input.
    ```
    tail [options] [input]
    
    Options
        -n [+]num   Output the last num lines. However, if num is prefixed with a '+'
                    start printing with line num from the start of input, instead of from the end.
    ```

## Helpless
Hides help messages for commands users do not have permissions for based on 
[Squid-Plugins Permissions](https://github.com/tekulvw/Squid-Plugins). This works for `[p]help` and `[p]help COMMAND` 
when typed in a channel. This does not affect `[p]help` typed in DMs. If you are the bot owner, you will not notice any 
difference because you always have permissions for everything. If [Permissions](https://github.com/tekulvw/Squid-Plugins) 
is not enabled, this cog does _nothing_.

### Commands
- **helpless on** turns on help filtering.
    ```
    helpless on
    ```

- **helpless off** turns off help filtering.
    ```
    helpless off
    ```

## Pick
Pick random users from your channel. Use this to perform giveaways, raffles, and other types of contests. This can 
instantly pick from members currently in channel, or create an "event" users can enter by typing a keyword in chat.

### Commands
- **pick** will pick random users instantly from the channel (ignores bots).
    ```
    pick [num] +[role] -[role] +[status] -[status]
    
    num       Number of users to pick (default is 1)
    +role     Users must have at least one of these roles
    -role     Users cannot have any of these roles
    +status   Users must have at least one of these statuses
    -status   Users cannot have any of these statuses
      
    Examples  pick 2
              pick 3 +mod +online
              pick 3 +sub +patreon -mod -admin -offline -invisible
    ```

- **pickfor** creates a _pick event_ that users can enter by typing the name of the event in chat.
    ```
    pickfor <event> <duration> [num] +[role] -[role]
    
    event     Name of the event
    duration  How long event will last before bot picks winners
              Duration is any number followed by 's', 'm', or 'h'
    num       Number of users to pick (default is 1)
    +role     Users must have at least one of these roles
    -role     Users cannot have any of these roles
    
    Examples  pickfor raffle 60s 2
              pickfor giveaway 24h 3
              pickfor myteam 2m 4 +mod +sub
    ```

- **pickfrom** will pick from a list of names typed in the command
    ```
    pickfrom <names> [num]
    
    names     Names to pick from
    num       Number of names to pick
    
    Examples  pickfrom a b c     (Pick 1 from a, b, c)
              pickfrom a b c 2   (Pick 2 from a, b, c)
    ```

- **picks check** will DM you if you are entered into any pick events.
    ```
    picks check
    ```
    
- **picks delete** will delete a pick event you created.
    ```
    picks delete <name> [channel]
    
    name      Name of event
    channel   Channel event is in (optional)
    
    Examples  picks delete giveaway
              picks delete giveaway #contests
    ```
    
- **picks force** will force the bot to pick for an event you created (and end the event).
    ```
    picks force <name> [channel]
    
    name      Name of event
    channel   Channel event is in (optional)
       
    Examples  picks force giveaway
              picks force giveaway #contests
    ```
    
- **picks list** will list all currently running pick events on the server.
    ```
    picks list
    ```
    
- **picks show** will show details about a pick event
    ```
    picks show <name> [channel]

    name      Name of event
    channel   Channel event is in (optional)
    
    Examples  picks show giveaway
              picks show giveaway #contests
    ```
    
## SysInfo
A set of commands that display system information for the machine running the bot. Note that some of these commands 
may not not be available depending on your system environment.

Will also install [psutil](https://pypi.python.org/pypi/psutil), which is used to retrieve system information. If this 
does not happen automatically, you can manually install it with `pip3 install psutil`

### Commands
- **sys info** displays a summary of cpu, memory, disk and network information.
    ```
    sys info
    ```

- **sys df** shows file system disk space usage, similar to "df -h" on linux.
    ```
    sys df
    ```

- **sys free** shows the amount of free and used memory in the system, similar to "free" on linux.
    ```
    sys free
    ```

- **sys ifconfig** shows network interface information, similar to "ifconfig" on linux.
    ```
    sys ifconfig
    ```

- **sys iotop** shows I/O usage information output by the kernel, like a snapshot of "iotop" on linux.
    ```
    sys iotop
    ```

- **sys meminfo** shows system memory information.
    ```
    sys meminfo
    ```

- **sys netstat** shows information about the networking subsystem, similar to "netstat -antp" on linux.
    ```
    sys netstat
    ```

- **sys nettop** shows a snapshot of real-time network statistics.
    ```
    sys nettop
    ```

- **sys mem** shows physical memory usage, taking shared memory pages into account, similar to "smem" on linux.
    ```
    sys smem
    ```

- **sys ps** shows information about active processes, similar to "ps -aux" on linux.
    ```
    sys ps
    ```

- **sys top** shows real-time system information and tasks, like a snapshot of "top" on linux.
    ```
    sys top
    ```

- **sys who** shows which users are currently logged in, similar to "who" on linux
    ```
    sys who
    ```

## TokyoTosho
Allows you to search [TokyoTosho](https://www.tokyotosho.info/) from discord and configure custom RSS alerts that 
notify you when new torrents matching user defined criteria appear on the site.

Will also install [js2py](https://pypi.python.org/pypi/Js2Py) to access TokyoTosho behind CloudFlare. If this does not 
happen automatically, you can manually install it with `pip3 install js2py`

### Commands
- **tt search** will search for torrents based on search terms and category.
    ```
    tt search <terms> [#category]
    
    terms      Regular search strings. Use '-' to exclude terms.
    category   One of the categories defined on TokyoTosho.
               Type '[p]tt cats' to see a list of valid categories.
    
    Examples   tt search horriblesubs madoka 1080
               tt search madoka rebellion -dub #anime
               tt search madoka #music
    ```

- **tt add** will add an RSS alert to your channel. The bot will display torrent name and link when a new torrent 
matching the configured `terms` and `categories` (optional) appears in TokyoTosho's RSS feed. Note you can specify 
    ```
    tt add <terms> [#categories]
    
    terms      Regular search strings. Use '-' to exclude terms.
    category   One of the categories defined on TokyoTosho.
               Type '[p]tt cats' to see a list of valid categories.
    
    Examples   tt add horriblesubs madoka 1080
               tt add madoka -horriblesubs -dub
               tt add madoka #anime #music
               tt add shokugeki 1080 -raw #anime
    ```

- **tt list** will lists existing alerts configured for your channel.
    ```
    tt list
    ```

- **tt check** will check existing alerts against the current RSS feed. The RSS feed only contains the last 150 items, 
so old items may not appear.
    ```
    tt check
    ```

- **tt remove** will remove alerts matching (exactly) the specified `terms` and `categories` if they exist in your 
channel. If no matching alerts are found, nothing happens.
    ```
    tt remove [terms] [#categories]
    ```

- **tt set** is used for configuring various options for the cog.
    ```
    tt set [option] [value]
    
    OPTIONS
        check_interval      Number of seconds between RSS updates
        comment_length      Max length of search result and RSS feed comments
        ignore              List of categories that are ignored in all search and RSS alerts
        items_per_message   Max number of items the bot will mention in one message
    ```
