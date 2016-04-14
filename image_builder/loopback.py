import image_builder as ib
import subprocess
import os
import sys

@ib.buildcmd()
@ib.buildcmd_name("loopback.init")
class init(object):
    def run(self, s, image, offset=0, size=-1, partscan=False):
        self.image = image
        cmd = ['losetup', '--offset', '%d' % offset, '--show', '--find']
        if partscan:
            cmd = cmd + ['--partscan']
        if size > 0:
            cmd = cmd + ['--sizelimit', '%d' % size]
        cmd = cmd + [self.image]

        with subprocess.Popen(cmd, stdout=subprocess.PIPE) as proc:
            lo = proc.stdout.readline().decode('utf-8')
        lo = lo.replace("\r", "").replace("\n", "").lstrip().rstrip()
        if os.path.exists(lo):
            self.device = lo
        else:
            raise BuilderError("Can't find loopback device: %s" % lo)
        s.debug("Using loopback device: %s", self.device)

    def cleanup(self, s):
        s.debug("Detaching loopback device: %s", self.device)
        ret = ib.subprocess(s, ["losetup", "-d", self.device]).returncode
        if ret != 0:
            s.warning("losetup detach returned %d", ret)
