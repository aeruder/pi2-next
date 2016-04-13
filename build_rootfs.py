#!/usr/bin/env python3

import image_builder as ib
import os
import subprocess
import textwrap
import datetime

OPJ = os.path.join

TODAY = datetime.datetime.now().strftime("%Y%m%d%H%M")

UBOOT_VER = "v2016.03"
UBOOT_URL = 'git://git.denx.de/u-boot.git'
HYP_VER = "master"
HYP_URL = "https://github.com/slp/rpi2-hyp-boot"
LINUX_VER = "rpi-4.6.y"
LINUX_URL = "https://github.com/raspberrypi/linux"
LINUX_UPSTREAM_URL = "git://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git"
LINUX_STABLE_URL = "git://git.kernel.org/pub/scm/linux/kernel/git/stable/linux-stable.git"
FIRMWARE_VER = "master"
FIRMWARE_URL = "http://github.com/raspberrypi/firmware"

def check_git_run(s, repo, cmd):
    ib.check_subprocess(s, ["git", "-C", repo] + list(cmd))

def git_run(s, repo, cmd):
    return ib.subprocess(s, ["git", "-C", repo] + list(cmd)).returncode

def fetch_git_url(s, repo, remote, url):
    if not os.path.isdir(repo):
        ib.check_subprocess(s, ['git', 'clone', '--bare', url, repo])
    if git_run(s, repo, [ 'remote', 'get-url', remote ]) != 0:
        check_git_run(s, repo, [ 'remote', 'add', remote, url ])
    check_git_run(s, repo, [ 'remote', 'set-url', remote, url ])
    check_git_run(s, repo, [ 'fetch', remote ])

