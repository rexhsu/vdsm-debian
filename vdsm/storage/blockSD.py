#
# Copyright 2009-2011 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
#
# Refer to the README and COPYING files for full details of the license
#

import os
import threading
import logging
import signal
import select
import errno
import re
from StringIO import StringIO
import time
import functools
from collections import namedtuple
from contextlib import contextmanager
from operator import itemgetter

from vdsm.config import config
from vdsm import constants
from vdsm import utils
import misc
import fileUtils
import sd
import lvm
import clusterlock
import blockVolume
import multipath
import resourceFactories
from resourceFactories import LVM_ACTIVATION_NAMESPACE
from persistentDict import PersistentDict, DictValidator
import iscsi
import storage_exception as se
from storage_mailbox import MAILBOX_SIZE
import resourceManager as rm
import mount
import supervdsm as svdsm
import volume

STORAGE_DOMAIN_TAG = "RHAT_storage_domain"
STORAGE_UNREADY_DOMAIN_TAG = STORAGE_DOMAIN_TAG + "_UNREADY"

MASTERLV = "master"
SPECIAL_LVS = (sd.METADATA, sd.LEASES, sd.IDS, sd.INBOX, sd.OUTBOX, MASTERLV)

MASTERLV_SIZE = "1024"  # In MiB = 2 ** 20 = 1024 ** 2 => 1GiB
BlockSDVol = namedtuple("BlockSDVol", "name, image, parent")

log = logging.getLogger("Storage.BlockSD")

# FIXME: Make this calculated from something logical
RESERVED_METADATA_SIZE = 40 * (2 ** 20)
RESERVED_MAILBOX_SIZE = MAILBOX_SIZE * clusterlock.MAX_HOST_ID
METADATA_BASE_SIZE = 378
# VG's min metadata threshold is 20%
VG_MDA_MIN_THRESHOLD = 0.2
# VG's metadata size in MiB
VG_METADATASIZE = 128

MAX_PVS_LIMIT = 10  # BZ#648051
MAX_PVS = config.getint('irs', 'maximum_allowed_pvs')
if MAX_PVS > MAX_PVS_LIMIT:
    log.warning("maximum_allowed_pvs = %d ignored. MAX_PVS = %d", MAX_PVS,
                MAX_PVS_LIMIT)
    MAX_PVS = MAX_PVS_LIMIT

PVS_METADATA_SIZE = MAX_PVS * 142

SD_METADATA_SIZE = 2048
DEFAULT_BLOCKSIZE = 512

DMDK_VGUUID = "VGUUID"
DMDK_PV_REGEX = re.compile(r"^PV\d+$")
DMDK_LOGBLKSIZE = "LOGBLKSIZE"
DMDK_PHYBLKSIZE = "PHYBLKSIZE"

VERS_METADATA_LV = (0,)
VERS_METADATA_TAG = (2, 3)


def encodePVInfo(pvInfo):
    return (
        "pv:%s," % pvInfo["guid"] +
        "uuid:%s," % pvInfo["uuid"] +
        "pestart:%s," % pvInfo["pestart"] +
        "pecount:%s," % pvInfo["pecount"] +
        "mapoffset:%s" % pvInfo["mapoffset"])


def decodePVInfo(value):
    pvInfo = dict([item.split(":") for item in value.split(",")])
    pvInfo["guid"] = pvInfo["pv"]
    del pvInfo["pv"]
    return pvInfo

BLOCK_SD_MD_FIELDS = sd.SD_MD_FIELDS.copy()
# TBD: Do we really need this key?
BLOCK_SD_MD_FIELDS.update({
    # Key           dec,  enc
    DMDK_PV_REGEX: (decodePVInfo, encodePVInfo),
    DMDK_VGUUID: (str, str),
    DMDK_LOGBLKSIZE: (functools.partial(sd.intOrDefault, DEFAULT_BLOCKSIZE),
                      str),
    DMDK_PHYBLKSIZE: (functools.partial(sd.intOrDefault, DEFAULT_BLOCKSIZE),
                      str),
})

INVALID_CHARS = re.compile(r"[^a-zA-Z0-9_+.\-/=!:#]")
LVM_ENC_ESCAPE = re.compile("&(\d+)&")


# Move to lvm
def lvmTagEncode(s):
    return INVALID_CHARS.sub(lambda c: "&%s&" % ord(c.group()), s)


def lvmTagDecode(s):
    return LVM_ENC_ESCAPE.sub(lambda c: unichr(int(c.groups()[0])), s)


def _tellEnd(devPath):
    """Size in bytes of a block device.

    stat.st_size of block devices is identically 0.
    """
    with open(devPath, "rb") as f:
        f.seek(0, os.SEEK_END)
        return f.tell()


def _getVolsTree(sdUUID):
    lvs = lvm.getLV(sdUUID)
    vols = {}
    for lv in lvs:
        image = ""
        parent = ""
        for tag in lv.tags:
            if tag.startswith(blockVolume.TAG_PREFIX_IMAGE):
                image = tag[len(blockVolume.TAG_PREFIX_IMAGE):]
            elif tag.startswith(blockVolume.TAG_PREFIX_PARENT):
                parent = tag[len(blockVolume.TAG_PREFIX_PARENT):]
            if parent and image:
                vols[lv.name] = BlockSDVol(lv.name, image, parent)
                break
        else:
            if lv.name not in SPECIAL_LVS:
                log.warning("Ignoring Volume %s that lacks minimal tag set"
                            "tags %s" % (lv.name, lv.tags))
    return vols


def getAllVolumes(sdUUID):
    """
    Return dict {volUUID: ((imgUUIDs,), parentUUID)} of the domain.

    imgUUIDs is a list of all images dependant on volUUID.
    For template based volumes, the first image is the template's image.
    For other volumes, there is just a single imageUUID.
    Template self image is the 1st term in template volume entry images.
    """
    vols = _getVolsTree(sdUUID)
    res = {}
    for volName in vols.iterkeys():
        res[volName] = {'imgs': [], 'parent': None}

    for volName, vImg, parentVol in vols.itervalues():
        res[volName]['parent'] = parentVol
        if vImg not in res[volName]['imgs']:
            res[volName]['imgs'].insert(0, vImg)
        if parentVol != sd.BLANK_UUID:
            try:
                imgIsUnknown = vImg not in res[parentVol]['imgs']
            except KeyError:
                log.warning("Found broken image %s, orphan volume %s/%s, "
                            "parent %s", vImg, sdUUID, volName, parentVol)
            else:
                if imgIsUnknown:
                    res[parentVol]['imgs'].append(vImg)

    return dict((k, sd.ImgsPar(tuple(v['imgs']), v['parent']))
                for k, v in res.iteritems())


