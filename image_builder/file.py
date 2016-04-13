import image_builder as ib
import shutil
import os

@ib.buildcmd()
@ib.buildcmd_name("file.copy")
@ib.buildcmd_flatten()
class copy(object):
    def run(self, s, fromfile, tofile):
        s.debug("Copying %s to %s", fromfile, tofile)
        shutil.copyfile(fromfile, tofile)

@ib.buildcmd()
@ib.buildcmd_name("file.install")
@ib.buildcmd_flatten()
class install(object):
    def run(self, s, from_path, to_path, uid, gid, perm):
        s.debug("Copying %s to %s (uid: %d, gid: %d, perm: %04o)" %
                (from_path, to_path, uid, gid, perm))
        shutil.copyfile(from_path, to_path, follow_symlinks=False)
        if not os.path.islink(to_path):
            os.chmod(to_path, perm)
        os.chown(to_path, uid, gid, follow_symlinks=False)

@ib.buildcmd()
@ib.buildcmd_name("file.install_dir")
@ib.buildcmd_flatten()
class install_dir(object):
    def run(self, s, to_path, uid, gid, perm):
        s.debug("Creating %s/ (uid: %d, gid: %d, perm: %04o)" %
            (to_path, uid, gid, perm))
        os.mkdir(to_path, perm)
        os.chown(to_path, uid, gid, follow_symlinks=False)

@ib.buildcmd()
@ib.buildcmd_name("file.rm")
@ib.buildcmd_flatten()
class rm(object):
    def run(self, s, to_path):
        s.debug("Removing %s", to_path)
        os.unlink(to_path)

@ib.buildcmd()
@ib.buildcmd_name("file.rm_r")
@ib.buildcmd_flatten()
class rm_r(object):
    def run(self, s, to_path):
        s.debug("Removing %s/", to_path)
        shutil.rmtree(to_path)

@ib.buildcmd()
@ib.buildcmd_name("file.chmod")
@ib.buildcmd_flatten()
class chmod(object):
    def run(self, s, to_path, perms):
        s.debug("Changing permissions on %s to %04o", to_path, perms)
        os.chmod(to_path, perms)

@ib.buildcmd()
@ib.buildcmd_name("file.chown")
@ib.buildcmd_flatten()
class chown(object):
    def run(self, s, to_path, uid=None, gid=None):
        stat = os.lstat(to_path)
        if not uid: uid = stat.st_uid
        if not gid: gid = stat.st_gid
        s.debug("Changing ownership on %s to %d:%d", to_path, uid, gid)
        os.chown(to_path, uid, gid, follow_symlinks=False)
