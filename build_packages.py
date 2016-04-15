#!/usr/bin/env python3

import image_builder as ib
import os
import sys
import pickle
import subprocess
import textwrap
import datetime
import shutil
import glob

OPJ = os.path.join

UBOOT_VER = "v2016.03"
UBOOT_URL = 'git://git.denx.de/u-boot.git'
LINUX_VER = "rpi-4.6.y"
LINUX_URL = "https://github.com/raspberrypi/linux"
LINUX_UPSTREAM_URL = "git://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git"
LINUX_STABLE_URL = "git://git.kernel.org/pub/scm/linux/kernel/git/stable/linux-stable.git"
FIRMWARE_VER = "master"
FIRMWARE_URL = "http://github.com/raspberrypi/firmware"

class GlobalBuildContext:
    pass

@ib.buildcmd()
@ib.buildcmd_flatten()
class check_git_run(object):
    def run(self, s, repo, cmd):
        ib.check_subprocess(s, ["git", "-C", repo] + list(cmd))

@ib.buildcmd()
@ib.buildcmd_flatten()
class git_run(object):
    def run(self, s, repo, cmd):
        self.returncode = ib.subprocess(s, ["git", "-C", repo] + list(cmd)).returncode

@ib.buildcmd()
class fetch_git_url(object):
    def run(self, s, repo, remote, url):
        if not os.path.isdir(repo):
            ib.check_subprocess(s, ['git', 'clone', '--bare', url, repo])
        if git_run(s, repo, [ 'remote', 'set-url', remote, url ]).returncode != 0:
            check_git_run(s, repo, [ 'remote', 'add', remote, url ])
        check_git_run(s, repo, [ 'fetch', remote ])

@ib.buildcmd()
class setup_gbc(object):
    def run(self, s):
        self.gbc = GlobalBuildContext()
        self.gbc.tmp = ib.mkdtemp(s, path=os.getcwd()).path
        self.gbc.repo = "repo"
        self.gbc.in_sudo = False
        self.gbc.in_fakeroot = False
        self.gbc.today = datetime.datetime.now().strftime("%Y%m%d%H%M")

        if not os.path.isdir(self.gbc.repo):
            os.mkdir(self.gbc.repo)

@ib.buildcmd()
class create_worktree(object):
    def run(self, s, from_repo, to_repo, head):
        self.from_repo = from_repo
        check_git_run(s, from_repo, [ 'worktree', 'add', '--detach',
                to_repo, head ])
    def cleanup(self, s):
        git_run(s, self.from_repo, [ 'worktree', 'prune', '-v', '--expire', 'now' ])

@ib.buildcmd()
class clone_linux(object):
    def run(self, s, gbc):
        gbc.linux_git = OPJ(gbc.repo, "linux.git")
        gbc.linux = OPJ(gbc.tmp, "linux")
        fetch_git_url(s, gbc.linux_git, "origin", LINUX_URL)
        fetch_git_url(s, gbc.linux_git, "upstream", LINUX_UPSTREAM_URL)
        fetch_git_url(s, gbc.linux_git, "stable", LINUX_STABLE_URL)
        create_worktree(s, gbc.linux_git, gbc.linux, LINUX_VER)
        check_git_run(s, gbc.linux, [ 'am', OPJ(os.getcwd(),
                'patches',
                '0001-Fix-deprecated-get_user_pages-page_cache_release.patch') ])

@ib.buildcmd()
class clone_firmware(object):
    def run(self, s, gbc):
        gbc.firmware_git = OPJ(gbc.repo, "firmware.git")
        gbc.firmware = OPJ(gbc.tmp, "firmware")
        gbc.firmware_deb_d = OPJ(gbc.tmp, 'firmware-deb')
        gbc.firmware_deb = OPJ(gbc.tmp, "raspberrypi-firmware-git-{0}-1_armhf.deb".format(gbc.today))
        fetch_git_url(s, gbc.firmware_git, "origin", FIRMWARE_URL)
        create_worktree(s, gbc.firmware_git, gbc.firmware, FIRMWARE_VER)

@ib.buildcmd()
class clone_uboot(object):
    def run(self, s, gbc):
        gbc.uboot_git = OPJ(gbc.repo, "u-boot.git")
        gbc.uboot = OPJ(gbc.tmp, "u-boot")
        gbc.uboot_deb_d = OPJ(gbc.tmp, 'u-boot-deb')
        gbc.uboot_deb = OPJ(gbc.tmp, "u-boot-git-{0}-1_armhf.deb".format(gbc.today))
        fetch_git_url(s, gbc.uboot_git, "origin", UBOOT_URL)
        create_worktree(s, gbc.uboot_git, gbc.uboot, UBOOT_VER)

