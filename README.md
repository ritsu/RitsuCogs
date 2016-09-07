# RitsuCogs

Some custom cogs for Red-DiscordBot

## TokyoTosho

### Get search results in your discord channel

`!tt search <terms> <types>`

<b>terms</b> are normal searech terms. Prepend a "-" for exclusion terms.  
<b>types</b> (optional) are the types/categories defined on TokyoTosho. Type `!tt types` to see a list of valid types.

Example: `!tt search madoka rebellion -dub #anime`

### Show RSS alerts in your discord channel

`!tt add <terms> <types>`

Adds an alert to your channel. The bot will display torrent name and link when a new torrent matching the configured <b>terms</b> and <b>types</b> (optional) appears in TokyoTosho's RSS feed.

Example: `!tt add shokugeki 1080 -raw #anime`

### Manage RSS alerts

`!tt list`

Lists existing alerts configured for your channel.

`!tt check`

Checks existing alerts against the current RSS feed. The RSS feed only contains the last 150 items, so old items will not appear.

`!tt remove <terms> <types>`

Removes alerts matching (exactly) the specified <b>terms</b> and <b>types</b> if they exist in your channel. If no matching alerts are found, nothing happens.
