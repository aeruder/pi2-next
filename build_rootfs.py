#!/usr/bin/env python3

import image_builder as ib
import os
import subprocess

UBOOT_VER = "v2016.03"
UBOOT_URL = 'git://git.denx.de/u-boot.git'
HYP_VER = "origin/master"
HYP_URL = "https://github.com/slp/rpi2-hyp-boot"
LINUX_VER = "origin/rpi-4.6.y"
LINUX_URL = "https://github.com/raspberrypi/linux"
FIRMWARE_VER = "origin/master"
FIRMWARE_URL = "http://github.com/raspberrypi/firmware"

def check_git_run(s, repo, *args):
    ib.check_subprocess(s, ["git", "-C", repo] + list(args))

def git_run(s, repo, *args):
    return ib.subprocess(s, ["git", "-C", repo] + list(args)).returncode

with ib.builder() as s:
    tmp = ib.mkdtemp(s, path=os.getcwd()).path

    repo_d = 'repo'
    uboot_repo_d = os.path.join(repo_d, 'u-boot.git')
    uboot_tmp_repo_d = os.path.join(tmp, 'u-boot')
    hyp_repo_d = os.path.join(repo_d, 'hyp.git')
    hyp_tmp_repo_d = os.path.join(tmp, 'hyp')
    linux_repo_d = os.path.join(repo_d, 'linux.git')
    linux_tmp_repo_d = os.path.join(tmp, 'linux')
    firmware_repo_d = os.path.join(repo_d, 'firmware.git')
    firmware_tmp_repo_d = os.path.join(tmp, 'firmware')

    if not os.path.isdir(repo_d):
        os.mkdir(repo_d)

    if not os.path.isdir(uboot_repo_d):
        ib.check_subprocess(s, ['git', 'clone', '--bare', UBOOT_URL, uboot_repo_d])
    check_git_run(s, uboot_repo_d, 'fetch')
    ib.check_subprocess(s, ['git', 'clone', '--reference',
        uboot_repo_d, UBOOT_URL, uboot_tmp_repo_d])
    check_git_run(s, uboot_tmp_repo_d, 'checkout', UBOOT_VER)
    ib.check_subprocess(s, ['make', '-C', uboot_tmp_repo_d, 'rpi_2_defconfig'])
    ib.check_subprocess(s, ['make', '-j5', '-C', uboot_tmp_repo_d])

    if not os.path.isdir(hyp_repo_d):
        ib.check_subprocess(s, ['git', 'clone', '--bare', HYP_URL, hyp_repo_d])
    check_git_run(s, hyp_repo_d, 'fetch')
    ib.check_subprocess(s, ['git', 'clone', '--reference',
        hyp_repo_d, HYP_URL, hyp_tmp_repo_d])
    check_git_run(s, hyp_tmp_repo_d, 'checkout', HYP_VER)
    ib.check_subprocess(s, ['make', '-C', hyp_tmp_repo_d])

    if not os.path.isdir(linux_repo_d):
        ib.check_subprocess(s, ['git', 'clone', '--bare', LINUX_URL, linux_repo_d])
    check_git_run(s, linux_repo_d, 'fetch')
    ib.check_subprocess(s, ['git', 'clone', '--reference',
        linux_repo_d, LINUX_URL, linux_tmp_repo_d])
    check_git_run(s, linux_tmp_repo_d, 'checkout', LINUX_VER)
    ib.check_subprocess(s, ['cp', 'linux-config', os.path.join(linux_tmp_repo_d, '.config')])
    ib.check_subprocess(s, ['make', '-C', linux_tmp_repo_d, 'oldconfig'], stdin=subprocess.DEVNULL)
    ib.check_subprocess(s, ['make', '-j4', '-C', linux_tmp_repo_d, 'deb-pkg'])

    if not os.path.isdir(firmware_repo_d):
        ib.check_subprocess(s, ['git', 'clone', '--bare', FIRMWARE_URL, firmware_repo_d])
    check_git_run(s, firmware_repo_d, 'fetch')
    ib.check_subprocess(s, ['git', 'clone', '--reference',
        firmware_repo_d, FIRMWARE_URL, firmware_tmp_repo_d])
    check_git_run(s, firmware_tmp_repo_d, 'checkout', FIRMWARE_VER)

    ib.subprocess(s, ['zsh'])