def deleteVolumes(sdUUID, vols):
    lvm.removeLVs(sdUUID, vols)


def _zeroVolume(sdUUID, volUUID):
    """Fill a block volume.

    This function requires an active LV.
    """
    dm = lvm.lvDmDev(sdUUID, volUUID)
    size = multipath.getDeviceSize(dm)  # Bytes
    # TODO: Change for zero 128 M chuncks and log.
    # 128 M is the vdsm extent size default
    BS = constants.MEGAB  # 1024 ** 2 = 1 MiB
    count = size / BS
    cmd = [constants.EXT_DD, "oflag=%s" % misc.DIRECTFLAG, "if=/dev/zero",
           "of=%s" % lvm.lvPath(sdUUID, volUUID), "bs=%s" % BS,
           "count=%s" % count]
    p = misc.execCmd(cmd, sync=False, nice=utils.NICENESS.HIGH,
                     ioclass=utils.IOCLASS.IDLE, deathSignal=signal.SIGKILL)
    return p


def zeroImgVolumes(sdUUID, imgUUID, volUUIDs):
    ProcVol = namedtuple("ProcVol", "proc, vol")
    # Put a sensible value for dd zeroing a 128 M or 1 G chunk and lvremove
    # spent time.
    ZEROING_TIMEOUT = 60000  # [miliseconds]
    log.debug("sd: %s, LVs: %s, img: %s", sdUUID, volUUIDs, imgUUID)
    # Following call to changelv is separate since setting rw permission on an
    # LV fails if the LV is already set to the same value, hence we would not
    # be able to differentiate between a real failure of deltag/addtag and one
    # we would like to ignore (permission is the same)
    try:
        lvm.changelv(sdUUID, volUUIDs, ("--permission", "rw"))
    except se.StorageException as e:
        # Hope this only means that some volumes were already writable.
        log.debug("Ignoring failed permission change: %s", e)
    # blank the volumes.
    zerofds = {}
    poller = select.poll()
    for volUUID in volUUIDs:
        proc = _zeroVolume(sdUUID, volUUID)
        fd = proc.stdout.fileno()
        zerofds[fd] = ProcVol(proc, volUUID)
        poller.register(fd, select.EPOLLHUP)

    # Wait until all the asyncs procs return
    # Yes, this is a potentially infinite loop. Kill the vdsm task.
    while zerofds:
        fdevents = poller.poll(ZEROING_TIMEOUT)  # [(fd, event)]
        toDelete = []
        for fd, event in fdevents:
            proc, vol = zerofds[fd]
            if not proc.wait(0):
                continue
            else:
                poller.unregister(fd)
                zerofds.pop(fd)
                if proc.returncode != 0:
                    log.error("zeroing %s/%s failed. Zero and remove this "
                              "volume manually. rc=%s %s", sdUUID, vol,
                              proc.returncode, proc.stderr.read(1000))
                else:
                    log.debug("%s/%s was zeroed and will be deleted",
                              sdUUID, volUUID)
                    toDelete.append(vol)
        if toDelete:
            try:
                deleteVolumes(sdUUID, toDelete)
            except se.CannotRemoveLogicalVolume:
                # TODO: Add the list of removed fail volumes to the exception.
                log.error("Remove failed for some of VG: %s zeroed volumes: "
                          "%s", sdUUID, toDelete, exc_info=True)

    log.debug("finished with VG:%s LVs: %s, img: %s", sdUUID, volUUIDs,
              imgUUID)
    return


class VGTagMetadataRW(object):
    log = logging.getLogger("Storage.Metadata.VGTagMetadataRW")
    METADATA_TAG_PREFIX = "MDT_"
    METADATA_TAG_PREFIX_LEN = len(METADATA_TAG_PREFIX)

    def __init__(self, vgName):
        self._vgName = vgName

    def readlines(self):
        lvm.invalidateVG(self._vgName)
        vg = lvm.getVG(self._vgName)
        metadata = []
        for tag in vg.tags:
            if not tag.startswith(self.METADATA_TAG_PREFIX):
                continue

            metadata.append(lvmTagDecode(tag[self.METADATA_TAG_PREFIX_LEN:]))

        return metadata

    def writelines(self, lines):
        currentMetadata = set(self.readlines())
        newMetadata = set(lines)

        # Remove all items that do not exist in the new metadata
        toRemove = [self.METADATA_TAG_PREFIX + lvmTagEncode(item) for item in
                    currentMetadata.difference(newMetadata)]

        # Add all missing items that do no exist in the old metadata
        toAdd = [self.METADATA_TAG_PREFIX + lvmTagEncode(item) for item in
                 newMetadata.difference(currentMetadata)]

        if len(toAdd) == 0 and len(toRemove) == 0:
            return

        self.log.debug("Updating metadata adding=%s removing=%s",
                       ", ".join(toAdd), ", ".join(toRemove))
        lvm.changeVGTags(self._vgName, delTags=toRemove, addTags=toAdd)


class LvMetadataRW(object):
    """
    Block Storage Domain metadata implementation
    """
    log = logging.getLogger("Storage.Metadata.LvMetadataRW")

    def __init__(self, vgName, lvName, offset, size):
        self._size = size
        self._lvName = lvName
        self._vgName = vgName
        self._offset = offset
        self.metavol = lvm.lvPath(vgName, lvName)

    def readlines(self):
        # Fetch the metadata from metadata volume
        lvm.activateLVs(self._vgName, self._lvName)

        m = misc.readblock(self.metavol, self._offset, self._size)
        # Read from metadata volume will bring a load of zeroes trailing
        # actual metadata. Strip it out.
        metadata = [i for i in m if len(i) > 0 and i[0] != '\x00' and "=" in i]

        return metadata

    def writelines(self, lines):
        lvm.activateLVs(self._vgName, self._lvName)

        # Write `metadata' to metadata volume
        metaStr = StringIO()

        for line in lines:
            metaStr.write(line)
            metaStr.write("\n")

        if metaStr.pos > self._size:
            raise se.MetadataOverflowError(metaStr.getvalue())

        # Clear out previous data - it is a volume, not a file
        metaStr.write('\0' * (self._size - metaStr.pos))

        data = metaStr.getvalue()
        with fileUtils.DirectFile(self.metavol, "r+d") as f:
            f.seek(self._offset)
            f.write(data)

LvBasedSDMetadata = lambda vg, lv: DictValidator(
    PersistentDict(LvMetadataRW(vg, lv, 0, SD_METADATA_SIZE)),
    BLOCK_SD_MD_FIELDS)
