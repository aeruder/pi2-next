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

DEBIAN_VER = "jessie"

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
class 

with ib.builder() as s:
    gbc = setup_gbc(s).gbc
