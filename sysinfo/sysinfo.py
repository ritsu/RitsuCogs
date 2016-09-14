from discord.ext import commands
from cogs.utils import checks
import asyncio
import os
from datetime import datetime

try:
    import psutil
    psutilAvailable = True
except:
    psutilAvailable = False

class sysinfo:
    """Display CPU, Memory, Disk, and Network information"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='sysinfo')
    @checks.is_owner()
    async def psutil(self):
        """Show CPU, Memory, Disk, and Network information"""

        # CPU
        cpu_cs = "CPU Count: {0} Physical, {1} Logical".format(psutil.cpu_count(), psutil.cpu_count(logical=False))
        psutil.cpu_percent(interval=None, percpu=True)
        await asyncio.sleep(1)
        cpu_ps = "CPU Usage: {0}".format(psutil.cpu_percent(interval=None, percpu=True))
        cpu_t = psutil.cpu_times()
        numlen = len(str(max([cpu_t.user, cpu_t.system, cpu_t.idle])))
        cpu_ts = ("CPU Times"
                  "\n\t{0:<7}: {1:>{width},}".format("User", int(cpu_t.user), width=numlen) +
                  "\n\t{0:<7}: {1:>{width},}".format("System", int(cpu_t.system), width=numlen) +
                  "\n\t{0:<7}: {1:>{width},}".format("Idle", int(cpu_t.idle), width=numlen))

        # Memory
        mem_v = psutil.virtual_memory()
        mem_vs = ("Virtual Memory"
                  "\n\t{0:<10}: {1:>6}".format("Total", self._size(mem_v.total)) +
                  "\n\t{0:<10}: {1:>6}".format("Available", self._size(mem_v.available)) +
                  "\n\t{0:<10}: {1:>6}".format("Used", str(mem_v.percent) + "%"))
        mem_s = psutil.swap_memory()
        mem_ss = ("Swap Memory"
                  "\n\t{0:<6}: {1:>6}".format("Total", self._size(mem_s.total)) +
                  "\n\t{0:<6}: {1:>6}".format("Free", self._size(mem_s.free)) +
                  "\n\t{0:<6}: {1:>6}".format("Used", str(mem_s.percent) + "%"))

        # Open files
        open_f = psutil.Process().open_files()
        common = os.path.commonpath([f.path for f in open_f])
        open_fs = "\n\t".join(["{0} [{1}]".format(f.path.replace(common, '.'), f.mode) for f in open_f])
        open_fs = "Open File Handles\n\t" + open_fs

        # Disk usage
        disk_u = psutil.disk_usage(os.path.sep)
        disk_us = ("Disk Usage"
                   "\n\t{0:<6}: {1:>8}".format("Total", self._size(disk_u.total)) +
                   "\n\t{0:<6}: {1:>8}".format("Free", self._size(disk_u.free)) +
                   "\n\t{0:<6}: {1:>8} {2}%".format("Used", self._size(disk_u.used), disk_u.percent))

        # Network
        net_io = psutil.net_io_counters()
        net_ios = ("Network:"
                   "\n\t{0:<11}: {1:>8}".format("Bytes sent", self._size(net_io.bytes_sent)) +
                   "\n\t{0:<11}: {1:>8}".format("Bytes recv", self._size(net_io.bytes_recv)))

        # Boot time
        boot_s = ("Boot Time: {0}".format(datetime.fromtimestamp(
                       psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S")))

        await self.bot.say("```" +
                           "\n\n".join([cpu_cs, cpu_ps, cpu_ts, mem_vs, mem_ss, open_fs, disk_us, net_ios, boot_s]) +
                           "```")

        return

    def _size(self, num):
        for unit in ["Bytes", "KB", "MB", "GB", "TB", "PB", "EB", "ZB"]:
            if abs(num) < 1024.0:
                return "{0:.1f}{1}".format(num, unit)
            num /= 1024.0
        return "{0:.1f}{1}".format(num, "YB")

def setup(bot):
    if psutilAvailable:
        n = sysinfo(bot)
        bot.add_cog(n)
    else:
        raise RuntimeError("You need to run 'pip3 install psutil'")
