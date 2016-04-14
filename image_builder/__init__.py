import enum
import os
import re
import atexit
import subprocess as sp
import logging
import time
import tempfile
import shutil
import sys
import atexit

import functools
import logging
import colorlog

IMAGE_SIZE = 1024*1024*512

class BuilderError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

class buildcmd(object):
    def __init__(self):
        pass

    def __call__(self, c):
        class buildcmd_wrapper(c):
            def __init__(self, builder, *args, **kwargs):
                super(buildcmd_wrapper, self).__init__()
                builder.run(self, *args, **kwargs)
        buildcmd_wrapper.__doc__ = c.__doc__
        buildcmd_wrapper.__name__ = c.__name__
        return buildcmd_wrapper

class buildcmd_flatten(object):
    def __init__(self):
        pass

    def __call__(self, c):
        c.buildcmd_flatten = True
        return c

class buildcmd_name(object):
    def __init__(self, name):
        self.name = name

    def __call__(self, c):
        c.buildcmd_name = self.name
        return c

class buildcmd_once(object):
    def __init__(self):
        pass

    def __call__(self, c):
        class buildcmd_once_wrapper(c):
            def run(self, builder, *args, **kwargs):
                if not hasattr(buildcmd_once_wrapper, 'buildcmd_once'):
                    super(buildcmd_once_wrapper, self).run(builder, *args, **kwargs)
                    buildcmd_once_wrapper.buildcmd_once = True
                    buildcmd_once_wrapper.buildcmd_flatten = True
        buildcmd_once_wrapper.__doc__ = c.__doc__
        buildcmd_once_wrapper.__name__ = c.__name__
        return buildcmd_once_wrapper

import image_builder.file
import image_builder.loopback

@buildcmd()
@buildcmd_flatten()
class check_subprocess(object):
    def run(self, s, cmd, *args, **kwargs):
        a = subprocess(s, cmd, *args, **kwargs)
        if a.returncode != 0:
            raise BuilderError("%s returned %d" % (cmd, a.returncode))

@buildcmd()
@buildcmd_flatten()
class subprocess(object):
    def run(self, s, cmd, *args, **kwargs):
        defaults = {"stdout": sys.stderr}
        defaults.update(kwargs)
        s.debug("Executing %s", cmd)
        with sp.Popen(cmd, *args, **kwargs) as proc:
            proc.wait()
            self.returncode = proc.returncode

@buildcmd()
class mkdtemp(object):
    def run(self, s, path=None):
        self.path = tempfile.mkdtemp(dir=path)
        s.debug("Created temporary directory %s", self.path)
    def cleanup(self, s):
        s.debug("Removing temporary directory %s", self.path)
        shutil.rmtree(self.path)

@buildcmd()
class empty_image(object):
    def run(self, s, path, size):
        self.path = path
        with open(self.path, "wb") as out:
            out.seek(size - 1)
            out.write(b'\0')

@buildcmd()
@buildcmd_flatten()
class mount(object):
    def run(self, s, fs_type, device, path, options = None):
        self._path = path
        cmd = ['mount', '-t', fs_type, device, path]
        if options:
            cmd.extend(['-o', options])

        check_subprocess(s, cmd)

    def cleanup(self, s):
        ret = subprocess(s, ['umount', self._path]).returncode
        if ret != 0:
            s.warning("umount returned %d", ret)

@buildcmd()
class extract_release(object):
    def run(self, s, src, dest):
        s.debug("Extracting %s to %s", src, dest)
        check_subprocess(s, ['tar', '-C', dest, '-zxf', src])

@buildcmd()
@buildcmd_once()
class check_fakeroot(object):
    def run(self, s):
        if os.geteuid() != 0:
            raise BuilderError("This script needs to be run with fakeroot!")

@buildcmd()
@buildcmd_once()
class check_root(object):
    def run(self, s):
        if os.geteuid() != 0:
            raise BuilderError("This script needs to be run as root!")

@buildcmd()
class download_git(object):
    def commit_to_path(self, commit):
        return re.sub("/", "_", commit)

    def run(self, s, name, url, commit, archive, temp_dir):
        directory = os.path.join(temp_dir, name)
        commit_path = self.commit_to_path(commit)
        archive_name = os.path.join(archive, "%s-%s.tar.gz" % (name, commit_path))
        if os.path.exists(archive_name):
            s.debug("Found archived git repository at %s", archive_name)
            check_subprocess(s, ['tar', '-C', temp_dir, '-zxf', archive_name])
        else:
            args=['git', 'clone']
            args.extend(['--no-checkout', url, directory])
            check_subprocess(s, args)
            check_subprocess(s, ['git', 'checkout', commit], cwd=directory)
            check_subprocess(s, ['git', 'fat', 'init'], cwd=directory)
            check_subprocess(s, ['git', 'fat', 'pull'], cwd=directory)
            check_subprocess(s, ['tar', '-C', temp_dir, '-zcf',
                                os.path.abspath(archive_name), name])

@buildcmd()
class new_image(object):
    def run(self, s):
        self.temp_dir = mkdtemp(s).path
        image = empty_image(s, os.path.join(self.temp_dir, "working.img"), IMAGE_SIZE).path
        lodevice = loopback.init(s, image).device
        mtd_device = mtd.from_block_dev(s, lodevice).device
        ubi.format(s, mtd_device)
        ubi_number = ubi.attach(s, mtd_device).ubi_number
        ubi.mkvol(s, ubi_number, "rootfs")
        self.mount_dir = os.path.join(self.temp_dir, "working")
        os.mkdir(self.mount_dir)
        ubi.mount(s, ubi_number, "rootfs", self.mount_dir)