@ib.buildcmd()
class compile_linux(object):
    def run(self, s, gbc):
        ib.check_subprocess(s, ['cp', 'linux-config', OPJ(gbc.linux, '.config')])
        ib.check_subprocess(s, ['make', '-C', gbc.linux, 'oldconfig'], stdin=subprocess.DEVNULL)
        ib.check_subprocess(s, ['make', '-j3', '-C', gbc.linux, 'deb-pkg'])

@ib.buildcmd()
class compile_uboot(object):
    def run(self, s, gbc):
        ib.check_subprocess(s, ['make', '-C', gbc.uboot, 'rpi_2_defconfig'])
        ib.check_subprocess(s, ['make', '-j3', '-C', gbc.uboot])

@ib.buildcmd()
class create_uboot_deb(object):
    def run(self, s, gbc):
        ib.file.install_dir(s, gbc.uboot_deb_d, 0, 0, 0o755)
        ib.file.install_dir(s, OPJ(gbc.uboot_deb_d, "boot"), 0, 0, 0o755)
        ib.file.install_dir(s, OPJ(gbc.uboot_deb_d, "boot", "firmware"), 0, 0, 0o755)
        ib.file.install_dir(s, OPJ(gbc.uboot_deb_d, "etc"), 0, 0, 0o755)
        ib.file.install_dir(s, OPJ(gbc.uboot_deb_d, "etc", "kernel"), 0, 0, 0o755)
        ib.file.install_dir(s, OPJ(gbc.uboot_deb_d, "etc", "kernel", "postinst.d"), 0, 0, 0o755)
        ib.file.install(s, OPJ("u-boot-deb", "zz-u-boot"),
                OPJ(gbc.uboot_deb_d, "etc", "kernel", "postinst.d", "zz-u-boot"), 0, 0, 0o755)
        ib.file.install(s, OPJ("u-boot-deb", "config.txt"),
                OPJ(gbc.uboot_deb_d, "boot", "firmware", "config.txt"), 0, 0, 0o644)
        ib.file.install_dir(s, OPJ(gbc.uboot_deb_d, "DEBIAN"), 0, 0, 0o755)
        with open(OPJ(gbc.uboot_deb_d, "DEBIAN", "conffiles"), "w") as f:
            print(textwrap.dedent("""\
                    /boot/firmware/config.txt
                    /boot/firmware/uboot.env"""), file=f)
        ib.file.chmod(s, OPJ(gbc.uboot_deb_d, "DEBIAN", "conffiles"), 0o644)
        with open(OPJ(gbc.uboot_deb_d, "DEBIAN", "control"), "w") as f:
            print(textwrap.dedent("""\
                    Package: u-boot-git
                    Version: {0}-1
                    Section: kernel
                    Priority: optional
                    Architecture: armhf
                    Maintainer: Andrew Ruder <andy@aeruder.net>
                    Description: U-Boot for raspberry pi 2 + 3
                      This is a debian package generated from the u-boot git repository""").format(gbc.today),
                    file=f)
        ib.file.chmod(s, OPJ(gbc.uboot_deb_d, "DEBIAN", "control"), 0o644)
        with open("u-boot-env.txt", "r") as fin:
            with open(OPJ(gbc.tmp, "u-boot-env-stripped.txt"), "wb") as fout:
                ib.check_subprocess(s, [ 'bash', OPJ("utils", "env_filter.sh") ],
                        stdin=fin, stdout=fout)
        ib.check_subprocess(s, [ OPJ(gbc.uboot, "tools", "mkenvimage"), "-p", "0",
            "-s", "16384", "-o", OPJ(gbc.uboot_deb_d, "boot", "firmware", "uboot.env"),
            OPJ(gbc.tmp, "u-boot-env-stripped.txt") ])
        ib.file.chmod(s, OPJ(gbc.uboot_deb_d, "boot", "firmware", "uboot.env"), 0o644)

        ib.check_subprocess(s, [ OPJ(gbc.linux, "scripts", "mkknlimg"), "--dtok",
            OPJ(gbc.uboot, "u-boot.bin"), OPJ(gbc.uboot_deb_d, "boot", "firmware", "uboot.bin") ])
        ib.file.chmod(s, OPJ(gbc.uboot_deb_d, "boot", "firmware", "uboot.bin"), 0o644)

        ib.check_subprocess(s, [ "dpkg-deb", "-b", gbc.uboot_deb_d, gbc.uboot_deb ])

