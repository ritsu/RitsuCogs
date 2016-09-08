# RitsuCogs

Some custom cogs for Red-DiscordBot

## GNU

An attempt to emulate some common GNU utilities

### grep

<i>grep</i> prints lines that contain a match for a pattern.

```grep [options] [pattern] [input]```
```
Matching Options
    -i      Ignore case distinctions, so that characters that differ only in case match each other.
    -w      Select only those lines containing matches that form whole words.
    -v      Invert the sense of matching, to select non-matching lines.
    -r      Treats search string as a regex pattern; other Matching Options are ignored.

Input Options
    -s      If input is a URL, this will treat the URL content as plain text instead of a DOM

Output Options
    -c      Suppress normal output; instead print a count of matching lines for each input file.
    -n      Prefix each line of output with its line number.
    -m num  Stop reading from input after num matching lines.

Input
    URL     If input matches a URL pattern, bot will fetch URL content as input.
            By default, DOM will be parsed from URL content and text elements will be treated as "lines"
            If -s option is set, URL content will be treated as plain text.
    @chat   If '@chat' is specified as the input, will search in chat log.
            Logging must be activated in the channel for this to work.
    <input> If none of the previous inputs are detected, remaining text is treated as input.
            To preserve whitespace (including newlines), enclose entire input in quotes.
```

### wc

<i>wc</i> counts the number of characters, whitespace-separated words, and newlines in the given input.

```wc [option] [input]```
```
Options
    -m      Print only the character counts.
    -w      Print only the word counts.
    -l      Print only the newline counts.

Input
    URL     If input matches a URL pattern, will attempt to fetch URL content.
            URL content is treated as plain text; DOM is never parsed.
    @chat   If '@chat' is specified as the input, will search in chat log.
            Logging must be activated in the channel for this to work.
    <input> If none of the previous inputs are detected, remaining text is treated as input.
            To preserve whitespace (including newlines), enclose entire input in quotes.
```

## TokyoTosho

### Get search results in your discord channel

`!tt search <terms> <#type>`

<b>terms</b> are normal searech terms. Prepend a "-" for exclusion terms.  
<b>type</b> (optional) is one of the types/categories defined on TokyoTosho. Type `!tt types` to see a list of valid types.

Example: `!tt search madoka rebellion -dub #anime`

### Show RSS alerts in your discord channel

`!tt add <terms> <#types>`

Adds an alert to your channel. The bot will display torrent name and link when a new torrent matching the configured <b>terms</b> and <b>types</b> (optional) appears in TokyoTosho's RSS feed. Note you can specify multiple types for RSS alerts.

Example: `!tt add shokugeki 1080 -raw #anime`

### Manage RSS alerts

`!tt list`

Lists existing alerts configured for your channel.

`!tt check`

Checks existing alerts against the current RSS feed. The RSS feed only contains the last 150 items, so old items will not appear.

`!tt remove <terms> <#types>`

Removes alerts matching (exactly) the specified <b>terms</b> and <b>types</b> if they exist in your channel. If no matching alerts are found, nothing happens.