@buildcmd()
@buildcmd_flatten()
class mount_disk_image(object):
    def run(self, s, img, mntdir, offset):
        lo_dev = loopback.init(s, img, offset).device
        mtd_dev = mtd.from_block_dev(s, lo_dev).device
        ubi_num = ubi.attach(s, mtd_dev).ubi_number
        ubi.mount(s, ubi_num, "rootfs", mntdir)

@buildcmd()
class mount_z2_image(object):
    def run(self, s, img, mntdir):
        mount_disk_image(s, img, mntdir, 0xe0000)

@buildcmd()
class mount_z4_image(object):
    def run(self, s, img, mntdir):
        mount_disk_image(s, img, mntdir, 0xe0000)

@buildcmd()
class mount_ubifs_image(object):
    def run(self, s, img, mntdir):
        disk_img = img + ".img"
        empty_image(s, disk_img, IMAGE_SIZE)
        lo_dev = loopback.init(s, disk_img).device
        mtd_dev = mtd.from_block_dev(s, lo_dev).device
        ubi.format(s, mtd_dev)
        ubi_number = ubi.attach(s, mtd_dev).ubi_number
        volume_number = ubi.mkvol(s, ubi_number, "rootfs").volume_number
        ubi.updatevol(s, ubi_number, volume_number, img)
        ubi.mount(s, ubi_number, "rootfs", mntdir)

@buildcmd()
class mount_image(object):
    def run(self, s, img, mntdir):
        retest = re.match(r"""^.*\.(.*)""", img)

        possible_error = BuilderError("Can't determine image type for %s" % img)

        if retest:
            extension = retest.group(1).lower()
            if extension == "img" or extension == "bin":
                statinfo = os.stat(img)
                if statinfo.st_size == 0x2000000:
                    mount_z2_image(s, img, mntdir)
                elif statinfo.st_size == 0x4000000:
                    mount_z4_image(s, img, mntdir)
                else:
                    raise possible_error
            elif extension == "ubifs":
                mount_ubifs_image(s, img, mntdir)
            else:
                raise possible_error
        else:
            raise possible_error

class builder(object):
    logger_init = False

    def __init__(self):
        self.buildcmd_count = {}
        self.buildcmd_stack = []
        self.exit_callbacks = []
        self.logger = logging.getLogger('image_builder')
        if not builder.logger_init:
            ch = logging.StreamHandler()
            ch.setFormatter(colorlog.ColoredFormatter(
                "%(log_color)s%(levelname)-8s%(reset)s %(message)s",
                datefmt=None,
                reset=True,
                log_colors={
                    'DEBUG':    'cyan',
                    'INFO':     'green',
                    'WARNING':  'yellow',
                    'ERROR':    'red',
                    'CRITICAL': 'red,bg_white',
                },
                style='%'))
            self.logger.addHandler(ch)
            self.logger.setLevel(logging.DEBUG)
            builder.logger_init = True
        self.in_exit = True

    def __enter__(self):
        self.in_exit = False
        return self

    def __exit__(self, type, value, traceback):
        self.in_exit = True
        for o in self.exit_callbacks:
            if not o._run_failed:
                self.info("Cleanup handler for %s", self.buildcmd_name(o))
                o.cleanup(self)
        self.exit_callbacks = []

    def buildcmd_name(self, o):
        if hasattr(o, 'buildcmd_name'):
            return o.buildcmd_name
        return o.__class__.__name__

    def register_exit_callback(self, o):
        if hasattr(o, 'cleanup'):
            if self.in_exit:
                self.error("Ran buildcmd %s with cleanup handler in __exit__, ignoring!", self.buildcmd_name(o))
            else:
                self.exit_callbacks.insert(0, o)

    def run(self, o, *args, **kwargs):
        name = self.buildcmd_name(o)

        wants_flatten = False
        if hasattr(o, 'buildcmd_flatten'):
            wants_flatten = o.buildcmd_flatten

        if not wants_flatten:
            self.info("Started %s {", name)
        self.buildcmd_stack.append((o, wants_flatten))

        ts = time.time()
        try:
            o._run_failed = True
            self.register_exit_callback(o)
            o.result = o.run(self, *args, **kwargs)
            o._run_failed = False
        except:
            self.error("Exception occurred during execution of %s", name)
            raise
        finally:
            te = time.time()
            self.buildcmd_stack.pop()
            if not wants_flatten:
                delta = te - ts
                if delta >= 0.01:
                    self.info("} (%2.2f seconds)", delta)
                else:
                    self.info("}")

        if name in self.buildcmd_count:
            self.buildcmd_count[name] += 1
        else:
            self.buildcmd_count[name] = 1

    def current_indent(self):
        stacksize = len([1 for o, flatten in self.buildcmd_stack if not flatten])
        return "    " * stacksize

    def debug(self, msg, *args, **kwargs):
        self.logger.debug(self.current_indent() + msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        self.logger.error(self.current_indent() + msg, *args, **kwargs)

    def critical(self, msg, *args, **kwargs):
        self.logger.critical(self.current_indent() + msg, *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        self.logger.info(self.current_indent() + msg, *args, **kwargs)

    def warn(self, msg, *args, **kwargs):
        self.logger.warn(self.current_indent() + msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        self.logger.warning(self.current_indent() + msg, *args, **kwargs)
