# Packages names
%global vdsm_name vdsm

# Required users and groups
%global vdsm_user vdsm
%global vdsm_group kvm
%global qemu_user qemu
%global qemu_group qemu
%global snlk_group sanlock
%global snlk_user sanlock
%global cdrom_group cdrom

# Glusterfs package version
%global gluster_version 3.7.1

# koji build - overridable using rpmbuild --define "fedora_koji_build 1"
%{!?fedora_koji_build: %global fedora_koji_build 0}

# RHEV build - overridable using rpmbuild --define "rhev_build 1"
%{!?rhev_build: %global rhev_build 0}

%if 0%{fedora_koji_build}
%global with_hooks 1
%endif

# Default to skipping autoreconf.  Distros can change just this one line
# (or provide a command-line override) if they backport any patches that
# touch configure.ac or Makefile.am.
%{!?enable_autotools:%define enable_autotools 0}

# Skips check since rhel default repos lack pep8 and pyflakes
%if ! 0%{?rhel}
%{!?with_check:%global with_check 1}
%else
%{!?with_check:%global with_check 0}
%endif

# Required paths
%if 0%{?fedora}
%global _polkitdir %{_datadir}/polkit-1/rules.d
%else
%global _polkitdir %{_localstatedir}/lib/polkit-1/localauthority/10-vendor.d
%endif

# Gluster should not be shipped with RHEV
%if ! 0%{?rhev_build}
%global with_gluster 1
%endif

%if ! 0%{?rhel} || ! 0%{fedora_koji_build}
%global with_vhostmd 1
%endif

%global _udevrulesdir /usr/lib/udev/rules.d/
%global _udevexecdir /usr/lib/udev/

Name:           %{vdsm_name}
Version:        4.17.23.2
Release:        0%{?dist}%{?extra_release}
Summary:        Virtual Desktop Server Manager
BuildArch:      noarch

Group:          Applications/System
License:        GPLv2+
Url:            http://www.ovirt.org/wiki/Vdsm
Source0:        %{vdsm_name}-%{version}.tar.gz
BuildRoot:      %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)

%{!?_licensedir:%global license %%doc}

BuildRequires: cyrus-sasl-lib
BuildRequires: gcc
BuildRequires: python
BuildRequires: python-devel
BuildRequires: python-netaddr
BuildRequires: python-nose
BuildRequires: python-six
BuildRequires: rpm-build

# BuildRequires needed by the tests during the build
BuildRequires: dosfstools
BuildRequires: genisoimage
BuildRequires: libnl3
BuildRequires: libselinux-python
BuildRequires: libvirt-python
BuildRequires: m2crypto
BuildRequires: mom >= 0.4.5
BuildRequires: openssl
BuildRequires: policycoreutils-python
BuildRequires: psmisc
BuildRequires: python-cpopen >= 1.3
BuildRequires: python-inotify
BuildRequires: python-ioprocess >= 0.15.0-4
BuildRequires: python-pthreading
BuildRequires: qemu-img
BuildRequires: rpm-python
BuildRequires: python-blivet

# Autotools BuildRequires
%if 0%{?enable_autotools}
BuildRequires: autoconf
BuildRequires: automake
BuildRequires: gettext-devel
BuildRequires: libtool
%endif

%if 0%{?with_check}
BuildRequires: pyflakes
BuildRequires: python-pep8
%endif

BuildRequires: systemd-units

Requires: ethtool
Requires: which
Requires: sudo >= 1.7.3
Requires: logrotate
Requires: xz
Requires: ntp
Requires: iproute >= 3.10.0
Requires: python-netaddr
Requires: python-inotify
Requires: python-argparse
Requires: python-cpopen >= 1.3
Requires: python-ioprocess >= 0.15.0-4
Requires: python-pthreading >= 0.1.3-3
Requires: python-six
Requires: python-requests
Requires: %{name}-infra = %{version}-%{release}
Requires: rpm-python
Requires: nfs-utils
Requires: m2crypto
Requires: libnl3
Requires: curl
Requires: %{name}-xmlrpc = %{version}-%{release}
Requires: %{name}-jsonrpc = %{version}-%{release}
%if 0%{?fedora} >= 23
Requires: safelease >= 1.0-6
%else
Requires: safelease >= 1.0-5
%endif
Requires: mom >= 0.4.5
Requires: ovirt-vmconsole >= 1.0.0-0

%if 0%{?rhel}
Requires: libguestfs-tools-c >= 1:1.20.11-10
%else # fedora
Requires: libguestfs-tools-c >= 1:1.26.7-2
%endif

Requires: libvirt-daemon-config-nwfilter
Requires: libvirt-daemon-driver-network
Requires: libvirt-daemon-driver-nwfilter
Requires: libvirt-daemon-driver-qemu

%if 0%{?rhel}
Requires: libvirt-daemon >= 1.2.17-9
Requires: libvirt-python >= 1.2.17-2
%endif # rhel

%if 0%{?fedora} >= 23
Requires: libvirt-daemon >= 1.2.18.1-1
Requires: libvirt-python >= 1.2.18-1
%endif

%if 0%{?fedora} == 22
Requires: libvirt-daemon >= 1.2.13
Requires: libvirt-python >= 1.2.9-2
%endif

Requires: libvirt-lock-sanlock, libvirt-client

# iscsi-intiator versions
%if 0%{?rhel}
Requires: iscsi-initiator-utils
%else # fedora
Requires: iscsi-initiator-utils >= 6.2.0.873-21
%endif

Requires: sanlock >= 2.8-2, sanlock-python

# device-mapper-multipath

%if 0%{?rhel}
Requires: device-mapper-multipath >= 0.4.9-84.el7
%endif #rhel

%if 0%{?fedora} == 22
Requires: device-mapper-multipath >= 0.4.9-73.fc22.2
%endif

%if 0%{?fedora} >= 23
Requires: device-mapper-multipath >= 0.4.9-80.fc23
%endif

%if 0%{?rhel}
Requires: e2fsprogs
Requires: fence-agents-all
%if 0%{?centos}
Requires: kernel >= 3.10.0-132.el7
%else
Requires: kernel >= 3.10.0-229.17.1.el7
%endif
%if 0%{?centos}
# TODO: Remove when lvm2 2.02.130 is available
Requires: lvm2 >= 2.02.107
%else
Requires: lvm2 >= 2.02.130-2
%endif
Requires: python >= 2.7.5-18.el7_1.1
Requires: policycoreutils-python
Requires: selinux-policy-targeted >= 3.13.1-16.el7
%else
Requires: fence-agents-all
Requires: kernel >= 4.1.6
# Subprocess and thread bug was found on python 2.7.2
Requires: python >= 2.7.3
Requires: initscripts >= 9.42.2-1
Requires: e2fsprogs >= 1.41.14
%if 0%{?fedora} >= 23
Requires: policycoreutils-python-utils
%endif # fedora 23
Requires: policycoreutils-python
Requires: sed >= 4.2.1-10
Requires: ed
Requires: lvm2 >= 2.02.107
Requires: selinux-policy-targeted >= 3.12.1-177
# In order to avoid a policycoreutils bug (rhbz 889698) when selinux is
# disabled we now require the version 2.1.13-55 (or newer) of Fedora.
Requires: policycoreutils >= 2.1.13-55
Requires: systemd >= 197-1.fc18.2
%endif

%if 0%{?rhel}
Requires: qemu-kvm-rhev >= 10:2.3.0-31.el7_2.4
Requires: qemu-img-rhev >= 10:2.3.0-31.el7_2.4
%else
Requires: qemu-kvm >= 2:2.1.3-11
Requires: qemu-img >= 2:2.1.3-11
%endif # rhel

# GlusterFS client-side RPMs needed for Gluster SD
%if 0%{?with_gluster}
Requires: glusterfs-cli >= %{gluster_version}
Requires: glusterfs-fuse >= %{gluster_version}
%endif

Requires: psmisc >= 22.6-15
Requires: bridge-utils
Requires: sos
Requires: tree
Requires: dosfstools
Requires: genisoimage
Requires: libselinux-python
Requires: %{name}-python = %{version}-%{release}
Requires: pyparted
Requires: %{name}-hook-vmfex-dev = %{version}-%{release}

Requires(post): /usr/sbin/saslpasswd2

%if 0%{?fedora}
Requires(post): hostname
%else
Requires(post): /bin/hostname
%endif

Conflicts: vdsm-hook-sriov

%description
The VDSM service is required by a Virtualization Manager to manage the
Linux hosts. VDSM manages and monitors the host's storage, memory and
networks as well as virtual machine creation, other host administration
tasks, statistics gathering, and log collection.

%package cli
Summary:        VDSM command line interface
Requires: %{name}-python = %{version}-%{release}
Requires: %{name}-xmlrpc = %{version}-%{release}

%description cli
Call VDSM commands from the command line. Used for testing and debugging.

%package xmlrpc
Summary:        VDSM xmlrpc API
Requires: %{name}-python = %{version}-%{release}


%description xmlrpc
An XMLRPC interface for interacting with vdsmd. Primary control interface for
ovirt-engine and vdsClient.

