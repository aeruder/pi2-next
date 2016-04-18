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

DEBIAN_VER = "stretch"
MIRROR = "http://ftp.us.debian.org/debian/"

class GlobalBuildContext:
    pass

@ib.buildcmd()
class setup_gbc(object):
    def run(self, s):
        self.gbc = GlobalBuildContext()
        self.gbc.tmp = ib.mkdtemp(s, path=os.getcwd()).path
        self.gbc.repo = "repo"
        self.gbc.today = datetime.datetime.now().strftime("%Y%m%d%H%M")

        if not os.path.isdir(self.gbc.repo):
            os.mkdir(self.gbc.repo)

@ib.buildcmd()
class download_repo(object):
    def run(self, s, gbc):
        gbc.debian = gbc.mnt
        debiantar = None
        for a in glob.glob(OPJ(gbc.repo, "{0}-bare-*.tar.gz".format(DEBIAN_VER))):
            debiantar = a
        if debiantar != None:
            s.info("Found %s, skipping debootstrap" % debiantar)
            with open(debiantar, "rb") as f:
                ib.check_subprocess(s, [ 'tar', '--strip-components=1', '-C', gbc.debian, '-zxf', '-' ], stdin=f)
        else:
            ib.check_subprocess(s, [ 'debootstrap', DEBIAN_VER, gbc.debian, MIRROR ])
            debiantar = "{0}-bare-{1}.tar.gz".format(DEBIAN_VER, gbc.today)
            with open(OPJ(gbc.repo, debiantar), "wb") as f:
                ib.check_subprocess(s, [ 'tar', '-C', gbc.tmp, '-zcf', '-', DEBIAN_VER ], stdout=f)

@ib.buildcmd()
class disable_services(object):
    def run(self, s, root):
        policyfile = OPJ(root, "usr", "sbin", "policy-rc.d")
        with open(policyfile, "w") as f:
            print(textwrap.dedent("""\
                    #!/bin/sh
                    exit 101"""), file=f)
        ib.file.chmod(s, policyfile, 0o755)

@ib.buildcmd()
class enable_services(object):
    def run(self, s, root):
        policyfile = OPJ(root, "usr", "sbin", "policy-rc.d")
        ib.file.rm(s, policyfile)

@ib.buildcmd()
@ib.buildcmd_flatten()
class run_chroot(object):
    def run(self, s, root, cmd, helper=ib.check_subprocess, *args, **kwargs):
        cmd = [ "chroot", root ] + cmd
        helper(s, cmd, *args, **kwargs)

@ib.buildcmd()
@ib.buildcmd_flatten()
class apt_get(object):
    def run(self, s, root, args):
        run_chroot(s, root, [ 'apt-get' ] + args)

@ib.buildcmd()
@ib.buildcmd_flatten()
class install_deb(object):
    def run(self, s, root, pkg):
        ib.file.copyfile(s, pkg, OPJ(root, "install.deb"))
        run_chroot(s, root, [ 'dpkg', '-i', '/install.deb' ])
        ib.file.rm(s, OPJ(root, "install.deb"))

@ib.buildcmd()
@ib.buildcmd_flatten()
class overlay(object):
    def run(self, s, root, path, uid, gid, perm):
        from_path = "overlay" + path
        to_path = root + path
        ib.file.install(s, from_path, to_path, uid, gid, perm)

@ib.buildcmd()
class create_image(object):
    def run(self, s, gbc):
        gbc.img = OPJ(gbc.tmp, "img.bin")
        ib.check_subprocess(s, [ 'dd', 'if=/dev/zero', 'of=%s' % gbc.img, 'bs=1048576', 'count=800' ])
        gbc.dev = ib.loopback.init(s, gbc.img, partscan=True).device

@ib.buildcmd()
class create_partitions(object):
    def run(self, s, gbc):
        with open(OPJ(gbc.tmp, "sfdisk.scr"), "w") as f:
            print(textwrap.dedent("""\
                label: dos
                unit: sectors

                start=2048, size=49152, type=e
                start=51200, size=153600, type=83
                start=204800, type=83"""), file=f)
        with open(OPJ(gbc.tmp, "sfdisk.scr"), "r") as f:
            ib.check_subprocess(s, [ 'sfdisk', gbc.dev ], stdin=f)
        gbc.fwdev = gbc.dev + "p1"
        gbc.bootdev = gbc.dev + "p2"
        gbc.rootdev = gbc.dev + "p3"

@ib.buildcmd()
class format_partitions(object):
    def run(self, s, gbc):
        ib.check_subprocess(s, [ 'mkfs.fat', '-F', '16', gbc.fwdev ])
        ib.check_subprocess(s, [ 'mkfs.ext4', gbc.bootdev ])
        ib.check_subprocess(s, [ 'mkfs.btrfs', gbc.rootdev ])

@ib.buildcmd()
class mount_partitions(object):
    def run(self, s, gbc):
        gbc.mnt = OPJ(gbc.tmp, DEBIAN_VER)
        ib.file.mkdir(s, gbc.mnt)
        with ib.builder() as s1:
            ib.mount(s1, 'btrfs', gbc.rootdev, gbc.mnt, "rw,relatime,compress=lzo,space_cache")
            ib.check_subprocess(s1, [ 'btrfs', 'subvolume', 'create', OPJ(gbc.mnt, 'rootfs') ])
            ib.check_subprocess(s1, [ 'btrfs', 'subvolume', 'create', OPJ(gbc.mnt, 'home') ])
        ib.mount(s, 'btrfs', gbc.rootdev, gbc.mnt, 'rw,relatime,compress=lzo,space_cache,subvol=rootfs')
        ib.file.mkdir(s, OPJ(gbc.mnt, "boot"))
        ib.file.mkdir(s, OPJ(gbc.mnt, "home"))
        ib.mount(s, 'btrfs', gbc.rootdev, OPJ(gbc.mnt, "home"), 'rw,relatime,compress=lzo,space_cache,subvol=home')
        ib.mount(s, 'ext4', gbc.bootdev, OPJ(gbc.mnt, 'boot'), 'rw,relatime')
        ib.file.mkdir(s, OPJ(gbc.mnt, "boot", "firmware"))
        ib.mount(s, 'vfat', gbc.fwdev, OPJ(gbc.mnt, 'boot', 'firmware'))

