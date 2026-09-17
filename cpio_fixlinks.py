#!/usr/bin/env python3
# Restore symlink + dir entries from a gzip'ed cpio newc archive into a tree
# (macOS BSD cpio -idm drops most symlinks).
import gzip, os, sys

base = sys.argv[1]
arch = sys.argv[2]
data = gzip.open(arch, 'rb').read()
i, n, dirs = 0, 0, 0
while i + 110 <= len(data):
    hdr = data[i:i+110]
    if hdr[104:110] == b'00000017':
        break
    namesize = int(hdr[0:8], 16)
    fsize = int(hdr[48:56], 16)
    ftype = int(hdr[56:64], 16)
    name = data[i+110:i+110+namesize].decode('utf-8', 'replace').rstrip('\x00')
    namelen = (namesize + 3) // 4 * 4
    payload = i + 110 + namelen
    if name == 'TRAILER!!!':
        break
    if ftype == 2:  # LNK
        target = data[payload:payload+fsize].decode('utf-8', 'replace').rstrip('\x00')
        path = os.path.join(base, name.lstrip('./'))
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        if os.path.lexists(path):
            os.remove(path)
        os.symlink(target, path)
        n += 1
    elif ftype == 4:  # DIR
        path = os.path.join(base, name.lstrip('./'))
        os.makedirs(path, exist_ok=True)
        dirs += 1
    i = payload + (fsize + 3) // 4 * 4
print('symlinks=%d dirs=%d' % (n, dirs))