%package jsonrpc
Summary:        VDSM API Server
Requires:       %{name}-python = %{version}-%{release}
Requires:       %{name}-yajsonrpc = %{version}-%{release}
Obsoletes:      vdsm-api < 4.16

%description jsonrpc
A Json-based RPC interface that serves as the protocol for libvdsm.

%package yajsonrpc
Summary:        JSON RPC server and client implementation
Requires:       python >= 2.6

%description yajsonrpc
A JSON RPC server and client implementation.

%package infra
Summary:        Utilities and libraries for vdsm
Requires:       python >= 2.6
Obsoletes:      %{name}-python-zombiereaper

%description infra
Utilities and libraries for vdsm.

%package reg
Summary:        VDSM registration package
Requires: %{name} = %{version}-%{release}
Requires: m2crypto
Requires: openssl
Conflicts: ovirt-node < 3.0.4

%description reg
VDSM registration package. Used to register a Linux host to a Virtualization
Manager.

%package python
Summary:        VDSM python libraries
Requires:       %{name}-infra = %{version}-%{release}
Requires:       python-cpopen >= 1.2.3-5
Requires:       m2crypto
Requires:       python-ioprocess >= 0.15.0-4

%description python
Shared libraries between the various VDSM packages.

%package debug-plugin
Summary:        VDSM Debug Plugin
Requires:       %{name}
Requires:       %{name}-xmlrpc = %{version}-%{release}

%description debug-plugin
Used by the trained monkeys at Red Hat to insert chaos and mayhem in to VDSM.

%post python
# REQUIRED_FOR: Upgrade from 4.14 to 4.17
# HACK: Remove vdsm python lib __init__ file if installed on old location
# https://bugzilla.redhat.com/show_bug.cgi?id=1279167
if [ "$1" -ge 2 ]; then
    if [ -d "%{python2_sitearch}/%{vdsm_name}" ]; then
        logger -t '%{vdsm_name}' \
            'Disabling old vdsm package in %{python2_sitearch}/%{vdsm_name}.' \
            'Removing %{python2_sitearch}/%{vdsm_name}/init.py*'
        rm -f %{python2_sitearch}/%{vdsm_name}/__init__.py*
    fi
fi

%package tests
Summary:        VDSM Test Suite
Requires:       %{name} = %{version}-%{release}
Requires:       dracut
Requires:       python-nose

%description tests
A test suite for verifying the functionality of a running vdsm instance

%package hook-allocate_net
Summary:        random_network allocation hook for VDSM
Requires:       %{name}

%description hook-allocate_net
VDSM hook used to allocate networks for vms in a random fashion

%package hook-checkimages
Summary:        Qcow2 disk image format check hook for VDSM
Requires:       %{name}

%description hook-checkimages
VDSM hook used to perform consistency check on a qcow2 format disk image
using the QEMU disk image utility.

%package hook-diskunmap
Summary:        Activate UNMAP for disk/lun devices
BuildArch:      noarch
Requires:       qemu-kvm >= 1.5

%description hook-diskunmap
VDSM hooks which allow to activate disk UNMAP.

%package hook-ethtool-options
Summary:        Allow setting custom ethtool options for vdsm controlled nics
Requires:       %{name} = %{version}-%{release}

%description hook-ethtool-options
VDSM hook used for applying custom network properties that define ethtool
options for vdsm network nics

%if 0%{?with_vhostmd}
%package hook-vhostmd
Summary:        VDSM hook set for interaction with vhostmd
Requires:       vhostmd

%description hook-vhostmd
VDSM hook to use vhostmd per VM according to Virtualization Manager requests.
%endif

%package hook-faqemu
Summary:        Fake qemu process for VDSM quality assurance
Requires:       %{name}

%description hook-faqemu
VDSM hook used for testing VDSM with multiple fake virtual machines without
running real guests.
To enable this hook on your host, set vars.fake_kvm_support=True in your
/etc/vdsm/vdsm.conf before adding the host to ovirt-Engine.

%package hook-macbind
Summary:        Bind a vNIC to a Bridge
Requires:       %{name} >= 4.14

%description hook-macbind
VDSM hooks which allow to bind a vNIC to a Bridge, managed or not by engine.

%package hook-macspoof
Summary:        Disables MAC spoofing filtering

%description hook-macspoof
VDSM hooks which allow to disable mac spoof filtering
either on all the of the VM's interfaces or on
specific vnics.

%package hook-noipspoof
Summary:        Enables strict anti-spoofing filtering

%description hook-noipspoof
VDSM hook which allows to enable strict anti-spoofing filtering
on all of the the VM's interfaces.

%package hook-extnet
Summary:        Force a vNIC to connect to a specific libvirt network
Requires:       %{name} = %{version}-%{release}

%description hook-extnet
VDSM hook which allows to connect a vNIC to a libvirt network that is managed
outside of oVirt, such as an openvswitch network.

%package hook-fakevmstats
Summary:        Generate random VM statistics
Requires:       %{name}

%description hook-fakevmstats
Hook intercepts VM's stats and randomizes various fields.
To enable this hook on your host, set vars.fake_vmstats_enable=true in your
/etc/vdsm/vdsm.conf.

%package hook-fileinject
Summary:        Allow uploading file to VMs disk
Requires:       python-libguestfs

%description hook-fileinject
Hook is getting target file name and its content and
create that file in target machine.

%package hook-floppy
Summary:        Allow adding floppy to VM

%description hook-floppy
Allow adding floppy to VM

%package hook-hostusb
Summary:        Allow attaching USB device from host
Requires:       usbutils

%description hook-hostusb
Hook is getting vendor and product id of USB device
disconnect it from host and attach it to VM

%package hook-httpsisoboot
Summary:        Allow directly booting from an https available ISO
BuildArch:      noarch
%if 0%{?rhel}
Requires:       qemu-kvm-rhev >= 10:2.1.2-3
%endif

%description hook-httpsisoboot
Let the VM boot from an ISO image made available via an https URL without
the need to import the ISO into an ISO storage domain.
It doesn't support plain http.

%package hook-hugepages
Summary:        Huge pages enable user to handle VM with 2048KB page files.

%description hook-hugepages
Hook is getting number of huge pages reserve them for the VM,
and enable user to handle VM with 2048KB page files.

%package hook-isolatedprivatevlan
Summary:        Isolated network environment for VMs

%description hook-isolatedprivatevlan
limit VM traffic to a specific gateway by its mac address,
hook prevent VM from spoofing its mac or  ip address
by using <filterref filter='clean-traffic'/> libvirt filter
and by adding custom filter: isolatedprivatevlan-vdsm.xml

%package hook-nestedvt
Summary:        Nested Virtualization support for VDSM

%description hook-nestedvt
If the nested virtualization is enabled in your kvm module
this hook will expose it to the guests.

%package hook-numa
Summary:        NUMA support for VDSM

%description hook-numa
Hooks is getting number/rage of NUMA nodes and NUMA mode,
and update the VM xml.

%package hook-openstacknet
Summary:        OpenStack Network vNICs support for VDSM

%description hook-openstacknet
Hook for OpenStack Network vNICs.

%package hook-ovs
Summary:        Open vSwitch support for VDSM
BuildArch:      noarch
Requires:       %{name} = %{version}-%{release}
Requires:       openvswitch >= 2.0.0

%description hook-ovs
Hook for Open vSwitch support.

%package hook-pincpu
Summary:        Hook pin VM so specific CPUs

%description hook-pincpu
pincpu is hook for VDSM.
pincpu enable to pin virtual machine to a specific CPUs.

%package hook-promisc
Summary:        Network interface promiscuous mode support for VDSM

%description hook-promisc
VDSM promiscuous mode let user define a VM interface that will capture
all network traffic.

%package hook-qemucmdline
Summary:        QEMU cmdline hook for VDSM
Requires:       %{name}

%description hook-qemucmdline
Provides support for injecting QEMU cmdline via VDSM hook.
It exploits libvirt's qemu:commandline facility available in the
qemu xml namespace.

%package hook-qos
Summary:        QoS network in/out traffic support for VDSM

%description hook-qos
Hook adds QoS in/out traffic to VMs interfaces

%package hook-scratchpad
Summary:        One time disk creation for VDSM

%description hook-scratchpad
scratchpad hook for VDSM
Hook creates a disk for a VM onetime usage,
the disk will be erased when the VM destroyed.
VM cannot be migrated when using scratchpad hook

%package hook-smbios
Summary:        Adding custom smbios entries to libvirt domain via VDSM

%description hook-smbios
Adding custom smbios entries to libvirt domain via VDSM
such as: vendor, version, date and release

%package hook-spiceoptions
Summary:        To configure spice options for vm

%description hook-spiceoptions
This vdsm hook can be used to configure some of
the spice optimization attributes and values..

%package hook-vmfex
Summary:        vmfex support for VDSM
Conflicts:      hook-vmfex-dev

%description hook-vmfex
Hook for vmfex.

%package hook-vmfex-dev
Summary:        VM-FEX vNIC support for VDSM
Requires:       %{name} = %{version}-%{release}
Conflicts:      hook-vmfex