@ib.buildcmd()
class create_firmware_deb(object):
    def run(self, s, gbc):
        ib.file.install_dir(s, gbc.firmware_deb_d, 0, 0, 0o755)
        ib.file.install_dir(s, OPJ(gbc.firmware_deb_d, "boot"), 0, 0, 0o755)
        ib.file.copy_r(s, OPJ(gbc.firmware, "boot"),
                OPJ(gbc.firmware_deb_d, "boot", "firmware"))
        ib.file.rm(s, OPJ(gbc.firmware_deb_d, "boot", "firmware", "kernel.img"))
        ib.file.rm(s, OPJ(gbc.firmware_deb_d, "boot", "firmware", "kernel7.img"))
        ib.check_subprocess(s, [ 'chmod', '-R', 'u=rwX,g=rX,o=rX',
            OPJ(gbc.firmware_deb_d, "boot", "firmware") ])

        ib.file.install_dir(s, OPJ(gbc.firmware_deb_d, "DEBIAN"), 0, 0, 0o755)
        with open(OPJ(gbc.firmware_deb_d, "DEBIAN", "control"), "w") as f:
            print(textwrap.dedent("""\
                    Package: raspberrypi-firmware-git
                    Version: {0}-1
                    Section: kernel
                    Priority: optional
                    Architecture: armhf
                    Maintainer: Andrew Ruder <andy@aeruder.net>
                    Description: Raspberry-pi firmware
                      This is a debian package generated from the raspberrypi firmware git repository""").format(gbc.today),
                    file=f)
        ib.file.chmod(s, OPJ(gbc.firmware_deb_d, "DEBIAN", "control"), 0o644)
        ib.check_subprocess(s, [ "dpkg-deb", "-b", gbc.firmware_deb_d, gbc.firmware_deb ])

@ib.buildcmd()
class run_with_root(object):
    def run(self, s, gbc, command, sudo=False, fakeroot=False):
        launch_sub = False
        out_file = None
        sub_type = None
        if sudo:
            if gbc.in_sudo:
                command(s, gbc)
            else:
                out_file = OPJ(gbc.tmp, "gbc_sudo")
                launch_sub = True
                sub_type = "sudo"
        elif fakeroot:
            if gbc.in_fakeroot:
                command(s, gbc)
            else:
                out_file = OPJ(gbc.tmp, "gbc_fakeroot")
                launch_sub = True
                sub_type = "fakeroot"
        else:
            command(s, gbc)
        if launch_sub:
            with open(out_file, "wb") as f:
                pickle.dump(gbc, f, protocol=pickle.HIGHEST_PROTOCOL)
            ib.check_subprocess(s, [ sub_type, sys.argv[0], "resume", sub_type, out_file, command.__name__ ])
            with open(out_file, "rb") as f:
                gbc = pickle.load(f)

@ib.buildcmd()
@ib.buildcmd_flatten()
class run_with_sudo(object):
    def run(self, s, gbc, command):
        run_with_root(s, gbc, command, sudo=True)

@ib.buildcmd()
@ib.buildcmd_flatten()
class run_with_fakeroot(object):
    def run(self, s, gbc, command):
        run_with_root(s, gbc, command, fakeroot=True)

@ib.buildcmd()
class resume(object):
    def run(self, s):
        self.resumed = False
        if len(sys.argv) == 5 and sys.argv[1] == "resume":
            if sys.argv[2] == "sudo":
                with open(sys.argv[3], "rb") as f:
                    gbc = pickle.load(f)
                gbc.in_sudo = True
                run_with_sudo(s, gbc, globals()[sys.argv[4]])
                gbc.in_sudo = False
                with open(sys.argv[3], "wb") as f:
                    pickle.dump(gbc, f, protocol=pickle.HIGHEST_PROTOCOL)
            elif sys.argv[2] == "fakeroot":
                with open(sys.argv[3], "rb") as f:
                    gbc = pickle.load(f)
                gbc.in_fakeroot = True
                run_with_fakeroot(s, gbc, globals()[sys.argv[4]])
                gbc.in_fakeroot = False
                with open(sys.argv[3], "wb") as f:
                    pickle.dump(gbc, f, protocol=pickle.HIGHEST_PROTOCOL)
            self.resumed = True

@ib.buildcmd()
class move_packages(object):
    def run(self, s, gbc):
        for a in glob.glob(OPJ('packages', '*.deb')):
            ib.file.rm(s, a)
        for a in glob.glob(OPJ(gbc.tmp, '*.deb')):
            ib.file.copy(s, a, 'packages')

with ib.builder() as s:
    if not resume(s).resumed:
        gbc = setup_gbc(s).gbc

        clone_linux(s, gbc)
        clone_firmware(s, gbc)
        clone_uboot(s, gbc)

        compile_linux(s, gbc)
        compile_uboot(s, gbc)

        run_with_fakeroot(s, gbc, create_uboot_deb)
        run_with_fakeroot(s, gbc, create_firmware_deb)

        move_packages(s, gbc)
