# RitsuCogs

Some custom cogs for Red-DiscordBot

## GNU

An attempt to emulate some common GNU utilities

### grep

<i>grep</i> prints lines that contain a match for a pattern.

```grep <options> <pattern> <input>```
```
Matching Options
    -i      Ignore case distinctions, so that characters that differ only in case match each other.
    -w      Select only those lines containing matches that form whole words.
    -v      Invert the sense of matching, to select non-matching lines.
    -r      Treats search string as a regex pattern. Other Matching Options are ignored.

Output Options
    -c      Suppress normal output; instead print a count of matching lines for each input file.
    -n      Prefix each line of output with its line number.
    -m num  Stop reading from input after num matching lines.

Input
    URL     If input matches a URL pattern, will attempt to fetch URL content.
            DOM text elements correspond to 'lines' in this context.
    @chat   If '@chat' is specified as the input, will search in chat log.
            Logging must be activated in the channel for this to work.
    <input> If none of the previous inputs are detected, remaining text is treated as raw input.
            Note: Discord chat messages are treated as a single line even if they include linebreaks.
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