%description hook-vmfex-dev
Allows to use custom device properties to connect a guest vNIC to a host
VM-FEX Virtual Function (SR-IOV with macvtap mode).

%package hook-vmdisk
Summary:        External disk support for VDSM

%description hook-vmdisk
Hook adds additional disk image for a VM (raw or qcow2)

%package hook-ipv6
Summary:        Set IPv6 configuration through custom network properties
Requires:       %{name} >= 4.16.7

%description hook-ipv6
VDSM hook used for applying IPv6 configuration through custom network
properties

%if 0%{?with_gluster}
%package gluster
Summary:        Gluster Plugin for VDSM
Requires: %{name} = %{version}-%{release}
Requires: glusterfs-server >= %{gluster_version}
Requires: glusterfs-api >= %{gluster_version}
Requires: glusterfs-geo-replication >= %{gluster_version}
Requires: python-magic
Requires: python-blivet
Requires: xfsprogs

%description gluster
Gluster plugin enables VDSM to serve Gluster functionalities.
%endif

%prep
%setup -q

%build
%if 0%{?enable_autotools}
autoreconf -if
%endif
%configure %{?with_hooks:--enable-hooks} \
%if 0%{?rhev_build}
        --enable-rhev \
        --with-smbios-manufacturer='Red Hat' \
        --with-smbios-osname='RHEV Hypervisor' \
        --with-qemu-kvm='qemu-kvm-rhev' \
        --with-qemu-img='qemu-img-rhev' \
%endif

make
# Setting software_version and software_revision in dsaversion.py
baserelease=`echo "%{release}" | sed 's/\([0-9]\+\(\.[0-9]\+\)\?\).*/\1/'`
baseversion=`echo "%{version}" | sed 's/\([0-9]\+\(\.[0-9]\+\)\?\).*/\1/'`
rawversion=%{version}-%{release}
sed -i -e 's/^software_version =.*/software_version = "'"${baseversion}"'"/' \
       -e 's/^raw_version_revision =.*/raw_version_revision = "'"${rawversion}"'"/' \
       -e 's/^software_revision =.*/software_revision = "'"${baserelease}"'"/' vdsm/dsaversion.py

sed -i -e 's/@SSL_IMPLEMENTATION@/m2c/g' lib/vdsm/config.py

%install
rm -rf %{buildroot}
make DESTDIR=%{buildroot} install

# Creating VDSM logs in this session to avoid rpmbuild
# complain during the build
install -dDm 0755 %{buildroot}/var/log/vdsm
touch %{buildroot}/var/log/vdsm/{connectivity.log,mom.log,supervdsm.log,vdsm.log}

# Install the lvm rules
install -Dm 0644 vdsm/storage/vdsm-lvm.rules \
                 %{buildroot}%{_udevrulesdir}/12-vdsm-lvm.rules

install -Dm 0644 vdsm/limits.conf \
                 %{buildroot}/etc/security/limits.d/99-vdsm.conf

install -Dm 0755 init/systemd/systemd-vdsmd %{buildroot}/usr/lib/systemd/systemd-vdsmd
install -Dm 0644 init/systemd/85-vdsmd.preset %{buildroot}/usr/lib/systemd/system-preset/85-vdsmd.preset
install -Dm 0644 init/systemd/vdsmd.service %{buildroot}%{_unitdir}/vdsmd.service
install -Dm 0644 init/systemd/vdsm-network.service %{buildroot}%{_unitdir}/vdsm-network.service
install -Dm 0644 init/systemd/supervdsmd.service %{buildroot}%{_unitdir}/supervdsmd.service

install -Dm 0644 init/systemd/mom-vdsm.service %{buildroot}%{_unitdir}/mom-vdsm.service

install -Dm 0644 vdsm/vdsm-modules-load.d.conf \
                 %{buildroot}%{_sysconfdir}/modules-load.d/vdsm.conf
install -Dm 0644 init/systemd/vdsm-tmpfiles.d.conf \
                 %{buildroot}%{_tmpfilesdir}/%{vdsm_name}.conf
install -Dm 0644 init/systemd/unlimited-core.conf \
                 %{buildroot}%{_sysconfdir}/systemd/system/libvirtd.service.d/unlimited-core.conf

%if 0%{?rhel}
# This is not commonplace, but we want /var/log/core to be a world-writable
# dropbox for core dumps
install -dDm 1777 %{buildroot}%{_localstatedir}/log/core
%endif

# Install the polkit for libvirt
install -Dm 0644 vdsm/vdsm-libvirt-access.rules \
                 %{buildroot}%{_polkitdir}/10-vdsm-libvirt-access.rules

# Install the libvirt hook for cleaning up the XML
install -Dm 0755 vdsm/virt/libvirt-hook.sh \
                 %{buildroot}%{_sysconfdir}/libvirt/hooks/qemu

%check
%if 0%{?with_check}
make check
%endif

%clean
rm -rf %{buildroot}

%pre
# Force standard locale behavior (English)
export LC_ALL=C

/usr/bin/getent passwd %{vdsm_user} >/dev/null || \
    /usr/sbin/useradd -r -u 36 -g %{vdsm_group} -d /var/lib/vdsm \
        -s /sbin/nologin -c "Node Virtualization Manager" %{vdsm_user}
/usr/sbin/usermod -a -G %{qemu_group},%{snlk_group} %{vdsm_user}
/usr/sbin/usermod -a -G %{cdrom_group} %{qemu_user}

# We keep the previous rpm version number in a file for managing upgrade flow
# in vdsmd_init_script upgraded_version_check task
if [ "$1" -gt 1 ]; then
    rpm -q %{vdsm_name} > "%{_localstatedir}/lib/%{vdsm_name}/upgraded_version"
fi

%post
# After vdsm install we should create the logs files.
# In the install session we create it but since we use
# the ghost macro (in files session) the files are not included
touch /var/log/vdsm/{connectivity.log,mom.log,supervdsm.log,vdsm.log}
chmod 0644 /var/log/vdsm/{connectivity.log,mom.log,supervdsm.log,vdsm.log}
chown vdsm:kvm /var/log/vdsm/{connectivity.log,mom.log,vdsm.log}
chown root:root /var/log/vdsm/supervdsm.log

# Have moved vdsm section in /etc/sysctl.conf to /etc/sysctl.d/vdsm.conf.
# So Remove them if it is played with /etc/sysctl.conf.
if grep -q "# VDSM section begin" /etc/sysctl.conf; then
    /bin/sed -i '/# VDSM section begin/,/# VDSM section end/d' \
        /etc/sysctl.conf
fi

# hack until we replace core dump with abrt
if /usr/sbin/selinuxenabled; then
    /usr/sbin/semanage fcontext -a -t virt_cache_t '/var/log/core(/.*)?'
fi
/sbin/restorecon -R /var/log/core >/dev/null 2>&1
# hack until we replace core dump with abrt

# VDSM installs vdsm-modules-load.d.conf file - the following command will
# refresh vdsm kernel modules requirements to start on boot
/bin/systemctl restart systemd-modules-load.service >/dev/null 2>&1 || :

# The following triggers vdsmd.preset file and enables vdsm required services
%systemd_post vdsmd.service
%systemd_post supervdsmd.service
%systemd_post vdsm-network.service
%systemd_post mom-vdsm.service
%systemd_post ksmtuned.service

# VDSM installs unit files - daemon-reload will refresh systemd
/bin/systemctl daemon-reload >/dev/null 2>&1 || :
exit 0

%preun
if [ "$1" -eq 0 ]; then
        %{_bindir}/vdsm-tool remove-config
fi
%systemd_preun vdsmd.service
%systemd_preun vdsm-network.service
%systemd_preun supervdsmd.service
%systemd_preun mom-vdsm.service
%systemd_preun ksmtuned.service
exit 0

%postun
if [ "$1" -ge 1 ]; then
    supervdsmd_start_required='no'
    vdsmd_start_required='no'

    # Both vdsm and supervdsm should be managed here and must be restarted if
    # ran before (code might changed)
    if %{_bindir}/vdsm-tool service-status vdsmd >/dev/null 2>&1; then
        %{_bindir}/vdsm-tool service-stop vdsmd >/dev/null 2>&1 || :
        vdsmd_start_required='yes'
    fi
    if %{_bindir}/vdsm-tool service-status supervdsmd >/dev/null 2>&1; then
        %{_bindir}/vdsm-tool service-stop supervdsmd >/dev/null 2>&1 || :
        supervdsmd_start_required='yes'
    fi

    if ! %{_bindir}/vdsm-tool is-configured >/dev/null 2>&1; then
        %{_bindir}/vdsm-tool configure --force >/dev/null 2>&1
    fi

    if [ "${supervdsmd_start_required}" = 'yes' ]; then
        %{_bindir}/vdsm-tool service-start supervdsmd >/dev/null 2>&1 || :
    fi
    if [ "${vdsmd_start_required}" = 'yes' ]; then
        %{_bindir}/vdsm-tool service-start vdsmd >/dev/null 2>&1 || :
    fi
fi
exit 0

