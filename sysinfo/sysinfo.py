from discord.ext import commands
from cogs.utils import checks
import asyncio
import os
from datetime import datetime

try:
    import psutil
except Exception as e:
    raise RuntimeError("You must run `pip3 install psutil` to use this cog") from e


class SysInfo:
    """Display CPU, Memory, Disk and Network information"""

    options = ('cpu', 'memory', 'file', 'disk', 'network', 'boot')

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='sysinfo')
    @checks.is_owner()
    async def psutil(self, *args: str):
        """Show CPU, Memory, Disk, and Network information

         Usage: sysinfo [option]

         Examples:
             sysinfo           Shows all available info
             sysinfo cpu       Shows CPU usage
             sysinfo memory    Shows memory usage
             sysinfo file      Shows full path of open files
             sysinfo disk      Shows disk usage
             sysinfo network   Shows network usage
             sysinfo boot      Shows boot time
         """

        # CPU
        cpu_count_p = psutil.cpu_count(logical=False)
        cpu_count_l = psutil.cpu_count()
        if cpu_count_p is None:
            cpu_count_p = "N/A"
        cpu_cs = ("CPU Count"
                  "\n\t{0:<9}: {1:>3}".format("Physical", cpu_count_p) +
                  "\n\t{0:<9}: {1:>3}".format("Logical", cpu_count_l))        
        psutil.cpu_percent(interval=None, percpu=True)
        await asyncio.sleep(1)
        cpu_p = psutil.cpu_percent(interval=None, percpu=True)
        cpu_ps = ("CPU Usage"
                  "\n\t{0:<8}: {1}".format("Per CPU", cpu_p) +
                  "\n\t{0:<8}: {1:.1f}%".format("Overall", sum(cpu_p)/len(cpu_p)))
        cpu_t = psutil.cpu_times()
        width = max([len("{:,}".format(int(n))) for n in [cpu_t.user, cpu_t.system, cpu_t.idle]])
        cpu_ts = ("CPU Times"
                  "\n\t{0:<7}: {1:>{width},}".format("User", int(cpu_t.user), width=width) +
                  "\n\t{0:<7}: {1:>{width},}".format("System", int(cpu_t.system), width=width) +
                  "\n\t{0:<7}: {1:>{width},}".format("Idle", int(cpu_t.idle), width=width))

        # Memory
        mem_v = psutil.virtual_memory()
        width = max([len(self._size(n)) for n in [mem_v.total, mem_v.available, (mem_v.total - mem_v.available)]])
        mem_vs = ("Virtual Memory"
                  "\n\t{0:<10}: {1:>{width}}".format("Total", self._size(mem_v.total), width=width) +
                  "\n\t{0:<10}: {1:>{width}}".format("Available", self._size(mem_v.available), width=width) +
                  "\n\t{0:<10}: {1:>{width}} {2}%".format("Used", self._size(mem_v.total - mem_v.available),
                                                          mem_v.percent, width=width))
        mem_s = psutil.swap_memory()
        width = max([len(self._size(n)) for n in [mem_s.total, mem_s.free, (mem_s.total - mem_s.free)]])
        mem_ss = ("Swap Memory"
                  "\n\t{0:<6}: {1:>{width}}".format("Total", self._size(mem_s.total), width=width) +
                  "\n\t{0:<6}: {1:>{width}}".format("Free", self._size(mem_s.free), width=width) +
                  "\n\t{0:<6}: {1:>{width}} {2}%".format("Used", self._size(mem_s.total - mem_s.free),
                                                         mem_s.percent, width=width))

        # Open files
        open_f = psutil.Process().open_files()
        open_fs = "Open File Handles\n\t"
        if open_f:
            if hasattr(open_f[0], "mode"):
                open_fs += "\n\t".join(["{0} [{1}]".format(f.path, f.mode) for f in open_f])
            else:
                open_fs += "\n\t".join(["{0}".format(f.path) for f in open_f])
        else:
            open_fs += "None"

        # Disk usage
        disk_u = psutil.disk_usage(os.path.sep)
        width = max([len(self._size(n)) for n in [disk_u.total, disk_u.free, disk_u.used]])
        disk_us = ("Disk Usage"
                   "\n\t{0:<6}: {1:>{width}}".format("Total", self._size(disk_u.total), width=width) +
                   "\n\t{0:<6}: {1:>{width}}".format("Free", self._size(disk_u.free), width=width) +
                   "\n\t{0:<6}: {1:>{width}} {2}%".format("Used", self._size(disk_u.used),
                                                          disk_u.percent, width=width))

        # Network
        net_io = psutil.net_io_counters()
        width = max([len(self._size(n)) for n in [net_io.bytes_sent, net_io.bytes_recv]])
        net_ios = ("Network"
                   "\n\t{0:<11}: {1:>{width}}".format("Bytes sent", self._size(net_io.bytes_sent), width=width) +
                   "\n\t{0:<11}: {1:>{width}}".format("Bytes recv", self._size(net_io.bytes_recv), width=width))

        # Boot time
        boot_s = ("Boot Time"
                  "\n\t{0}".format(datetime.fromtimestamp(
                       psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S")))

        # Output
        if not args or args[0].lower() not in self.options:
            await self.bot.say("```\n" +
                               "\n\n".join([cpu_cs, cpu_ps, cpu_ts, mem_vs, mem_ss, open_fs, disk_us, net_ios, boot_s]) +
                               "```")
        elif args[0].lower() == 'cpu':
            await self.bot.say("```\n" + "\n\n".join([cpu_cs, cpu_ps, cpu_ts]) + "```")
        elif args[0].lower() == 'memory':
            await self.bot.say("```\n" + "\n\n".join([mem_vs, mem_ss]) + "```")
        elif args[0].lower() == 'file':
            await self.bot.say("```\n" + open_fs + "```")
        elif args[0].lower() == 'disk':
            await self.bot.say("```\n" + disk_us + "```")
        elif args[0].lower() == 'network':
            await self.bot.say("```\n" + net_ios + "```")
        elif args[0].lower() == 'boot':
            await self.bot.say("```\n" + boot_s + "```")

        return

    def _size(self, num):
        for unit in ["Bytes", "KB", "MB", "GB", "TB", "PB", "EB", "ZB"]:
            if abs(num) < 1024.0:
                return "{0:.1f}{1}".format(num, unit)
            num /= 1024.0
        return "{0:.1f}{1}".format(num, "YB")


def setup(bot):
    n = SysInfo(bot)
    bot.add_cog(n)