TagBasedSDMetadata = lambda vg: DictValidator(
    PersistentDict(VGTagMetadataRW(vg)),
    BLOCK_SD_MD_FIELDS)


def selectMetadata(sdUUID):
    mdProvider = LvBasedSDMetadata(sdUUID, sd.METADATA)
    if len(mdProvider) > 0:
        metadata = mdProvider
    else:
        metadata = TagBasedSDMetadata(sdUUID)
    return metadata


def metadataValidity(vg):
    """
    Return the metadata validity:
     mdathreshold - False if the VG's metadata exceeded its threshold,
                    else True
     mdavalid - False if the VG's metadata size too small, else True
    """
    mda_size = int(vg.vg_mda_size)
    mda_free = int(vg.vg_mda_free)

    mda_size_ok = mda_size >= VG_METADATASIZE * constants.MEGAB / 2
    mda_free_ok = mda_free >= mda_size * VG_MDA_MIN_THRESHOLD

    return {'mdathreshold': mda_free_ok, 'mdavalid': mda_size_ok}


class BlockStorageDomainManifest(sd.StorageDomainManifest):
    mountpoint = os.path.join(sd.StorageDomain.storage_repository,
                              sd.DOMAIN_MNT_POINT, sd.BLOCKSD_DIR)

    def __init__(self, sdUUID, metadata=None):
        domaindir = os.path.join(self.mountpoint, sdUUID)
        sd.StorageDomainManifest.__init__(self, sdUUID, domaindir)

        if metadata is None:
            metadata = selectMetadata(self.sdUUID)
        self.replaceMetadata(metadata)

        try:
            self.logBlkSize = self.getMetaParam(DMDK_LOGBLKSIZE)
            self.phyBlkSize = self.getMetaParam(DMDK_PHYBLKSIZE)
        except KeyError:
            # 512 by Saggi "Trust me (Smoch Alai (sic))"
            # *blkSize keys may be missing from metadata only for domains that
            # existed before the introduction of the keys.
            # Such domains supported only 512 sizes
            self.logBlkSize = 512
            self.phyBlkSize = 512

    def getReadDelay(self):
        stats = misc.readspeed(lvm.lvPath(self.sdUUID, sd.METADATA), 4096)
        return stats['seconds']

    def getVSize(self, imgUUUID, volUUID):
        """ Return the block volume size in bytes. """
        try:
            size = _tellEnd(lvm.lvPath(self.sdUUID, volUUID))
        except IOError as e:
            if e.errno == os.errno.ENOENT:
                # Inactive volume has no /dev entry. Fallback to lvm way.
                size = lvm.getLV(self.sdUUID, volUUID).size
            else:
                self.log.warn("Could not get size for vol %s/%s",
                              self.sdUUID, volUUID, exc_info=True)
                raise

        return int(size)

    def getLeasesFilePath(self):
        # TODO: Determine the path without activating the LV
        lvm.activateLVs(self.sdUUID, [sd.LEASES])
        return lvm.lvPath(self.sdUUID, sd.LEASES)

    def getIdsFilePath(self):
        # TODO: Determine the path without activating the LV
        lvm.activateLVs(self.sdUUID, [sd.IDS])
        return lvm.lvPath(self.sdUUID, sd.IDS)