@ib.buildcmd()
class install_packages(object):
    def run(self, s, gbc):
        for a in glob.glob(OPJ("packages", "raspberrypi-firmware-git-*.deb")):
            install_deb(s, gbc.debian, a)
        for a in glob.glob(OPJ("packages", "u-boot-%s-git-*.deb" % gbc.build)):
            install_deb(s, gbc.debian, a)
        for a in glob.glob(OPJ("packages", "linux-*.deb")):
            install_deb(s, gbc.debian, a)

@ib.buildcmd()
class move_image(object):
    def run(self, s, gbc):
        with open("r%s-next-%s.img.gz" % (gbc.build, gbc.today), "wb") as f1:
            with open(gbc.img, "rb") as f2:
                ib.check_subprocess(s, [ "gzip", "-c" ], stdin=f2, stdout=f1)

@ib.buildcmd()
class remove_keys(object):
    def run(self, s, gbc):
        for a in glob.glob(OPJ(gbc.debian, "etc", "ssh", "ssh_host_*")):
            ib.file.rm(s, a)

@ib.buildcmd()
class set_password(object):
    def run(self, s, gbc, user, password):
        with open(OPJ(gbc.tmp, "pass"), "w") as f:
            print(textwrap.dedent("""\
                    %s:%s""" % (user, password)), file=f)
        with open(OPJ(gbc.tmp, "pass"), "r") as f:
            run_chroot(s, gbc.debian, [ 'chpasswd', '-c', 'SHA512' ], stdin=f)

@ib.buildcmd()
class add_user(object):
    def run(self, s, gbc, user):
        run_chroot(s, gbc.debian, [ "useradd", "-m", "-s", "/bin/bash", user ])

with ib.builder() as s:
    ib.check_root(s)
    gbc = setup_gbc(s).gbc

    if len(sys.argv) != 2:
        print("Usage: %s <pi2|pi3>" % sys.argv[0])
        sys.exit(1)
    elif sys.argv[1] == "pi2":
        gbc.build = "pi2"
    elif sys.argv[1] == "pi3":
        gbc.build = "pi3"
    else:
        print("Usage: %s <pi2|pi3>" % sys.argv[0])
        sys.exit(1)

    with ib.builder() as s1:
        create_image(s1, gbc)
        create_partitions(s1, gbc)
        format_partitions(s1, gbc)
        mount_partitions(s1, gbc)
        download_repo(s1, gbc)
        ib.file.rm(s1, OPJ(gbc.debian, "etc", "resolv.conf"))
        ib.check_subprocess(s1, [ "cp", "-L", "/etc/resolv.conf", OPJ(gbc.debian, "etc", "resolv.conf") ])

        disable_services(s1, gbc.debian)
        apt_get(s1, gbc.debian, ['update'])
        apt_get(s1, gbc.debian, ['-y', 'install', 'openssh-client',
            'openssh-server', 'initramfs-tools', 'btrfs-tools', 'parted' ])
        apt_get(s1, gbc.debian, ['clean'])
        install_packages(s1, gbc)
        remove_keys(s1, gbc)
        run_chroot(s1, gbc.debian, [ 'systemctl', 'enable', 'systemd-networkd.service' ])
        run_chroot(s1, gbc.debian, [ 'systemctl', 'enable', 'systemd-resolved.service' ])
        run_chroot(s1, gbc.debian, [ 'systemctl', 'enable', 'systemd-timesyncd.service' ])

        run_chroot(s1, gbc.debian, [ 'rm', '/etc/resolv.conf' ])
        run_chroot(s1, gbc.debian, [ 'ln', '-s', '/run/systemd/resolve/resolv.conf', '/etc/resolv.conf' ])
        overlay(s1, gbc.debian, "/etc/cron.d/FIRST_BOOT_SSH", 0, 0, 0o644)
        overlay(s1, gbc.debian, "/etc/cron.d/FIRST_BOOT_PARTITION", 0, 0, 0o644)
        overlay(s1, gbc.debian, "/etc/systemd/network/eth.network", 0, 0, 0o644)
        overlay(s1, gbc.debian, "/etc/systemd/network/enx.network", 0, 0, 0o644)
        overlay(s1, gbc.debian, "/etc/fstab", 0, 0, 0o644)
        with open(OPJ(gbc.debian, "etc", "hostname"), "w") as f:
            print("%s-next" % gbc.build, file=f)
        ib.file.chmod(s1, OPJ(gbc.debian, "etc", "hostname"), 0o644)
        overlay(s1, gbc.debian, "/boot/uboot_params.txt", 0, 0, 0o644)
        set_password(s1, gbc, "root", "%s-next" % gbc.build)

        add_user(s1, gbc, "%s-next" % gbc.build)
        set_password(s1, gbc, "%s-next" % gbc.build, "%s-next" % gbc.build)

        enable_services(s1, gbc.debian)
    move_image(s, gbc)