%files
%defattr(-, root, root, -)
%doc README lib/vdsm/vdsm.conf.sample
%license COPYING
/usr/lib/systemd/systemd-vdsmd
/usr/lib/systemd/system-preset/85-vdsmd.preset
%{_unitdir}/vdsmd.service
%{_unitdir}/vdsm-network.service
%{_unitdir}/supervdsmd.service
%{_unitdir}/mom-vdsm.service
%{_sysconfdir}/systemd/system/libvirtd.service.d/unlimited-core.conf

%dir %attr(-, %{vdsm_user}, %{vdsm_group}) /rhev/data-center
%ghost %config %attr(0644, %{vdsm_user}, %{vdsm_group}) /var/log/vdsm/connectivity.log
%ghost %config %attr(0644, %{vdsm_user}, %{vdsm_group}) /var/log/vdsm/mom.log
%ghost %config %attr(0644, root, root) /var/log/vdsm/supervdsm.log
%ghost %config %attr(0644, %{vdsm_user}, %{vdsm_group}) /var/log/vdsm/vdsm.log
%ghost %dir %attr(-, %{vdsm_user}, %{vdsm_group}) /rhev/data-center/hsm-tasks
%ghost %dir %attr(-, %{vdsm_user}, %{vdsm_group}) /rhev/data-center/mnt
%dir %{_libexecdir}/%{vdsm_name}
%dir %{_sysconfdir}/%{vdsm_name}
%dir %{_sysconfdir}/%{vdsm_name}/mom.d
%dir %{_datadir}/%{vdsm_name}
%dir %{_datadir}/%{vdsm_name}/network
%dir %{_datadir}/%{vdsm_name}/network/configurators
%dir %{_datadir}/%{vdsm_name}/network/tc
%dir %{_datadir}/%{vdsm_name}/storage
%dir %{_datadir}/%{vdsm_name}/storage/imageRepository
%dir %{_datadir}/%{vdsm_name}/virt
%dir %{_datadir}/%{vdsm_name}/virt/vmdevices
%dir %{_datadir}/%{vdsm_name}/rpc
%{_datadir}/%{vdsm_name}/alignmentScan.py*
%{_datadir}/%{vdsm_name}/blkid.py*
%{_datadir}/%{vdsm_name}/caps.py*
%{_datadir}/%{vdsm_name}/clientIF.py*
%{_datadir}/%{vdsm_name}/daemonAdapter
%{_datadir}/%{vdsm_name}/dmidecodeUtil.py*
%{_datadir}/%{vdsm_name}/API.py*
%{_datadir}/%{vdsm_name}/hooking.py*
%{_datadir}/%{vdsm_name}/hooks.py*
%{_datadir}/%{vdsm_name}/hostdev.py*
%{_datadir}/%{vdsm_name}/mk_sysprep_floppy
%{_datadir}/%{vdsm_name}/parted_utils.py*
%{_datadir}/%{vdsm_name}/mkimage.py*
%{_datadir}/%{vdsm_name}/numaUtils.py*
%{_datadir}/%{vdsm_name}/ppc64HardwareInfo.py*
%{_datadir}/%{vdsm_name}/protocoldetector.py*
%{_datadir}/%{vdsm_name}/supervdsm.py*
%{_datadir}/%{vdsm_name}/sitecustomize.py*
%{_datadir}/%{vdsm_name}/supervdsmServer
%{_datadir}/%{vdsm_name}/v2v.py*
%{_datadir}/%{vdsm_name}/vdsm
%{_datadir}/%{vdsm_name}/vdsm-restore-net-config
%{_datadir}/%{vdsm_name}/vdsm-store-net-config
%{_datadir}/%{vdsm_name}/virt/__init__.py*
%{_datadir}/%{vdsm_name}/virt/domain_descriptor.py*
%{_datadir}/%{vdsm_name}/virt/guestagent.py*
%{_datadir}/%{vdsm_name}/virt/migration.py*
%{_datadir}/%{vdsm_name}/virt/periodic.py*
%{_datadir}/%{vdsm_name}/virt/sampling.py*
%{_datadir}/%{vdsm_name}/virt/secret.py*
%{_datadir}/%{vdsm_name}/virt/virdomain.py*
%{_datadir}/%{vdsm_name}/virt/vmchannels.py*
%{_datadir}/%{vdsm_name}/virt/vmstats.py*
%{_datadir}/%{vdsm_name}/virt/vmstatus.py*
%{_datadir}/%{vdsm_name}/virt/vmtune.py*
%{_datadir}/%{vdsm_name}/virt/vm.py*
%{_datadir}/%{vdsm_name}/virt/vmexitreason.py*
%{_datadir}/%{vdsm_name}/virt/vmpowerdown.py*
%{_datadir}/%{vdsm_name}/virt/vmxml.py*
%{_datadir}/%{vdsm_name}/virt/utils.py*
%{_datadir}/%{vdsm_name}/virt/vmdevices/__init__.py*
%{_datadir}/%{vdsm_name}/virt/vmdevices/core.py*
%{_datadir}/%{vdsm_name}/virt/vmdevices/graphics.py*
%{_datadir}/%{vdsm_name}/virt/vmdevices/hostdevice.py*
%{_datadir}/%{vdsm_name}/virt/vmdevices/hwclass.py*
%{_datadir}/%{vdsm_name}/virt/vmdevices/network.py*
%{_datadir}/%{vdsm_name}/virt/vmdevices/storage.py*