class BlockStorageDomain(sd.StorageDomain):
    manifestClass = BlockStorageDomainManifest

    def __init__(self, sdUUID):
        manifest = self.manifestClass(sdUUID)
        sd.StorageDomain.__init__(self, manifest)
        lvm.activateLVs(self.sdUUID, SPECIAL_LVS)
        self.metavol = lvm.lvPath(self.sdUUID, sd.METADATA)

        # Check that all devices in the VG have the same logical and physical
        # block sizes.
        lvm.checkVGBlockSizes(sdUUID, (self.logBlkSize, self.phyBlkSize))

        # _extendlock is used to prevent race between
        # VG extend and LV extend.
        self._extendlock = threading.Lock()
        self.imageGarbageCollector()
        self._registerResourceNamespaces()
        self._lastUncachedSelftest = 0

    @property
    def logBlkSize(self):
        return self._manifest.logBlkSize

    @property
    def phyBlkSize(self):
        return self._manifest.phyBlkSize

    def _registerResourceNamespaces(self):
        """
        Register resources namespaces and create
        factories for it.
        """
        sd.StorageDomain._registerResourceNamespaces(self)

        rmanager = rm.ResourceManager.getInstance()
        # Register lvm activation resource namespace for the underlying VG
        lvmActivationFactory = resourceFactories.LvmActivationFactory(
            self.sdUUID)
        lvmActivationNamespace = sd.getNamespace(self.sdUUID,
                                                 LVM_ACTIVATION_NAMESPACE)
        try:
            rmanager.registerNamespace(lvmActivationNamespace,
                                       lvmActivationFactory)
        except KeyError:
            self.log.info("Resource namespace %s already registered",
                          lvmActivationNamespace)

    @classmethod
    def metaSize(cls, vgroup):
        ''' Calc the minimal meta volume size in MB'''
        # In any case the metadata volume cannot be less than 512MB for the
        # case of 512 bytes per volume metadata, 2K for domain metadata and
        # extent size of 128MB. In any case we compute the right size on line.
        vg = lvm.getVG(vgroup)
        minmetasize = (SD_METADATA_SIZE / sd.METASIZE * int(vg.extent_size) +
                       (1024 * 1024 - 1)) / (1024 * 1024)
        metaratio = int(vg.extent_size) / sd.METASIZE
        metasize = (int(vg.extent_count) * sd.METASIZE +
                    (1024 * 1024 - 1)) / (1024 * 1024)
        metasize = max(minmetasize, metasize)
        if metasize > int(vg.free) / (1024 * 1024):
            raise se.VolumeGroupSizeError(
                "volume group has not enough extents %s (Minimum %s), VG may "
                "be too small" % (vg.extent_count,
                                  (1024 * 1024) / sd.METASIZE))
        cls.log.info("size %s MB (metaratio %s)" % (metasize, metaratio))
        return metasize

    @classmethod
    def create(cls, sdUUID, domainName, domClass, vgUUID, storageType,
               version):
        """ Create new storage domain
            'sdUUID' - Storage Domain UUID
            'domainName' - storage domain name
            'domClass' - Data/Iso
            'vgUUID' - volume group UUID
            'storageType' - NFS_DOMAIN, LOCALFS_DOMAIN, &etc.
            'version' - DOMAIN_VERSIONS
        """
        cls.log.info("sdUUID=%s domainName=%s domClass=%s vgUUID=%s "
                     "storageType=%s version=%s", sdUUID, domainName, domClass,
                     vgUUID, storageType, version)

        if not misc.isAscii(domainName) and not sd.supportsUnicode(version):
            raise se.UnicodeArgumentException()

        if len(domainName) > sd.MAX_DOMAIN_DESCRIPTION_SIZE:
            raise se.StorageDomainDescriptionTooLongError()

        sd.validateDomainVersion(version)

        vg = lvm.getVGbyUUID(vgUUID)
        vgName = vg.name

        if set((STORAGE_UNREADY_DOMAIN_TAG,)) != set(vg.tags):
            raise se.VolumeGroupHasDomainTag(vgUUID)
        try:
            lvm.getLV(vgName)
            raise se.StorageDomainNotEmpty(vgUUID)
        except se.LogicalVolumeDoesNotExistError:
            pass

        numOfPVs = len(lvm.listPVNames(vgName))
        if version in VERS_METADATA_LV and numOfPVs > MAX_PVS:
            cls.log.debug("%d > %d", numOfPVs, MAX_PVS)
            raise se.StorageDomainIsMadeFromTooManyPVs()

        # Create metadata service volume
        metasize = cls.metaSize(vgName)
        lvm.createLV(vgName, sd.METADATA, "%s" % (metasize))
        # Create the mapping right now so the index 0 is guaranteed
        # to belong to the metadata volume. Since the metadata is at
        # least SDMETADATA/METASIZE units, we know we can use the first
        # SDMETADATA bytes of the metadata volume for the SD metadata.
        # pass metadata's dev to ensure it is the first mapping
        mapping = cls.getMetaDataMapping(vgName)

        # Create the rest of the BlockSD internal volumes
        for metaFile, metaSizeMb in sd.SPECIAL_VOLUME_SIZES_MIB.iteritems():
            lvm.createLV(vgName, metaFile, metaSizeMb)

        lvm.createLV(vgName, MASTERLV, MASTERLV_SIZE)

        # Create VMS file system
        _createVMSfs(os.path.join("/dev", vgName, MASTERLV))

        lvm.deactivateLVs(vgName, MASTERLV)

        path = lvm.lvPath(vgName, sd.METADATA)

        # Zero out the metadata and special volumes before use
        try:
            misc.ddCopy("/dev/zero", path, RESERVED_METADATA_SIZE)
            path = lvm.lvPath(vgName, sd.INBOX)
            misc.ddCopy("/dev/zero", path, RESERVED_MAILBOX_SIZE)
            path = lvm.lvPath(vgName, sd.OUTBOX)
            misc.ddCopy("/dev/zero", path, RESERVED_MAILBOX_SIZE)
        except utils.ActionStopped:
            raise
        except se.StorageException:
            raise se.VolumesZeroingError(path)

        if version in VERS_METADATA_LV:
            md = LvBasedSDMetadata(vgName, sd.METADATA)
        elif version in VERS_METADATA_TAG:
            md = TagBasedSDMetadata(vgName)

        logBlkSize, phyBlkSize = lvm.getVGBlockSizes(vgName)

        # create domain metadata
        # FIXME : This is 99% like the metadata in file SD
        #         Do we really need to keep the VGUUID?
        #         no one reads it from here anyway
        initialMetadata = {
            sd.DMDK_VERSION: version,
            sd.DMDK_SDUUID: sdUUID,
            sd.DMDK_TYPE: storageType,
            sd.DMDK_CLASS: domClass,
            sd.DMDK_DESCRIPTION: domainName,
            sd.DMDK_ROLE: sd.REGULAR_DOMAIN,
            sd.DMDK_POOLS: [],
            sd.DMDK_LOCK_POLICY: '',
            sd.DMDK_LOCK_RENEWAL_INTERVAL_SEC: sd.DEFAULT_LEASE_PARAMS[
                sd.DMDK_LOCK_RENEWAL_INTERVAL_SEC],
            sd.DMDK_LEASE_TIME_SEC: sd.DEFAULT_LEASE_PARAMS[
                sd.DMDK_LEASE_TIME_SEC],
            sd.DMDK_IO_OP_TIMEOUT_SEC: sd.DEFAULT_LEASE_PARAMS[
                sd.DMDK_IO_OP_TIMEOUT_SEC],
            sd.DMDK_LEASE_RETRIES: sd.DEFAULT_LEASE_PARAMS[
                sd.DMDK_LEASE_RETRIES],
            DMDK_VGUUID: vgUUID,
            DMDK_LOGBLKSIZE: logBlkSize,
            DMDK_PHYBLKSIZE: phyBlkSize,
        }

        initialMetadata.update(mapping)

        md.update(initialMetadata)

        # Mark VG with Storage Domain Tag
        try:
            lvm.replaceVGTag(vgName, STORAGE_UNREADY_DOMAIN_TAG,
                             STORAGE_DOMAIN_TAG)
        except se.StorageException:
            raise se.VolumeGroupUninitialized(vgName)

        bsd = BlockStorageDomain(sdUUID)

        bsd.initSPMlease()

        return bsd

    def getVolumeClass(self):
        """
        Return a type specific volume generator object
        """
        return blockVolume.BlockVolume

    def getVAllocSize(self, imgUUID, volUUID):
        return self._manifest.getVSize(imgUUID, volUUID)

    def validateCreateVolumeParams(self, volFormat, srcVolUUID,
                                   preallocate=None):
        super(BlockStorageDomain, self).validateCreateVolumeParams(
            volFormat, srcVolUUID, preallocate=preallocate)
        # Sparse-Raw not supported for block volumes
        if preallocate == volume.SPARSE_VOL and volFormat == volume.RAW_FORMAT:
            raise se.IncorrectFormat(volume.type2name(volFormat))

    @classmethod
    def getMetaDataMapping(cls, vgName, oldMapping={}):
        firstDev, firstExtent = lvm.getFirstExt(vgName, sd.METADATA)
        firstExtent = int(firstExtent)
        if firstExtent != 0:
            cls.log.error("INTERNAL: metadata ext is not 0")
            raise se.MetaDataMappingError("vg %s: metadata extent is not the "
                                          "first extent" % vgName)

        pvlist = list(lvm.listPVNames(vgName))

        pvlist.remove(firstDev)
        pvlist.insert(0, firstDev)
        cls.log.info("Create: SORT MAPPING: %s" % pvlist)

        mapping = {}
        devNum = len(oldMapping)
        for dev in pvlist:
            knownDev = False
            for pvID, oldInfo in oldMapping.iteritems():
                if os.path.basename(dev) == oldInfo["guid"]:
                    mapping[pvID] = oldInfo
                    knownDev = True
                    break

            if knownDev:
                continue

            pv = lvm.getPV(dev)
            pvInfo = {}
            pvInfo["guid"] = os.path.basename(pv.name)
            pvInfo["uuid"] = pv.uuid
            # this is another trick, it's not the
            # the pestart value you expect, it's just
            # 0, always
            pvInfo["pestart"] = 0
            pvInfo["pecount"] = pv.pe_count
            if devNum == 0:
                mapOffset = 0
            else:
                prevDevNum = devNum - 1
                try:
                    prevInfo = mapping["PV%d" % (prevDevNum,)]
                except KeyError:
                    prevInfo = oldMapping["PV%d" % (prevDevNum,)]

                mapOffset = int(prevInfo["mapoffset"]) + \
                    int(prevInfo["pecount"])

            pvInfo["mapoffset"] = mapOffset
            mapping["PV%d" % devNum] = pvInfo
            devNum += 1

        return mapping

    def updateMapping(self):
        # First read existing mapping from metadata
        with self._metadata.transaction():
            mapping = self.getMetaDataMapping(self.sdUUID,
                                              self.readMetadataMapping())
            for key in set(self._metadata.keys() + mapping.keys()):
                if DMDK_PV_REGEX.match(key):
                    if key in mapping:
                        self._metadata[key] = mapping[key]
                    else:
                        del self._metadata[key]

    def extend(self, devlist, force):
        with self._extendlock:
            if self.getVersion() in VERS_METADATA_LV:
                mapping = self.readMetadataMapping().values()
                if len(mapping) + len(devlist) > MAX_PVS:
                    raise se.StorageDomainIsMadeFromTooManyPVs()

            knowndevs = set(multipath.getMPDevNamesIter())
            unknowndevs = set(devlist) - knowndevs
            if unknowndevs:
                raise se.InaccessiblePhysDev(unknowndevs)

            lvm.extendVG(self.sdUUID, devlist, force)
            self.updateMapping()
            newsize = self.metaSize(self.sdUUID)
            lvm.extendLV(self.sdUUID, sd.METADATA, newsize)

    def resizePV(self, guid):
        with self._extendlock:
            lvm.resizePV(self.sdUUID, guid)
            self.updateMapping()
            newsize = self.metaSize(self.sdUUID)
            lvm.extendLV(self.sdUUID, sd.METADATA, newsize)

    _lvTagMetaSlotLock = threading.Lock()

    @contextmanager
    def acquireVolumeMetadataSlot(self, vol_name, slotSize):
        # TODO: Check if the lock is needed when using
        # getVolumeMetadataOffsetFromPvMapping()
        with self._lvTagMetaSlotLock:
            if self.getVersion() in VERS_METADATA_LV:
                yield self.getVolumeMetadataOffsetFromPvMapping(vol_name)
            else:
                yield self.getFreeMetadataSlot(slotSize)

    def _getOccupiedMetadataSlots(self):
        stripPrefix = lambda s, pfx: s[len(pfx):]
        occupiedSlots = []
        for lv in lvm.getLV(self.sdUUID):
            if lv.name in SPECIAL_LVS:
                # Special LVs have no mapping
                continue

            offset = None
            size = blockVolume.VOLUME_MDNUMBLKS
            for tag in lv.tags:
                if tag.startswith(blockVolume.TAG_PREFIX_MD):
                    offset = int(stripPrefix(tag, blockVolume.TAG_PREFIX_MD))

                if tag.startswith(blockVolume.TAG_PREFIX_MDNUMBLKS):
                    size = int(stripPrefix(tag,
                                           blockVolume.TAG_PREFIX_MDNUMBLKS))

                if offset is not None and size != blockVolume.VOLUME_MDNUMBLKS:
                    # I've found everything I need
                    break

            if offset is None:
                self.log.warn("Could not find mapping for lv %s/%s",
                              self.sdUUID, lv.name)
                continue

            occupiedSlots.append((offset, size))

        occupiedSlots.sort(key=itemgetter(0))
        return occupiedSlots

    def getFreeMetadataSlot(self, slotSize):
        occupiedSlots = self._getOccupiedMetadataSlots()

        # It might look weird skipping the sd metadata when it has been moved
        # to tags. But this is here because domain metadata and volume metadata
        # look the same. The domain might get confused and think it has lv
        # metadata if it finds something is written in that area.
        freeSlot = (SD_METADATA_SIZE + self.logBlkSize - 1) / self.logBlkSize

        for offset, size in occupiedSlots:
            if offset - freeSlot > slotSize:
                break

            freeSlot = offset + size

        self.log.debug("Found freeSlot %s in VG %s", freeSlot, self.sdUUID)
        return freeSlot

    def getVolumeMetadataOffsetFromPvMapping(self, vol_name):
        dev, ext = lvm.getFirstExt(self.sdUUID, vol_name)
        self.log.debug("vol %s dev %s ext %s" % (vol_name, dev, ext))
        for pv in self.readMetadataMapping().values():
            self.log.debug("MAPOFFSET: pv %s -- dev %s ext %s" %
                           (pv, dev, ext))
            pestart = int(pv["pestart"])
            pecount = int(pv["pecount"])
            if (os.path.basename(dev) == pv["guid"] and
                    int(ext) in range(pestart, pestart + pecount)):

                offs = int(ext) + int(pv["mapoffset"])
                if offs < SD_METADATA_SIZE / sd.METASIZE:
                    raise se.MetaDataMappingError(
                        "domain %s: vol %s MD offset %s is bad - will "
                        "overwrite SD's MD" % (self.sdUUID, vol_name, offs))
                return offs
        raise se.MetaDataMappingError("domain %s: can't map PV %s ext %s" %
                                      (self.sdUUID, dev, ext))

    def readMetadataMapping(self):
        meta = self.getMetadata()
        for key in meta.keys():
            if not DMDK_PV_REGEX.match(key):
                del meta[key]

        self.log.info("META MAPPING: %s" % meta)
        return meta

    def getLeasesFileSize(self):
        lv = lvm.getLV(self.sdUUID, sd.LEASES)
        return int(lv.size)

    def selftest(self):
        """
        Run the underlying VG validation routine
        """

        timeout = config.getint("irs", "repo_stats_cache_refresh_timeout")
        now = time.time()

        if now - self._lastUncachedSelftest > timeout:
            self._lastUncachedSelftest = now
            lvm.chkVG(self.sdUUID)
        elif lvm.getVG(self.sdUUID).partial != lvm.VG_OK:
            raise se.StorageDomainAccessError(self.sdUUID)

    def validate(self):
        """
        Validate that the storage domain metadata
        """
        self.log.info("sdUUID=%s", self.sdUUID)
        lvm.chkVG(self.sdUUID)
        self.invalidateMetadata()
        if not len(self.getMetadata()):
            raise se.StorageDomainAccessError(self.sdUUID)

    def invalidate(self):
        """
        Make sure that storage domain is inaccessible.
        1. Make sure master LV is not mounted
        2. Deactivate all the volumes from the underlying VG
        3. Destroy any possible dangling maps left in device mapper
        """
        try:
            self.unmountMaster()
        except se.StorageDomainMasterUnmountError:
            self.log.warning("Unable to unmount master LV during invalidateSD")
        except se.CannotDeactivateLogicalVolume:
            # It could be that at this point there is no LV, so just ignore it
            pass
        except Exception:
            # log any other exception, but keep going
            self.log.error("Unexpected error", exc_info=True)

        # FIXME: remove this and make sure nothing breaks
        try:
            lvm.deactivateVG(self.sdUUID)
        except Exception:
            # log any other exception, but keep going
            self.log.error("Unexpected error", exc_info=True)

        fileUtils.cleanupdir(os.path.join("/dev", self.sdUUID))

    @classmethod
    def format(cls, sdUUID):
        """Format detached storage domain.
           This removes all data from the storage domain.
        """
        # Remove the directory tree
        try:
            domaindir = cls.findDomainPath(sdUUID)
        except (se.StorageDomainDoesNotExist):
            pass
        else:
            fileUtils.cleanupdir(domaindir, ignoreErrors=True)
        # Remove special metadata and service volumes
        # Remove all volumes LV if exists
        _removeVMSfs(lvm.lvPath(sdUUID, MASTERLV))
        try:
            lvs = lvm.getLV(sdUUID)
        except se.LogicalVolumeDoesNotExistError:
            lvs = ()  # No LVs in this VG (domain)

        for lv in lvs:
            # Fix me: Should raise and get resource lock.
            try:
                lvm.removeLVs(sdUUID, lv.name)
            except se.CannotRemoveLogicalVolume as e:
                cls.log.warning("Remove logical volume failed %s/%s %s",
                                sdUUID, lv.name, str(e))

        lvm.removeVG(sdUUID)
        return True

    def getInfo(self):
        """
        Get storage domain info
        """
        # self.log.info("sdUUID=%s", self.sdUUID)
        # First call parent getInfo() - it fills in all the common details
        info = sd.StorageDomain.getInfo(self)
        # Now add blockSD specific data
        vg = lvm.getVG(self.sdUUID)  # vg.name = self.sdUUID
        info['vguuid'] = vg.uuid
        info['state'] = vg.partial
        return info

    def getStats(self):
        """
        """
        vg = lvm.getVG(self.sdUUID)
        vgMetadataStatus = metadataValidity(vg)
        return dict(disktotal=vg.size, diskfree=vg.free,
                    mdasize=vg.vg_mda_size, mdafree=vg.vg_mda_free,
                    mdavalid=vgMetadataStatus['mdavalid'],
                    mdathreshold=vgMetadataStatus['mdathreshold'])

    def getAllImages(self):
        """
        Get the set of all images uuids in the SD.
        """
        vols = self.getAllVolumes()  # {volName: ([imgs], parent)}
        images = set()
        for imgs, parent in vols.itervalues():
            images.update(imgs)
        return images

    def rmDCVolLinks(self, imgPath, volsImgs):
        for vol in volsImgs:
            lPath = os.path.join(imgPath, vol)
            removedPaths = []
            try:
                os.unlink(lPath)
            except OSError as e:
                self.log.warning("Can't unlink %s. %s", lPath, e)
            else:
                removedPaths.append(lPath)
        self.log.debug("removed: %s", removedPaths)
        return tuple(removedPaths)

    def rmDCImgDir(self, imgUUID, volsImgs):
        imgPath = os.path.join(self.domaindir, sd.DOMAIN_IMAGES, imgUUID)
        self.rmDCVolLinks(imgPath, volsImgs)
        try:
            os.rmdir(imgPath)
        except OSError:
            self.log.warning("Can't rmdir %s", imgPath, exc_info=True)
        else:
            self.log.debug("removed image dir: %s", imgPath)
        return imgPath

    def _getImgExclusiveVols(self, imgUUID, volsImgs):
        """Filter vols belonging to imgUUID only."""
        exclusives = dict((vName, v) for vName, v in volsImgs.iteritems()
                          if v.imgs[0] == imgUUID)
        return exclusives

    def __markForDelVols(self, sdUUID, imgUUID, volUUIDs, opTag):
        """
        Mark volumes that will be zeroed or removed.

        Mark for delete just in case that lvremove [lvs] success partialy.
        Mark for zero just in case that zero process is interrupted.

        Tagging is preferable to rename since it can be done in a single lvm
        operation and is resilient to open LVs, etc.
        """
        try:
            lvm.changelv(sdUUID, volUUIDs, (("-a", "y"),
                         ("--deltag", blockVolume.TAG_PREFIX_IMAGE + imgUUID),
                         ("--addtag", blockVolume.TAG_PREFIX_IMAGE +
                          opTag + imgUUID)))
        except se.StorageException as e:
            log.error("Can't activate or change LV tags in SD %s. "
                      "failing Image %s %s operation for vols: %s. %s",
                      sdUUID, imgUUID, opTag, volUUIDs, e)
            raise

    def deleteImage(self, sdUUID, imgUUID, volsImgs):
        toDel = self._getImgExclusiveVols(imgUUID, volsImgs)
        self.__markForDelVols(sdUUID, imgUUID, toDel, sd.REMOVED_IMAGE_PREFIX)
        deleteVolumes(sdUUID, toDel)
        self.rmDCImgDir(imgUUID, volsImgs)

    def zeroImage(self, sdUUID, imgUUID, volsImgs):
        toZero = self._getImgExclusiveVols(imgUUID, volsImgs)
        self.__markForDelVols(sdUUID, imgUUID, toZero, sd.ZEROED_IMAGE_PREFIX)
        zeroImgVolumes(sdUUID, imgUUID, toZero)
        self.rmDCImgDir(imgUUID, volsImgs)

    def deactivateImage(self, imgUUID):
        """
        Deactivate all the volumes belonging to the image.

        imgUUID: the image to be deactivated.

        If the image is based on a template image it should be expressly
        deactivated.
        """
        self.removeImageLinks(imgUUID)
        allVols = self.getAllVolumes()
        volUUIDs = self._getImgExclusiveVols(imgUUID, allVols)
        lvm.deactivateLVs(self.sdUUID, volUUIDs)

    def getAllVolumesImages(self):
        """
        Return all the images that depend on a volume.

        Return dicts:
        vols = {volUUID: ([imgUUID1, imgUUID2], parentUUID)]}
        for complete images.
        remnants (same) for broken imgs, orphan volumes, etc.
        """
        vols = {}  # The "legal" volumes: not half deleted/removed volumes.
        remnants = {}  # Volumes which are part of failed image deletes.
        allVols = getAllVolumes(self.sdUUID)
        for volName, ip in allVols.iteritems():
            if (volName.startswith(sd.REMOVED_IMAGE_PREFIX) or
                    ip.imgs[0].startswith(sd.REMOVED_IMAGE_PREFIX)):
                        remnants[volName] = ip
            else:
                # Deleted images are not dependencies of valid volumes.
                images = [img for img in ip.imgs
                          if not img.startswith(sd.REMOVED_IMAGE_PREFIX)]
                vols[volName] = sd.ImgsPar(images, ip.parent)
        return vols, remnants

    def getAllVolumes(self):
        vols, rems = self.getAllVolumesImages()
        return vols

    def getAllRemnants(self):
        vols, rems = self.getAllVolumesImages()
        return rems

    def linkBCImage(self, imgPath, imgUUID):
        dst = self.getLinkBCImagePath(imgUUID)
        self.log.debug("Creating symlink from %s to %s", imgPath, dst)
        try:
            os.symlink(imgPath, dst)
        except OSError as e:
            if e.errno == errno.EEXIST:
                self.log.debug("path to image directory already exists: %s",
                               dst)
            else:
                self.log.error("Failed to create path to image directory: %s",
                               dst)
                raise
        return dst

    def unlinkBCImage(self, imgUUID):
        img_path = self.getLinkBCImagePath(imgUUID)
        if os.path.islink(img_path):
            self.log.debug("Removing image directory link %r", img_path)
            os.unlink(img_path)

    def createImageLinks(self, srcImgPath, imgUUID, volUUIDs):
        """
        qcow chain is build by reading each qcow header and reading the path
        to the parent. When creating the qcow layer, we pass a relative path
        which allows us to build a directory with links to all volumes in the
        chain anywhere we want. This method creates a directory with the image
        uuid under /var/run/vdsm and creates sym links to all the volumes in
        the chain.

        srcImgPath: Dir where the image volumes are.
        """
        sdRunDir = os.path.join(constants.P_VDSM_STORAGE, self.sdUUID)
        imgRunDir = os.path.join(sdRunDir, imgUUID)
        fileUtils.createdir(imgRunDir)
        for volUUID in volUUIDs:
            srcVol = os.path.join(srcImgPath, volUUID)
            dstVol = os.path.join(imgRunDir, volUUID)
            self.log.debug("Creating symlink from %s to %s", srcVol, dstVol)
            try:
                os.symlink(srcVol, dstVol)
            except OSError as e:
                if e.errno == errno.EEXIST:
                    self.log.debug("img run vol already exists: %s", dstVol)
                else:
                    self.log.error("Failed to create img run vol: %s", dstVol)
                    raise

        return imgRunDir

    def removeImageLinks(self, imgUUID):
        """
        Remove /run/vdsm/storage/sd_uuid/img_uuid directory, created in
        createImageLinks.

        Should be called when tearing down an image.
        """
        fileUtils.cleanupdir(self.getImageRundir(imgUUID))

    def activateVolumes(self, imgUUID, volUUIDs):
        """
        Activate all the volumes belonging to the image.

        imgUUID: the image to be deactivated.
        allVols: getAllVolumes result.

        If the image is based on a template image it will be activated.
        """
        lvm.activateLVs(self.sdUUID, volUUIDs)
        vgDir = os.path.join("/dev", self.sdUUID)
        return self.createImageLinks(vgDir, imgUUID, volUUIDs)

    def getVolumeLease(self, imgUUID, volUUID):
        """
        Return the volume lease (leasePath, leaseOffset)
        """
        if self.hasVolumeLeases():
            # TODO: use the sanlock specific offset when present
            leaseSlot = self.produceVolume(imgUUID, volUUID).getMetaOffset()
            leaseOffset = ((leaseSlot + blockVolume.RESERVED_LEASES) *
                           self.logBlkSize * sd.LEASE_BLOCKS)
            return self.getLeasesFilePath(), leaseOffset
        return None, None

    def validateMasterMount(self):
        return mount.isMounted(self.getMasterDir())

    def mountMaster(self):
        """
        Mount the master metadata file system. Should be called only by SPM.
        """
        lvm.activateLVs(self.sdUUID, MASTERLV)
        masterDir = os.path.join(self.domaindir, sd.MASTER_FS_DIR)
        fileUtils.createdir(masterDir)

        masterfsdev = lvm.lvPath(self.sdUUID, MASTERLV)
        cmd = [constants.EXT_FSCK, "-p", masterfsdev]
        (rc, out, err) = misc.execCmd(cmd, sudo=True,
                                      deathSignal=signal.SIGKILL)
        # fsck exit codes
        # 0    - No errors
        # 1    - File system errors corrected
        # 2    - File system errors corrected, system should
        #        be rebooted
        # 4    - File system errors left uncorrected
        # 8    - Operational error
        # 16   - Usage or syntax error
        # 32   - E2fsck canceled by user request
        # 128  - Shared library error
        if rc == 1 or rc == 2:
            # rc is a number
            self.log.info("fsck corrected fs errors (%s)", rc)
        if rc >= 4:
            raise se.BlockStorageDomainMasterFSCKError(masterfsdev, rc)

        # TODO: Remove when upgrade is only from a version which creates ext3
        # Try to add a journal - due to unfortunate circumstances we exposed
        # to the public the code that created ext2 file system instead of ext3.
        # In order to make up for it we are trying to add journal here, just
        # to be sure (and we have fixed the file system creation).
        # If there is a journal already tune2fs will do nothing, indicating
        # this condition only with exit code. However, we do not really care.
        cmd = [constants.EXT_TUNE2FS, "-j", masterfsdev]
        misc.execCmd(cmd, sudo=True, deathSignal=signal.SIGKILL)

        masterMount = mount.Mount(masterfsdev, masterDir)

        try:
            masterMount.mount(vfstype=mount.VFS_EXT3)
        except mount.MountError as ex:
            rc, out = ex
            raise se.BlockStorageDomainMasterMountError(masterfsdev, rc, out)

        cmd = [constants.EXT_CHOWN, "%s:%s" %
               (constants.METADATA_USER, constants.METADATA_GROUP), masterDir]
        (rc, out, err) = misc.execCmd(cmd, sudo=True)
        if rc != 0:
            self.log.error("failed to chown %s", masterDir)

    @classmethod
    def __handleStuckUmount(cls, masterDir):
        umountPids = utils.pgrep("umount")
        try:
            masterMount = mount.getMountFromTarget(masterDir)
        except OSError as ex:
            if ex.errno == errno.ENOENT:
                return

            raise

        for umountPid in umountPids:
            try:
                state = utils.pidStat(umountPid).state
                mountPoint = utils.getCmdArgs(umountPid)[-1]
            except:
                # Process probably exited
                continue

            if mountPoint != masterDir:
                continue

            if state != "D":
                # If the umount is not in d state there
                # is a possibility that the world might
                # be in flux and umount will get stuck
                # in an unkillable state that is not D
                # which I don't know about, perhaps a
                # bug in umount will cause umount to
                # wait for something unrelated that is
                # not the syscall. Waiting on a process
                # which is not your child is race prone
                # I will just call for another umount
                # and wait for it to finish. That way I
                # know that a umount ended.
                try:
                    masterMount.umount()
                except mount.MountError:
                    # timeout! we are stuck again.
                    # if you are here spmprotect forgot to
                    # reboot the machine but in any case
                    # continue with the disconnection.
                    pass

            try:
                vgName = masterDir.rsplit("/", 2)[1]
                masterDev = os.path.join(
                    "/dev/mapper", vgName.replace("-", "--") + "-" + MASTERLV)
            except KeyError:
                # Umount succeeded after all
                return

            cls.log.warn("master mount resource is `%s`, trying to disconnect "
                         "underlying storage", masterDev)
            iscsi.disconnectFromUndelyingStorage(masterDev)

    @classmethod
    def doUnmountMaster(cls, masterdir):
        """
        Unmount the master metadata file system. Should be called only by SPM.
        """
        # fuser processes holding mount point and validate that the umount
        # succeeded
        cls.__handleStuckUmount(masterdir)
        try:
            masterMount = mount.getMountFromTarget(masterdir)
        except OSError as ex:
            if ex.errno == errno.ENOENT:
                return

            raise
        if masterMount.isMounted():
            # Try umount, take 1
            try:
                masterMount.umount()
            except mount.MountError:
                # umount failed, try to kill that processes holding mount point
                svdsmp = svdsm.getProxy()
                pids = svdsmp.fuser(masterMount.fs_file, mountPoint=True)

                # It was unmounted while I was checking no need to do anything
                if not masterMount.isMounted():
                    return

                if len(pids) == 0:
                    cls.log.warn("Unmount failed because of errors that fuser "
                                 "can't solve")
                else:
                    for pid in pids:
                        try:
                            cls.log.debug("Trying to kill pid %d", pid)
                            os.kill(pid, signal.SIGKILL)
                        except OSError as e:
                            if e.errno == errno.ESRCH:  # No such process
                                pass
                            elif e.errno == errno.EPERM:  # Op. not permitted
                                cls.log.warn("Could not kill pid %d because "
                                             "operation was not permitted",
                                             pid)
                            else:
                                cls.log.warn("Could not kill pid %d because an"
                                             " unexpected error",
                                             exc_info=True)
                        except:
                            cls.log.warn("Could not kill pid %d because an "
                                         "unexpected error", exc_info=True)

                # Try umount, take 2
                try:
                    masterMount.umount()
                except mount.MountError:
                    pass

                if masterMount.isMounted():
                    # We failed to umount masterFS
                    # Forcibly rebooting the SPM host would be safer. ???
                    raise se.StorageDomainMasterUnmountError(masterdir, 1)

    def unmountMaster(self):
        """
        Unmount the master metadata file system. Should be called only by SPM.
        """
        masterdir = os.path.join(self.domaindir, sd.MASTER_FS_DIR)
        self.doUnmountMaster(masterdir)
        # It is time to deactivate the master LV now
        lvm.deactivateLVs(self.sdUUID, MASTERLV)

    def refreshDirTree(self):
        # create domain images folder
        imagesPath = os.path.join(self.domaindir, sd.DOMAIN_IMAGES)
        fileUtils.createdir(imagesPath)

        # create domain special volumes folder
        domMD = os.path.join(self.domaindir, sd.DOMAIN_META_DATA)
        fileUtils.createdir(domMD)

        lvm.activateLVs(self.sdUUID, SPECIAL_LVS)
        for lvName in SPECIAL_LVS:
            dst = os.path.join(domMD, lvName)
            if not os.path.lexists(dst):
                src = lvm.lvPath(self.sdUUID, lvName)
                self.log.debug("Creating symlink from %s to %s", src, dst)
                os.symlink(src, dst)

    def extendVolume(self, volumeUUID, size, isShuttingDown=None):
        self._extendlock.acquire()
        try:
            # FIXME: following line.
            lvm.extendLV(self.sdUUID, volumeUUID, size)  # , isShuttingDown)
        finally:
            self._extendlock.release()

    def refresh(self):
        self.refreshDirTree()
        lvm.invalidateVG(self.sdUUID)
        self.replaceMetadata(selectMetadata(self.sdUUID))

    @staticmethod
    def findDomainPath(sdUUID):
        try:
            vg = lvm.getVG(sdUUID)
        except se.VolumeGroupDoesNotExist:
            raise se.StorageDomainDoesNotExist(sdUUID)

        if _isSD(vg):
            return vg.name

        raise se.StorageDomainDoesNotExist(sdUUID)


def _createVMSfs(dev):
    """
    Create a special file system to store VM data
    """
    cmd = [constants.EXT_MKFS, "-q", "-j", "-E", "nodiscard", dev]
    rc = misc.execCmd(cmd, sudo=True, deathSignal=signal.SIGKILL)[0]
    if rc != 0:
        raise se.MkfsError(dev)


def _removeVMSfs(dev):
    """
    Destroy special VM data file system
    """
    # XXX Add at least minimal sanity check:. i.e. fs not mounted
    pass


def _isSD(vg):
    return STORAGE_DOMAIN_TAG in vg.tags


def findDomain(sdUUID):
    return BlockStorageDomain(BlockStorageDomain.findDomainPath(sdUUID))


def getStorageDomainsList():
    return [vg.name for vg in lvm.getAllVGs() if _isSD(vg)]