with ib.builder() as s:
    ib.check_fakeroot(s)
    tmp = ib.mkdtemp(s, path=os.getcwd()).path

    repo_d = 'repo'
    uboot_repo_d = OPJ(repo_d, 'u-boot.git')
    uboot_tmp_repo_d = OPJ(tmp, 'u-boot')
    hyp_repo_d = OPJ(repo_d, 'hyp.git')
    hyp_tmp_repo_d = OPJ(tmp, 'hyp')
    linux_repo_d = OPJ(repo_d, 'linux.git')
    linux_tmp_repo_d = OPJ(tmp, 'linux')
    firmware_repo_d = OPJ(repo_d, 'firmware.git')
    firmware_tmp_repo_d = OPJ(tmp, 'firmware')
    uboot_deb_d = OPJ(tmp, 'u-boot-deb')
    uboot_deb = OPJ(tmp, "u-boot-git-{0}-1_armhf.deb".format(TODAY))

    if not os.path.isdir(repo_d):
        os.mkdir(repo_d)

    # fetch_git_url(s, uboot_repo_d, 'origin', UBOOT_URL)
    # fetch_git_url(s, hyp_repo_d, 'origin', HYP_URL)
    # fetch_git_url(s, linux_repo_d, 'origin', LINUX_URL)
    # fetch_git_url(s, linux_repo_d, 'upstream', LINUX_UPSTREAM_URL)
    # fetch_git_url(s, linux_repo_d, 'stable', LINUX_STABLE_URL)
    # fetch_git_url(s, firmware_repo_d, 'origin', FIRMWARE_URL)

    check_git_run(s, uboot_repo_d, [ 'worktree', 'add', '--detach',
            uboot_tmp_repo_d, UBOOT_VER ])
    check_git_run(s, hyp_repo_d, [ 'worktree', 'add', '--detach',
            hyp_tmp_repo_d, HYP_VER ])
    # check_git_run(s, linux_repo_d, [ 'worktree', 'add', '--detach',
    #         linux_tmp_repo_d, LINUX_VER ])
    check_git_run(s, firmware_repo_d, [ 'worktree', 'add', '--detach',
            firmware_tmp_repo_d, FIRMWARE_VER ])

    # check_git_run(s, linux_tmp_repo_d, [ 'am',
    #         OPJ(os.getcwd(),
    #                      'patches',
    #                      '0001-Fix-deprecated-get_user_pages-page_cache_release.patch') ])

    ib.check_subprocess(s, ['make', '-C', hyp_tmp_repo_d])
    ib.check_subprocess(s, ['make', '-C', uboot_tmp_repo_d, 'rpi_2_defconfig'])
    ib.check_subprocess(s, ['make', '-j8', '-C', uboot_tmp_repo_d])

    # ib.check_subprocess(s, ['cp', 'linux-config', OPJ(linux_tmp_repo_d, '.config')])
    # ib.check_subprocess(s, ['make', '-C', linux_tmp_repo_d, 'oldconfig'], stdin=subprocess.DEVNULL)
    # ib.check_subprocess(s, ['make', '-j8', '-C', linux_tmp_repo_d, 'deb-pkg'])

    create_uboot_package(s, uboot_deb_d, uboot_deb

    ib.file.install_dir(s, uboot_deb_d, 0, 0, 0o755)
    ib.file.install_dir(s, OPJ(uboot_deb_d, "boot"), 0, 0, 0o755)
    ib.file.install_dir(s, OPJ(uboot_deb_d, "boot", "firmware"), 0, 0, 0o755)
    ib.file.install_dir(s, OPJ(uboot_deb_d, "etc"), 0, 0, 0o755)
    ib.file.install_dir(s, OPJ(uboot_deb_d, "etc", "kernel"), 0, 0, 0o755)
    ib.file.install_dir(s, OPJ(uboot_deb_d, "etc", "kernel", "postinst.d"), 0, 0, 0o755)
    ib.file.install(s, OPJ("u-boot-deb", "zz-u-boot"),
            OPJ(uboot_deb_d, "etc", "kernel", "postinst.d", "zz-u-boot"), 0, 0, 0o755)
    ib.file.install(s, OPJ("u-boot-deb", "config.txt"),
            OPJ(uboot_deb_d, "boot", "firmware", "config.txt"), 0, 0, 0o644)
    ib.file.install_dir(s, OPJ(uboot_deb_d, "DEBIAN"), 0, 0, 0o755)
    with open(OPJ(uboot_deb_d, "DEBIAN", "conffiles"), "w") as f:
        print(textwrap.dedent("""\
                /boot/firmware/config.txt
                /boot/firmware/uboot.env"""), file=f)
    ib.file.chmod(s, OPJ(uboot_deb_d, "DEBIAN", "conffiles"), 0o644)
    with open(OPJ(uboot_deb_d, "DEBIAN", "control"), "w") as f:
        print(textwrap.dedent("""\
                Package: u-boot-git
                Version: {0}
                Section: kernel
                Priority: optional
                Architecture: armhf
                Maintainer: Andrew Ruder <andy@aeruder.net>
                Description: U-Boot for raspberry pi 2 + 3 with HYP
                  This is a debian package generated from the u-boot git repository""").format(TODAY),
                file=f)
    ib.file.chmod(s, OPJ(uboot_deb_d, "DEBIAN", "control"), 0o644)
    with open("u-boot-env.txt", "r") as fin:
        with open(OPJ(tmp, "u-boot-env-stripped.txt"), "wb") as fout:
            ib.check_subprocess(s, [ 'bash', OPJ("utils", "env_filter.sh") ],
                    stdin=fin, stdout=fout)
    ib.check_subprocess(s, [ OPJ(uboot_tmp_repo_d, "tools", "mkenvimage"), "-p", "0",
        "-s", "16384", "-o", OPJ(uboot_deb_d, "boot", "firmware", "uboot.env"),
        OPJ(tmp, "u-boot-env-stripped.txt") ])
    ib.file.chmod(s, OPJ(uboot_deb_d, "boot", "firmware", "uboot.env"), 0o644)

    with open(OPJ(uboot_deb_d, "boot", "firmware", "uboot.hyp"), "wb") as f:
        ib.check_subprocess(s, [ 'cat', OPJ(hyp_tmp_repo_d, "bootblk.bin"),
                                        OPJ(uboot_tmp_repo_d, "u-boot.bin") ], stdout=f)
    ib.file.chmod(s, OPJ(uboot_deb_d, "boot", "firmware", "uboot.hyp"), 0o644)
    ib.check_subprocess(s, [ "dpkg-deb", "-b", uboot_deb_d, uboot_deb ])

    ib.subprocess(s, ['zsh'])