%config(noreplace) %{_sysconfdir}/%{vdsm_name}/vdsm.conf
%config(noreplace) %{_sysconfdir}/%{vdsm_name}/logger.conf
%config(noreplace) %{_sysconfdir}/%{vdsm_name}/svdsm.logger.conf
%config(noreplace) %{_sysconfdir}/%{vdsm_name}/mom.conf
%config(noreplace) %{_sysconfdir}/%{vdsm_name}/mom.d/*.policy
%config(noreplace) %{_sysconfdir}/%{vdsm_name}/logrotate/vdsm
%config(noreplace) %{_sysconfdir}/rwtab.d/vdsm
%config(noreplace) %{_sysconfdir}/sysctl.d/vdsm.conf
%config(noreplace) %{_sysconfdir}/modules-load.d/vdsm.conf
%config(noreplace) %{_tmpfilesdir}/%{vdsm_name}.conf
%{_sysconfdir}/dhcp/dhclient.d/sourceRoute.sh
%{_sysconfdir}/sudoers.d/50_vdsm
%{_sysconfdir}/cron.hourly/vdsm-logrotate
%{_sysconfdir}/libvirt/hooks/qemu
%{_datadir}/%{vdsm_name}/logUtils.py*
%{_datadir}/%{vdsm_name}/dsaversion.py*
%{_libexecdir}/%{vdsm_name}/curl-img-wrap
%{_libexecdir}/%{vdsm_name}/fc-scan
%{_libexecdir}/%{vdsm_name}/persist-vdsm-hooks
%{_libexecdir}/%{vdsm_name}/unpersist-vdsm-hook
%{_libexecdir}/%{vdsm_name}/ovirt_functions.sh
%{_libexecdir}/%{vdsm_name}/vdsm-gencerts.sh
%{_libexecdir}/%{vdsm_name}/vdsmd_init_common.sh
%{_datadir}/%{vdsm_name}/network/__init__.py*
%{_datadir}/%{vdsm_name}/network/api.py*
%{_datadir}/%{vdsm_name}/network/configurators/__init__.py*
%{_datadir}/%{vdsm_name}/network/configurators/dhclient.py*
%{_datadir}/%{vdsm_name}/network/configurators/ifcfg.py*
%{_datadir}/%{vdsm_name}/network/configurators/iproute2.py*
%{_datadir}/%{vdsm_name}/network/configurators/libvirt.py*
%{_datadir}/%{vdsm_name}/network/configurators/pyroute_two.py*
%{_datadir}/%{vdsm_name}/network/configurators/qos.py*
%{_datadir}/%{vdsm_name}/network/errors.py*
%{_datadir}/%{vdsm_name}/network/models.py*
%{_datadir}/%{vdsm_name}/network/sourceroute.py*
%{_datadir}/%{vdsm_name}/network/sourceroutethread.py*
%{_datadir}/%{vdsm_name}/network/tc/__init__.py*
%{_datadir}/%{vdsm_name}/network/tc/_parser.py*
%{_datadir}/%{vdsm_name}/network/tc/_wrapper.py*
%{_datadir}/%{vdsm_name}/network/tc/cls.py*
%{_datadir}/%{vdsm_name}/network/tc/filter.py*
%{_datadir}/%{vdsm_name}/network/tc/qdisc.py*
%{_datadir}/%{vdsm_name}/network/utils.py*
%{_datadir}/%{vdsm_name}/storage/__init__.py*
%{_datadir}/%{vdsm_name}/storage/blockSD.py*
%{_datadir}/%{vdsm_name}/storage/blockVolume.py*
%{_datadir}/%{vdsm_name}/storage/curlImgWrap.py*
%{_datadir}/%{vdsm_name}/storage/devicemapper.py*
%{_datadir}/%{vdsm_name}/storage/dispatcher.py*
%{_datadir}/%{vdsm_name}/storage/monitor.py*
%{_datadir}/%{vdsm_name}/storage/fileSD.py*
%{_datadir}/%{vdsm_name}/storage/fileUtils.py*
%{_datadir}/%{vdsm_name}/storage/fileVolume.py*
%{_datadir}/%{vdsm_name}/storage/fuser.py*
%{_datadir}/%{vdsm_name}/storage/glusterSD.py*
%{_datadir}/%{vdsm_name}/storage/glusterVolume.py*
%{_datadir}/%{vdsm_name}/storage/hba.py*
%{_datadir}/%{vdsm_name}/storage/hsm.py*
%{_datadir}/%{vdsm_name}/storage/image.py*
%{_datadir}/%{vdsm_name}/storage/imageSharing.py*
%{_datadir}/%{vdsm_name}/storage/iscsiadm.py*
%{_datadir}/%{vdsm_name}/storage/iscsi.py*
%{_datadir}/%{vdsm_name}/storage/localFsSD.py*
%{_datadir}/%{vdsm_name}/storage/lvm.env
%{_datadir}/%{vdsm_name}/storage/lvm.py*
%{_datadir}/%{vdsm_name}/storage/misc.py*
%{_datadir}/%{vdsm_name}/storage/mount.py*
%{_datadir}/%{vdsm_name}/storage/multipath.py*
%{_datadir}/%{vdsm_name}/storage/nfsSD.py*
%{_datadir}/%{vdsm_name}/storage/outOfProcess.py*
%{_datadir}/%{vdsm_name}/storage/persistentDict.py*
%{_datadir}/%{vdsm_name}/storage/resourceFactories.py*
%{_datadir}/%{vdsm_name}/storage/remoteFileHandler.py*
%{_datadir}/%{vdsm_name}/storage/resourceManager.py*
%{_datadir}/%{vdsm_name}/storage/clusterlock.py*
%{_datadir}/%{vdsm_name}/storage/sdc.py*
%{_datadir}/%{vdsm_name}/storage/sd.py*
%{_datadir}/%{vdsm_name}/storage/securable.py*
%{_datadir}/%{vdsm_name}/storage/sp.py*
%{_datadir}/%{vdsm_name}/storage/spbackends.py*
%{_datadir}/%{vdsm_name}/storage/storageConstants.py*
%{_datadir}/%{vdsm_name}/storage/storage_exception.py*
%{_datadir}/%{vdsm_name}/storage/storage_mailbox.py*
%{_datadir}/%{vdsm_name}/storage/storageServer.py*
%{_datadir}/%{vdsm_name}/storage/sync.py*
%{_datadir}/%{vdsm_name}/storage/taskManager.py*
%{_datadir}/%{vdsm_name}/storage/task.py*
%{_datadir}/%{vdsm_name}/storage/threadLocal.py*
%{_datadir}/%{vdsm_name}/storage/threadPool.py*
%{_datadir}/%{vdsm_name}/storage/volume.py*
%{_datadir}/%{vdsm_name}/storage/imageRepository/__init__.py*
%{_datadir}/%{vdsm_name}/storage/imageRepository/formatConverter.py*
%{_libexecdir}/%{vdsm_name}/spmprotect.sh
%{_libexecdir}/%{vdsm_name}/spmstop.sh
%dir %{_libexecdir}/%{vdsm_name}/hooks
%dir %{_libexecdir}/%{vdsm_name}/hooks/before_device_create
%dir %{_libexecdir}/%{vdsm_name}/hooks/after_device_create
%dir %{_libexecdir}/%{vdsm_name}/hooks/before_device_destroy
%dir %{_libexecdir}/%{vdsm_name}/hooks/after_device_destroy
%dir %{_libexecdir}/%{vdsm_name}/hooks/before_vm_start
%dir %{_libexecdir}/%{vdsm_name}/hooks/after_vm_start
%dir %{_libexecdir}/%{vdsm_name}/hooks/before_vm_cont
%dir %{_libexecdir}/%{vdsm_name}/hooks/after_vm_cont
%dir %{_libexecdir}/%{vdsm_name}/hooks/before_vm_pause
%dir %{_libexecdir}/%{vdsm_name}/hooks/after_vm_pause
%dir %{_libexecdir}/%{vdsm_name}/hooks/before_vm_hibernate
%dir %{_libexecdir}/%{vdsm_name}/hooks/after_vm_hibernate
%dir %{_libexecdir}/%{vdsm_name}/hooks/before_vm_dehibernate
%dir %{_libexecdir}/%{vdsm_name}/hooks/after_vm_dehibernate
%dir %{_libexecdir}/%{vdsm_name}/hooks/before_device_migrate_source
%dir %{_libexecdir}/%{vdsm_name}/hooks/after_device_migrate_source
%dir %{_libexecdir}/%{vdsm_name}/hooks/before_device_migrate_destination
%dir %{_libexecdir}/%{vdsm_name}/hooks/after_device_migrate_destination
%dir %{_libexecdir}/%{vdsm_name}/hooks/before_vm_migrate_source
%dir %{_libexecdir}/%{vdsm_name}/hooks/after_vm_migrate_source
%dir %{_libexecdir}/%{vdsm_name}/hooks/before_vm_migrate_destination
%dir %{_libexecdir}/%{vdsm_name}/hooks/after_vm_migrate_destination
%dir %{_libexecdir}/%{vdsm_name}/hooks/before_vm_destroy
%dir %{_libexecdir}/%{vdsm_name}/hooks/after_vm_destroy
%dir %{_libexecdir}/%{vdsm_name}/hooks/before_vm_set_ticket
%dir %{_libexecdir}/%{vdsm_name}/hooks/after_vm_set_ticket
%dir %{_libexecdir}/%{vdsm_name}/hooks/before_update_device
%dir %{_libexecdir}/%{vdsm_name}/hooks/after_update_device
%dir %{_libexecdir}/%{vdsm_name}/hooks/after_update_device_fail
%dir %{_libexecdir}/%{vdsm_name}/hooks/before_nic_hotplug
%dir %{_libexecdir}/%{vdsm_name}/hooks/after_nic_hotplug
%dir %{_libexecdir}/%{vdsm_name}/hooks/before_nic_hotunplug
%dir %{_libexecdir}/%{vdsm_name}/hooks/after_nic_hotunplug
%dir %{_libexecdir}/%{vdsm_name}/hooks/after_nic_hotplug_fail
%dir %{_libexecdir}/%{vdsm_name}/hooks/after_nic_hotunplug_fail
%dir %{_libexecdir}/%{vdsm_name}/hooks/before_disk_hotplug
%dir %{_libexecdir}/%{vdsm_name}/hooks/after_disk_hotplug
%dir %{_libexecdir}/%{vdsm_name}/hooks/before_disk_hotunplug
%dir %{_libexecdir}/%{vdsm_name}/hooks/after_disk_hotunplug
%dir %{_libexecdir}/%{vdsm_name}/hooks/before_vdsm_start
%dir %{_libexecdir}/%{vdsm_name}/hooks/after_vdsm_stop
%dir %{_libexecdir}/%{vdsm_name}/hooks/before_network_setup
%dir %{_libexecdir}/%{vdsm_name}/hooks/after_network_setup
%dir %{_libexecdir}/%{vdsm_name}/hooks/after_network_setup_fail
%dir %{_libexecdir}/%{vdsm_name}/hooks/before_set_num_of_cpus
%dir %{_libexecdir}/%{vdsm_name}/hooks/after_set_num_of_cpus
%dir %{_libexecdir}/%{vdsm_name}/hooks/before_memory_hotplug
%dir %{_libexecdir}/%{vdsm_name}/hooks/after_memory_hotplug
%dir %{_libexecdir}/%{vdsm_name}/hooks/before_get_vm_stats
%dir %{_libexecdir}/%{vdsm_name}/hooks/after_get_vm_stats
%dir %{_libexecdir}/%{vdsm_name}/hooks/before_get_all_vm_stats
%dir %{_libexecdir}/%{vdsm_name}/hooks/after_get_all_vm_stats
%dir %{_libexecdir}/%{vdsm_name}/hooks/before_get_caps
%dir %{_libexecdir}/%{vdsm_name}/hooks/after_get_caps
%dir %{_libexecdir}/%{vdsm_name}/hooks/before_get_stats
%dir %{_libexecdir}/%{vdsm_name}/hooks/after_get_stats
%dir %{_libexecdir}/%{vdsm_name}/hooks/after_hostdev_list_by_caps
%dir %{_libexecdir}/%{vdsm_name}/hooks/before_ifcfg_write
%dir %{_libexecdir}/%{vdsm_name}/hooks/after_ifcfg_write

%{_datadir}/%{vdsm_name}/dumpStorageTable.py*
%{_datadir}/%{vdsm_name}/get-conf-item
%{_datadir}/%{vdsm_name}/kaxmlrpclib.py*
%{_datadir}/%{vdsm_name}/momIF.py*
%{_datadir}/%{vdsm_name}/set-conf-item
%dir %{_datadir}/%{vdsm_name}/gluster
%{_datadir}/%{vdsm_name}/gluster/__init__.py*
%{_datadir}/%{vdsm_name}/gluster/cli.py*
%{_datadir}/%{vdsm_name}/gluster/exception.py*
%{python_sitelib}/sos/plugins/vdsm.py*
%{_udevrulesdir}/12-vdsm-lvm.rules
/etc/security/limits.d/99-vdsm.conf
%{_mandir}/man8/vdsmd.8*
%if 0%{?rhel}
%dir %{_localstatedir}/log/core
%endif
%{_polkitdir}/10-vdsm-libvirt-access.rules

%defattr(-, %{vdsm_user}, %{qemu_group}, -)
%dir %{_localstatedir}/lib/libvirt/qemu/channels

%defattr(-, %{vdsm_user}, %{vdsm_group}, -)
%dir %{_sysconfdir}/pki/%{vdsm_name}
%dir %{_sysconfdir}/pki/%{vdsm_name}/keys
%dir %{_sysconfdir}/pki/%{vdsm_name}/certs
%dir %{_sysconfdir}/pki/%{vdsm_name}/libvirt-spice
%config(noreplace) %{_sysconfdir}/pki/%{vdsm_name}/keys/libvirt_password
%dir %{_localstatedir}/lib/%{vdsm_name}
%dir %{_localstatedir}/lib/%{vdsm_name}/netconfback
%dir %{_localstatedir}/lib/%{vdsm_name}/persistence
%dir %{_localstatedir}/lib/%{vdsm_name}/upgrade
%dir %{_localstatedir}/run/%{vdsm_name}
%dir %{_localstatedir}/run/%{vdsm_name}/sourceRoutes
%dir %{_localstatedir}/run/%{vdsm_name}/trackedInterfaces
%ghost %dir %{_localstatedir}/run/%{vdsm_name}/payload
%dir %{_localstatedir}/run/%{vdsm_name}/v2v
%dir %{_localstatedir}/log/%{vdsm_name}
%dir %{_localstatedir}/log/%{vdsm_name}/backup
%defattr(644, %{vdsm_user}, %{vdsm_group}, -)
%{_localstatedir}/lib/%{vdsm_name}/bonding-defaults.json

%files python
%defattr(-, root, root, -)
%{_mandir}/man1/vdsm-tool.1*
%{_bindir}/vdsm-tool
%dir %{python_sitelib}/%{vdsm_name}
%dir %{python_sitelib}/%{vdsm_name}/netlink
%dir %{python_sitelib}/%{vdsm_name}/tool
%dir %{python_sitelib}/%{vdsm_name}/tool/configurators
%dir %{python_sitelib}/%{vdsm_name}/profiling
%{python_sitelib}/%{vdsm_name}/__init__.py*
%{python_sitelib}/%{vdsm_name}/cmdutils.py*
%{python_sitelib}/%{vdsm_name}/compat.py*
%{python_sitelib}/%{vdsm_name}/concurrent.py*
%{python_sitelib}/%{vdsm_name}/config.py*
%{python_sitelib}/%{vdsm_name}/constants.py*
%{python_sitelib}/%{vdsm_name}/define.py*
%{python_sitelib}/%{vdsm_name}/exception.py*
%{python_sitelib}/%{vdsm_name}/executor.py*
%{python_sitelib}/%{vdsm_name}/health.py*
%{python_sitelib}/%{vdsm_name}/ipwrapper.py*
%{python_sitelib}/%{vdsm_name}/jsonrpcvdscli.py*
%{python_sitelib}/%{vdsm_name}/libvirtconnection.py*
%{python_sitelib}/%{vdsm_name}/m2cutils.py*
%{python_sitelib}/%{vdsm_name}/netinfo.py*
%{python_sitelib}/%{vdsm_name}/netlink/__init__.py*
%{python_sitelib}/%{vdsm_name}/netlink/addr.py*
%{python_sitelib}/%{vdsm_name}/netlink/link.py*
%{python_sitelib}/%{vdsm_name}/netlink/monitor.py*
%{python_sitelib}/%{vdsm_name}/netlink/route.py*
%{python_sitelib}/%{vdsm_name}/password.py*
%{python_sitelib}/%{vdsm_name}/profiling/__init__.py*
%{python_sitelib}/%{vdsm_name}/profiling/cpu.py*
%{python_sitelib}/%{vdsm_name}/profiling/errors.py*
%{python_sitelib}/%{vdsm_name}/profiling/memory.py*
%{python_sitelib}/%{vdsm_name}/profiling/profile.py*
%{python_sitelib}/%{vdsm_name}/pthread.py*
%{python_sitelib}/%{vdsm_name}/qemuimg.py*
%{python_sitelib}/%{vdsm_name}/response.py*
%{python_sitelib}/%{vdsm_name}/netconfpersistence.py*
%{python_sitelib}/%{vdsm_name}/schedule.py*
%{python_sitelib}/%{vdsm_name}/sslcompat.py*
%{python_sitelib}/%{vdsm_name}/sslutils.py*
%{python_sitelib}/%{vdsm_name}/sysctl.py*
%{python_sitelib}/%{vdsm_name}/taskset.py*
%{python_sitelib}/%{vdsm_name}/udevadm.py*
%{python_sitelib}/%{vdsm_name}/utils.py*
%{python_sitelib}/%{vdsm_name}/vdscli.py*
%{python_sitelib}/%{vdsm_name}/virtsparsify.py*
%{python_sitelib}/%{vdsm_name}/xmlrpc.py*
%{python_sitelib}/%{vdsm_name}/tool/__init__.py*
%{python_sitelib}/%{vdsm_name}/tool/configfile.py*
%{python_sitelib}/%{vdsm_name}/tool/dummybr.py*
%{python_sitelib}/%{vdsm_name}/tool/dump_bonding_defaults.py*
%{python_sitelib}/%{vdsm_name}/tool/nwfilter.py*
%{python_sitelib}/%{vdsm_name}/tool/configurator.py*
%{python_sitelib}/%{vdsm_name}/tool/configurators/__init__*
%{python_sitelib}/%{vdsm_name}/tool/configurators/certificates.py*
%{python_sitelib}/%{vdsm_name}/tool/configurators/libvirt.py*
%{python_sitelib}/%{vdsm_name}/tool/configurators/passwd.py*
%{python_sitelib}/%{vdsm_name}/tool/configurators/sanlock.py*
%{python_sitelib}/%{vdsm_name}/tool/configurators/sebool.py*
%{python_sitelib}/%{vdsm_name}/tool/configurators/multipath.py*
%{python_sitelib}/%{vdsm_name}/tool/dump_volume_chains.py*
%{python_sitelib}/%{vdsm_name}/tool/register.py*
%{python_sitelib}/%{vdsm_name}/tool/restore_nets.py*
%{python_sitelib}/%{vdsm_name}/tool/service.py*
%{python_sitelib}/%{vdsm_name}/tool/transient.py*
%{python_sitelib}/%{vdsm_name}/tool/unified_persistence.py*
%{python_sitelib}/%{vdsm_name}/tool/upgrade.py*
%{python_sitelib}/%{vdsm_name}/tool/validate_ovirt_certs.py*
%{python_sitelib}/%{vdsm_name}/tool/vdsm-id.py*

%files tests
%doc %{_datadir}/%{vdsm_name}/tests/README
%defattr(-, root, root, -)
%dir %{_datadir}/%{vdsm_name}
%dir %{_datadir}/%{vdsm_name}/tests
%dir %{_datadir}/%{vdsm_name}/tests/functional
%dir %{_datadir}/%{vdsm_name}/tests/devices
%dir %{_datadir}/%{vdsm_name}/tests/devices/data
%dir %{_datadir}/%{vdsm_name}/tests/devices/parsing
%dir %{_datadir}/%{vdsm_name}/tests/integration
%{_datadir}/%{vdsm_name}/tests/*.py*
%{_datadir}/%{vdsm_name}/tests/cpu_info.out
%{_datadir}/%{vdsm_name}/tests/caps_libvirt_intel_E5649.out
%{_datadir}/%{vdsm_name}/tests/caps_libvirt_amd_6274.out
%{_datadir}/%{vdsm_name}/tests/caps_libvirt_ibm_S822L.out
%{_datadir}/%{vdsm_name}/tests/caps_libvirt_intel_E31220.out
%{_datadir}/%{vdsm_name}/tests/caps_libvirt_intel_E5606.out
%{_datadir}/%{vdsm_name}/tests/caps_libvirt_intel_i73770.out
%{_datadir}/%{vdsm_name}/tests/caps_libvirt_intel_i73770_nosnap.out
%{_datadir}/%{vdsm_name}/tests/caps_libvirt_multiqemu.out
%{_datadir}/%{vdsm_name}/tests/caps_numactl_4_nodes.out
%{_datadir}/%{vdsm_name}/tests/cpu_map.xml
%{_datadir}/%{vdsm_name}/tests/devices/*.py*
%{_datadir}/%{vdsm_name}/tests/devices/parsing/*.py*
%{_datadir}/%{vdsm_name}/tests/devices/data/*.xml
%{_datadir}/%{vdsm_name}/tests/ip_route_show_table_all.out
%{_datadir}/%{vdsm_name}/tests/iscsiadm_-m_iface.out
%{_datadir}/%{vdsm_name}/tests/lvs_3386c6f2-926f-42c4-839c-38287fac8998.out
%{_datadir}/%{vdsm_name}/tests/mem_info.out
%{_datadir}/%{vdsm_name}/tests/netmaskconversions
%{_datadir}/%{vdsm_name}/tests/run_tests.sh
%{_datadir}/%{vdsm_name}/tests/tc_filter_show.out
%{_datadir}/%{vdsm_name}/tests/toolTests_empty.conf
%{_datadir}/%{vdsm_name}/tests/toolTests_lconf_ssl.conf
%{_datadir}/%{vdsm_name}/tests/toolTests_libvirtd.conf
%{_datadir}/%{vdsm_name}/tests/toolTests_qemu_sanlock.conf
%{_datadir}/%{vdsm_name}/tests/toolTests_qemu_ssl.conf
%{_datadir}/%{vdsm_name}/tests/toolTests_vdsm_no_ssl.conf
%{_datadir}/%{vdsm_name}/tests/toolTests_vdsm_ssl.conf
%{_datadir}/%{vdsm_name}/tests/glusterGeoRepStatus.xml
%{_datadir}/%{vdsm_name}/tests/glusterVolumeGeoRepConfigList.xml
%{_datadir}/%{vdsm_name}/tests/glusterSnapshotList.xml
%{_datadir}/%{vdsm_name}/tests/glusterSnapshotListEmpty.xml
%{_datadir}/%{vdsm_name}/tests/glusterVolumeProfileInfo.xml
%{_datadir}/%{vdsm_name}/tests/glusterSnapshotConfig.xml
%{_datadir}/%{vdsm_name}/tests/glusterVolumeProfileInfoNfs.xml
%{_datadir}/%{vdsm_name}/tests/glusterVolumeRebalanceStatus.xml
%{_datadir}/%{vdsm_name}/tests/glusterVolumeRemoveBricksStatus.xml
%{_datadir}/%{vdsm_name}/tests/glusterSnapshotRestore.xml
%{_datadir}/%{vdsm_name}/tests/glusterVolumeSnapshotList.xml
%{_datadir}/%{vdsm_name}/tests/glusterVolumeSnapshotListEmpty.xml
%{_datadir}/%{vdsm_name}/tests/glusterVolumeTasks.xml
%{_datadir}/%{vdsm_name}/tests/functional/*.py*
%{_datadir}/%{vdsm_name}/tests/functional/*.policy
%{_datadir}/%{vdsm_name}/tests/integration/*.py*

%files hook-openstacknet
%defattr(-, root, root, -)
%{_sysconfdir}/sudoers.d/50_vdsm_hook_openstacknet
%{_libexecdir}/%{vdsm_name}/hooks/after_device_create/50_openstacknet
%{_libexecdir}/%{vdsm_name}/hooks/after_device_create/openstacknet_utils.py*
%{_libexecdir}/%{vdsm_name}/hooks/after_device_destroy/50_openstacknet
%{_libexecdir}/%{vdsm_name}/hooks/after_device_destroy/openstacknet_utils.py*
%{_libexecdir}/%{vdsm_name}/hooks/after_device_migrate_destination/50_openstacknet
%{_libexecdir}/%{vdsm_name}/hooks/after_device_migrate_destination/openstacknet_utils.py*
%{_libexecdir}/%{vdsm_name}/hooks/after_nic_hotplug/50_openstacknet
%{_libexecdir}/%{vdsm_name}/hooks/after_nic_hotplug/openstacknet_utils.py*
%{_libexecdir}/%{vdsm_name}/hooks/after_nic_hotunplug/50_openstacknet
%{_libexecdir}/%{vdsm_name}/hooks/after_nic_hotunplug/openstacknet_utils.py*
%{_libexecdir}/%{vdsm_name}/hooks/before_device_create/50_openstacknet
%{_libexecdir}/%{vdsm_name}/hooks/before_device_create/openstacknet_utils.py*
%{_libexecdir}/%{vdsm_name}/hooks/before_device_migrate_destination/50_openstacknet
%{_libexecdir}/%{vdsm_name}/hooks/before_device_migrate_destination/openstacknet_utils.py*
%{_libexecdir}/%{vdsm_name}/hooks/before_nic_hotplug/50_openstacknet
%{_libexecdir}/%{vdsm_name}/hooks/before_nic_hotplug/openstacknet_utils.py*

%files hook-ovs
%defattr(-, root, root, -)
%{_sysconfdir}/sudoers.d/50_vdsm_hook_ovs
%{_libexecdir}/%{vdsm_name}/hooks/after_get_caps/50_ovs
%{_libexecdir}/%{vdsm_name}/hooks/after_get_caps/ovs_utils.py*
%{_libexecdir}/%{vdsm_name}/hooks/after_get_stats/50_ovs
%{_libexecdir}/%{vdsm_name}/hooks/after_get_stats/ovs_utils.py*
%{_libexecdir}/%{vdsm_name}/hooks/before_device_create/50_ovs
%{_libexecdir}/%{vdsm_name}/hooks/before_device_create/ovs_utils.py*
%{_libexecdir}/%{vdsm_name}/hooks/before_network_setup/50_ovs
%{_libexecdir}/%{vdsm_name}/hooks/before_network_setup/ovs_setup_ip.py*
%{_libexecdir}/%{vdsm_name}/hooks/before_network_setup/ovs_setup_libvirt.py*
%{_libexecdir}/%{vdsm_name}/hooks/before_network_setup/ovs_setup_mtu.py*
%{_libexecdir}/%{vdsm_name}/hooks/before_network_setup/ovs_setup_ovs.py*
%{_libexecdir}/%{vdsm_name}/hooks/before_network_setup/ovs_utils.py*
%{_libexecdir}/%{vdsm_name}/hooks/after_network_setup/50_ovs
%{_libexecdir}/%{vdsm_name}/hooks/after_network_setup/ovs_utils.py*
%{_libexecdir}/%{vdsm_name}/hooks/after_network_setup_fail/50_ovs
%{_libexecdir}/%{vdsm_name}/hooks/after_network_setup_fail/ovs_utils.py*

%files hook-macspoof
%defattr(-, root, root, -)
%{_libexecdir}/%{vdsm_name}/hooks/before_vm_start/50_macspoof
%{_libexecdir}/%{vdsm_name}/hooks/before_device_create/50_macspoof
%{_libexecdir}/%{vdsm_name}/hooks/before_nic_hotplug/50_macspoof

%if 0%{?with_vhostmd}
%files hook-vhostmd
%defattr(-, root, root, -)
%license COPYING
%{_sysconfdir}/sudoers.d/50_vdsm_hook_vhostmd
%{_libexecdir}/%{vdsm_name}/hooks/before_vm_start/50_vhostmd
%{_libexecdir}/%{vdsm_name}/hooks/before_vm_migrate_destination/50_vhostmd
%{_libexecdir}/%{vdsm_name}/hooks/before_vm_dehibernate/50_vhostmd
%{_libexecdir}/%{vdsm_name}/hooks/after_vm_destroy/50_vhostmd
%else
%exclude %{_sysconfdir}/sudoers.d/50_vdsm_hook_vhostmd
%exclude %{_libexecdir}/%{vdsm_name}/hooks/before_vm_start/50_vhostmd
%exclude %{_libexecdir}/%{vdsm_name}/hooks/before_vm_migrate_destination/50_vhostmd
%exclude %{_libexecdir}/%{vdsm_name}/hooks/before_vm_dehibernate/50_vhostmd
%exclude %{_libexecdir}/%{vdsm_name}/hooks/after_vm_destroy/50_vhostmd
%endif

%files hook-qemucmdline
%defattr(-, root, root, -)
%license COPYING
%{_libexecdir}/%{vdsm_name}/hooks/before_vm_start/50_qemucmdline

%files hook-ethtool-options
%defattr(-, root, root, -)
%{_libexecdir}/%{vdsm_name}/hooks/after_network_setup/30_ethtool_options

%files hook-ipv6
%defattr(-, root, root, -)
%{_libexecdir}/%{vdsm_name}/hooks/before_network_setup/50_ipv6

%files hook-vmfex-dev
%defattr(-, root, root, -)
%{_libexecdir}/%{vdsm_name}/hooks/before_device_create/50_vmfex
%{_libexecdir}/%{vdsm_name}/hooks/before_device_migrate_destination/50_vmfex
%{_libexecdir}/%{vdsm_name}/hooks/before_nic_hotplug/50_vmfex

%if 0%{?with_hooks}
%files hook-allocate_net
%defattr(-, root, root, -)
%{_libexecdir}/%{vdsm_name}/hooks/before_device_create/10_allocate_net

%files hook-checkimages
%defattr(-, root, root, -)
%{_libexecdir}/%{vdsm_name}/hooks/before_vm_start/60_checkimages

%files hook-diskunmap
%defattr(-, root, root, -)
%{_libexecdir}/%{vdsm_name}/hooks/before_vm_start/50_diskunmap

%files hook-fakevmstats
%defattr(-, root, root, -)
%{_libexecdir}/%{vdsm_name}/hooks/after_get_all_vm_stats/10_fakevmstats

%files hook-fileinject
%defattr(-, root, root, -)
%{_libexecdir}/%{vdsm_name}/hooks/before_vm_start/50_fileinject

%files hook-floppy
%defattr(-, root, root, -)
%{_libexecdir}/%{vdsm_name}/hooks/before_vm_start/50_floppy
%{_libexecdir}/%{vdsm_name}/hooks/before_vm_migrate_source/50_floppy

%files hook-hostusb
%defattr(-, root, root, -)
%{_sysconfdir}/sudoers.d/50_vdsm_hook_hostusb
%{_libexecdir}/%{vdsm_name}/hooks/before_vm_start/50_hostusb
%{_libexecdir}/%{vdsm_name}/hooks/before_vm_migrate_source/50_hostusb
%{_libexecdir}/%{vdsm_name}/hooks/after_vm_destroy/50_hostusb

%files hook-httpsisoboot
%defattr(-, root, root, -)
%{_libexecdir}/%{vdsm_name}/hooks/before_vm_start/50_httpsisoboot

%files hook-hugepages
%defattr(-, root, root, -)
%{_sysconfdir}/sudoers.d/50_vdsm_hook_hugepages
%{_libexecdir}/%{vdsm_name}/hooks/before_vm_start/50_hugepages
%{_libexecdir}/%{vdsm_name}/hooks/before_vm_migrate_destination/50_hugepages
%{_libexecdir}/%{vdsm_name}/hooks/after_vm_destroy/50_hugepages

%files hook-isolatedprivatevlan
%defattr(-, root, root, -)
%{_libexecdir}/%{vdsm_name}/hooks/before_vm_start/50_isolatedprivatevlan
%config(noreplace) %{_sysconfdir}/libvirt/nwfilter/isolatedprivatevlan-vdsm.xml

%files hook-macbind
%defattr(-, root, root, -)
%{_libexecdir}/%{vdsm_name}/hooks/before_vm_start/50_macbind

%files hook-noipspoof
%defattr(-, root, root, -)
%{_libexecdir}/%{vdsm_name}/hooks/before_device_create/50_noipspoof
%{_libexecdir}/%{vdsm_name}/hooks/before_nic_hotplug/50_noipspoof

%files hook-extnet
%defattr(-, root, root, -)
%{_libexecdir}/%{vdsm_name}/hooks/before_device_create/50_extnet
%{_libexecdir}/%{vdsm_name}/hooks/before_nic_hotplug/50_extnet

%files hook-nestedvt
%defattr(-, root, root, -)
%{_sysconfdir}/modprobe.d/vdsm-nestedvt.conf
%{_libexecdir}/%{vdsm_name}/hooks/before_vm_start/50_nestedvt

%files hook-numa
%defattr(-, root, root, -)
%{_libexecdir}/%{vdsm_name}/hooks/before_vm_start/50_numa

%files hook-pincpu
%defattr(-, root, root, -)
%{_libexecdir}/%{vdsm_name}/hooks/before_vm_start/50_pincpu

%files hook-promisc
%defattr(-, root, root, -)
%{_sysconfdir}/sudoers.d/50_vdsm_hook_promisc
%{_libexecdir}/%{vdsm_name}/hooks/after_vm_start/50_promisc
%{_libexecdir}/%{vdsm_name}/hooks/before_vm_destroy/50_promisc

%files hook-qos
%defattr(-, root, root, -)
%{_libexecdir}/%{vdsm_name}/hooks/before_vm_start/50_qos

%files hook-scratchpad
%defattr(-, root, root, -)
%{_libexecdir}/%{vdsm_name}/hooks/before_vm_start/50_scratchpad
%{_libexecdir}/%{vdsm_name}/hooks/before_vm_migrate_source/50_scratchpad
%{_libexecdir}/%{vdsm_name}/hooks/after_vm_destroy/50_scratchpad

%files hook-smbios
%defattr(-, root, root, -)
%{_libexecdir}/%{vdsm_name}/hooks/before_vm_start/50_smbios

%files hook-spiceoptions
%defattr(-, root, root, -)
%{_libexecdir}/%{vdsm_name}/hooks/before_vm_start/50_spiceoptions

%files hook-vmdisk
%defattr(-, root, root, -)
%{_libexecdir}/%{vdsm_name}/hooks/before_vm_start/50_vmdisk

%files hook-vmfex
%defattr(-, root, root, -)
%{_libexecdir}/%{vdsm_name}/hooks/before_vm_migrate_destination/50_vmfex
%{_libexecdir}/%{vdsm_name}/hooks/before_vm_start/50_vmfex
%endif

%files debug-plugin
%defattr(-, root, root, -)
%{_datadir}/%{vdsm_name}/vdsmDebugPlugin.py*
%{_datadir}/%{vdsm_name}/debugPluginClient.py*

%files cli
%defattr(-, root, root, -)
%license COPYING
%{_bindir}/vdsClient
%dir %{_datadir}/%{vdsm_name}
%{_datadir}/%{vdsm_name}/vdsClient.py*
%{_datadir}/%{vdsm_name}/vdsClientGluster.py*
%{_sysconfdir}/bash_completion.d/vdsClient
%{_mandir}/man1/vdsClient.1*

%files xmlrpc
%defattr(-, root, root, -)
%dir %{_datadir}/%{vdsm_name}
%dir %{_datadir}/%{vdsm_name}/rpc
%{_datadir}/%{vdsm_name}/rpc/bindingxmlrpc.py*

%files jsonrpc
%doc %{vdsm_name}/rpc/vdsm-api.html
%dir %{_datadir}/%{vdsm_name}
%dir %{_datadir}/%{vdsm_name}/rpc
%{_datadir}/%{vdsm_name}/rpc/__init__.py*
%{_datadir}/%{vdsm_name}/rpc/bindingjsonrpc.py*
%{_datadir}/%{vdsm_name}/rpc/Bridge.py*
%{_datadir}/%{vdsm_name}/rpc/vdsmapi-schema.json
%{python_sitelib}/vdsmapi.py*
%{python_sitelib}/yajsonrpc/__init__.py*
%if ! 0%{?with_gluster}
%exclude %{_datadir}/%{vdsm_name}/rpc/vdsmapi-gluster-schema.json
%endif

%files yajsonrpc
%dir %{python_sitelib}/yajsonrpc
%{python_sitelib}/yajsonrpc/betterAsyncore.py*
%{python_sitelib}/yajsonrpc/stomp.py*
%{python_sitelib}/yajsonrpc/stompreactor.py*

%files infra
%dir %{python_sitelib}/%{vdsm_name}
%dir %{python_sitelib}/%{vdsm_name}/infra
%dir %{python_sitelib}/%{vdsm_name}/infra/eventfd
%dir %{python_sitelib}/%{vdsm_name}/infra/filecontrol
%dir %{python_sitelib}/%{vdsm_name}/infra/sigutils
%dir %{python_sitelib}/%{vdsm_name}/infra/zombiereaper
%{python_sitelib}/%{vdsm_name}/infra/eventfd/__init__.py*
%{python_sitelib}/%{vdsm_name}/infra/filecontrol/__init__.py*
%{python_sitelib}/%{vdsm_name}/infra/sigutils/__init__.py*
%{python_sitelib}/%{vdsm_name}/infra/zombiereaper/__init__.py*
%{python_sitelib}/%{vdsm_name}/infra/__init__.py*

%files hook-faqemu
%defattr(-, root, root, -)
%license COPYING
%{_libexecdir}/%{vdsm_name}/hooks/before_vm_start/10_faqemu

%if 0%{?with_gluster}
%files gluster
%defattr(-, root, root, -)
%dir %{_datadir}/%{vdsm_name}
%dir %{_datadir}/%{vdsm_name}/gluster
%license COPYING
%{_datadir}/%{vdsm_name}/gluster/api.py*
%{_datadir}/%{vdsm_name}/gluster/apiwrapper.py*
%{_datadir}/%{vdsm_name}/gluster/fstab.py*
%{_datadir}/%{vdsm_name}/rpc/vdsmapi-gluster-schema.json
%{_datadir}/%{vdsm_name}/gluster/gfapi.py*
%{_datadir}/%{vdsm_name}/gluster/hooks.py*
%{_datadir}/%{vdsm_name}/gluster/services.py*
%{_datadir}/%{vdsm_name}/gluster/storagedev.py*
%{_datadir}/%{vdsm_name}/gluster/tasks.py*
%endif

%changelog
* Sun Oct 13 2013 Yaniv Bronhaim <ybronhei@redhat.com> - 4.13.0
- Removing vdsm-python-cpopen from the spec
- Adding dependency on formal cpopen package

* Sun Apr 07 2013 Yaniv Bronhaim <ybronhei@redhat.com> - 4.9.0-1
- Adding cpopen package

* Wed Oct 12 2011 Federico Simoncelli <fsimonce@redhat.com> - 4.9.0-0
- Initial upstream release

* Thu Nov 02 2006 Simon Grinberg <simong@qumranet.com> -  0.0-1
- Initial build
