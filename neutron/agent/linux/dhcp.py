# Copyright 2012 OpenStack Foundation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import abc
import collections
import os
import re
import shutil
import socket
import sys

import netaddr
from oslo.serialization import jsonutils
from oslo.utils import importutils
import six

from neutron.agent.linux import ip_lib
from neutron.agent.linux import utils
from neutron.common import constants
from neutron.common import exceptions
from neutron.common import utils as commonutils
from neutron.i18n import _LE
from neutron.openstack.common import log as logging
from neutron.openstack.common import uuidutils

LOG = logging.getLogger(__name__)

IPV4 = 4
IPV6 = 6
UDP = 'udp'
TCP = 'tcp'
DNS_PORT = 53
DHCPV4_PORT = 67
DHCPV6_PORT = 547
METADATA_DEFAULT_PREFIX = 16
METADATA_DEFAULT_IP = '169.254.169.254'
METADATA_DEFAULT_CIDR = '%s/%d' % (METADATA_DEFAULT_IP,
                                   METADATA_DEFAULT_PREFIX)
METADATA_PORT = 80
WIN2k3_STATIC_DNS = 249
NS_PREFIX = 'qdhcp-'
DNSMASQ_SERVICE_NAME = 'dnsmasq'


class DictModel(dict):
    """Convert dict into an object that provides attribute access to values."""

    def __init__(self, *args, **kwargs):
        """Convert dict values to DictModel values."""
        super(DictModel, self).__init__(*args, **kwargs)

        def needs_upgrade(item):
            """Check if `item` is a dict and needs to be changed to DictModel.
            """
            return isinstance(item, dict) and not isinstance(item, DictModel)

        def upgrade(item):
            """Upgrade item if it needs to be upgraded."""
            if needs_upgrade(item):
                return DictModel(item)
            else:
                return item

        for key, value in self.iteritems():
            if isinstance(value, (list, tuple)):
                # Keep the same type but convert dicts to DictModels
                self[key] = type(value)(
                    (upgrade(item) for item in value)
                )
            elif needs_upgrade(value):
                # Change dict instance values to DictModel instance values
                self[key] = DictModel(value)

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as e:
            raise AttributeError(e)

    def __setattr__(self, name, value):
        self[name] = value

    def __delattr__(self, name):
        del self[name]


class NetModel(DictModel):

    def __init__(self, use_namespaces, d):
        super(NetModel, self).__init__(d)

        self._ns_name = (use_namespaces and
                         "%s%s" % (NS_PREFIX, self.id) or None)

    @property
    def namespace(self):
        return self._ns_name


@six.add_metaclass(abc.ABCMeta)
class DhcpBase(object):

    def __init__(self, conf, network, process_monitor, root_helper='sudo',
                 version=None, plugin=None):
        self.conf = conf
        self.network = network
        self.root_helper = root_helper
        self.process_monitor = process_monitor
        self.device_manager = DeviceManager(self.conf,
                                            self.root_helper, plugin)
        self.version = version

    @abc.abstractmethod
    def enable(self):
        """Enables DHCP for this network."""

    @abc.abstractmethod
    def disable(self, retain_port=False):
        """Disable dhcp for this network."""

    def restart(self):
        """Restart the dhcp service for the network."""
        self.disable(retain_port=True)
        self.enable()

    @abc.abstractproperty
    def active(self):
        """Boolean representing the running state of the DHCP server."""

    @abc.abstractmethod
    def reload_allocations(self):
        """Force the DHCP server to reload the assignment database."""

    @classmethod
    def existing_dhcp_networks(cls, conf, root_helper):
        """Return a list of existing networks ids that we have configs for."""

        raise NotImplementedError()

    @classmethod
    def check_version(cls):
        """Execute version checks on DHCP server."""

        raise NotImplementedError()

    @classmethod
    def get_isolated_subnets(cls, network):
        """Returns a dict indicating whether or not a subnet is isolated"""
        raise NotImplementedError()

    @classmethod
    def should_enable_metadata(cls, conf, network):
        """True if the metadata-proxy should be enabled for the network."""
        raise NotImplementedError()


class DhcpLocalProcess(DhcpBase):
    PORTS = []

    def __init__(self, conf, network, process_monitor, root_helper='sudo',
                 version=None, plugin=None):
        super(DhcpLocalProcess, self).__init__(conf, network, process_monitor,
                                               root_helper, version, plugin)
        self.confs_dir = self.get_confs_dir(conf)
        self.network_conf_dir = os.path.join(self.confs_dir, network.id)
        self._ensure_network_conf_dir()

    @staticmethod
    def get_confs_dir(conf):
        return os.path.abspath(os.path.normpath(conf.dhcp_confs))

    def get_conf_file_name(self, kind):
        """Returns the file name for a given kind of config file."""
        return os.path.join(self.network_conf_dir, kind)

    def _ensure_network_conf_dir(self):
        """Ensures the directory for configuration files is created."""
        if not os.path.isdir(self.network_conf_dir):
            os.makedirs(self.network_conf_dir, 0o755)

    def _remove_config_files(self):
        shutil.rmtree(self.network_conf_dir, ignore_errors=True)

    def _enable_dhcp(self):
        """check if there is a subnet within the network with dhcp enabled."""
        for subnet in self.network.subnets:
            if subnet.enable_dhcp:
                return True
        return False

    def enable(self):
        """Enables DHCP for this network by spawning a local process."""
        if self.active:
            self.restart()
        elif self._enable_dhcp():
            self._ensure_network_conf_dir()
            interface_name = self.device_manager.setup(self.network)
            self.interface_name = interface_name
            self.spawn_process()

    def disable(self, retain_port=False):
        """Disable DHCP for this network by killing the local process."""
        pid_filename = self.get_conf_file_name('pid')

        pid = self.process_monitor.get_pid(uuid=self.network.id,
                                           service=DNSMASQ_SERVICE_NAME,
                                           pid_file=pid_filename)

        self.process_monitor.disable(uuid=self.network.id,
                                     namespace=self.network.namespace,
                                     service=DNSMASQ_SERVICE_NAME,
                                     pid_file=pid_filename)
        if pid and not retain_port:
            self.device_manager.destroy(self.network, self.interface_name)

        self._remove_config_files()

        if not retain_port:
            if self.conf.dhcp_delete_namespaces and self.network.namespace:
                ns_ip = ip_lib.IPWrapper(self.root_helper,
                                         self.network.namespace)
                try:
                    ns_ip.netns.delete(self.network.namespace)
                except RuntimeError:
                    LOG.exception(_LE('Failed trying to delete namespace: %s'),
                                  self.network.namespace)

    def _get_value_from_conf_file(self, kind, converter=None):
        """A helper function to read a value from one of the state files."""
        file_name = self.get_conf_file_name(kind)
        msg = _('Error while reading %s')

        try:
            with open(file_name, 'r') as f:
                try:
                    return converter(f.read()) if converter else f.read()
                except ValueError:
                    msg = _('Unable to convert value in %s')
        except IOError:
            msg = _('Unable to access %s')

        LOG.debug(msg, file_name)
        return None

    @property
    def interface_name(self):
        return self._get_value_from_conf_file('interface')

    @interface_name.setter
    def interface_name(self, value):
        interface_file_path = self.get_conf_file_name('interface')
        utils.replace_file(interface_file_path, value)

    @property
    def active(self):
        pid_filename = self.get_conf_file_name('pid')
        return self.process_monitor.is_active(self.network.id,
                                              DNSMASQ_SERVICE_NAME,
                                              pid_file=pid_filename)

    @abc.abstractmethod
    def spawn_process(self):
        pass


class Dnsmasq(DhcpLocalProcess):
    # The ports that need to be opened when security policies are active
    # on the Neutron port used for DHCP.  These are provided as a convenience
    # for users of this class.
    PORTS = {IPV4: [(UDP, DNS_PORT), (TCP, DNS_PORT), (UDP, DHCPV4_PORT)],
             IPV6: [(UDP, DNS_PORT), (TCP, DNS_PORT), (UDP, DHCPV6_PORT)],
             }

    _TAG_PREFIX = 'tag%d'

    NEUTRON_NETWORK_ID_KEY = 'NEUTRON_NETWORK_ID'
    NEUTRON_RELAY_SOCKET_PATH_KEY = 'NEUTRON_RELAY_SOCKET_PATH'

    @classmethod
    def check_version(cls):
        pass

    @classmethod
    def existing_dhcp_networks(cls, conf, root_helper):
        """Return a list of existing networks ids that we have configs for."""
        confs_dir = cls.get_confs_dir(conf)
        try:
            return [
                c for c in os.listdir(confs_dir)
                if uuidutils.is_uuid_like(c)
            ]
        except OSError:
            return []

    def _build_cmdline_callback(self, pid_file):
        cmd = [
            'dnsmasq',
            '--no-hosts',
            '--no-resolv',
            '--strict-order',
            '--bind-interfaces',
            '--interface=%s' % self.interface_name,
            '--except-interface=lo',
            '--pid-file=%s' % pid_file,
            '--dhcp-hostsfile=%s' % self.get_conf_file_name('host'),
            '--addn-hosts=%s' % self.get_conf_file_name('addn_hosts'),
            '--dhcp-optsfile=%s' % self.get_conf_file_name('opts'),
            '--leasefile-ro',
            '--dhcp-authoritative',
        ]

        possible_leases = 0
        for i, subnet in enumerate(self.network.subnets):
            mode = None
            # if a subnet is specified to have dhcp disabled
            if not subnet.enable_dhcp:
                continue
            if subnet.ip_version == 4:
                mode = 'static'
            else:
                # Note(scollins) If the IPv6 attributes are not set, set it as
                # static to preserve previous behavior
                addr_mode = getattr(subnet, 'ipv6_address_mode', None)
                ra_mode = getattr(subnet, 'ipv6_ra_mode', None)
                if (addr_mode in [constants.DHCPV6_STATEFUL,
                                  constants.DHCPV6_STATELESS] or
                        not addr_mode and not ra_mode):
                    mode = 'static'

            cidr = netaddr.IPNetwork(subnet.cidr)

            if self.conf.dhcp_lease_duration == -1:
                lease = 'infinite'
            else:
                lease = '%ss' % self.conf.dhcp_lease_duration

            # mode is optional and is not set - skip it
            if mode:
                if subnet.ip_version == 4:
                    cmd.append('--dhcp-range=%s%s,%s,%s,%s' %
                               ('set:', self._TAG_PREFIX % i,
                                cidr.network, mode, lease))
                else:
                    cmd.append('--dhcp-range=%s%s,%s,%s,%d,%s' %
                               ('set:', self._TAG_PREFIX % i,
                                cidr.network, mode,
                                cidr.prefixlen, lease))
                possible_leases += cidr.size

        # Cap the limit because creating lots of subnets can inflate
        # this possible lease cap.
        cmd.append('--dhcp-lease-max=%d' %
                   min(possible_leases, self.conf.dnsmasq_lease_max))

        cmd.append('--conf-file=%s' % self.conf.dnsmasq_config_file)
        if self.conf.dnsmasq_dns_servers:
            cmd.extend(
                '--server=%s' % server
                for server in self.conf.dnsmasq_dns_servers)

        if self.conf.dhcp_domain:
            cmd.append('--domain=%s' % self.conf.dhcp_domain)

        if self.conf.dhcp_broadcast_reply:
            cmd.append('--dhcp-broadcast')

        return cmd

    def spawn_process(self):
        """Spawn the process, if it's not spawned already."""
        self._spawn_or_reload_process(reload_with_HUP=False)

    def _spawn_or_reload_process(self, reload_with_HUP):
        """Spawns or reloads a Dnsmasq process for the network.

        When reload_with_HUP is True, dnsmasq receives a HUP signal,
        or it's reloaded if the process is not running.
        """

        self._output_config_files()

        pid_filename = self.get_conf_file_name('pid')

        self.process_monitor.enable(
            uuid=self.network.id,
            cmd_callback=self._build_cmdline_callback,
            namespace=self.network.namespace,
            service=DNSMASQ_SERVICE_NAME,
            cmd_addl_env={self.NEUTRON_NETWORK_ID_KEY: self.network.id},
            reload_cfg=reload_with_HUP,
            pid_file=pid_filename)

    def _release_lease(self, mac_address, ip):
        """Release a DHCP lease."""
        cmd = ['dhcp_release', self.interface_name, ip, mac_address]
        ip_wrapper = ip_lib.IPWrapper(self.root_helper,
                                      self.network.namespace)
        ip_wrapper.netns.execute(cmd)

    def _output_config_files(self):
        self._output_hosts_file()
        self._output_addn_hosts_file()
        self._output_opts_file()

    def reload_allocations(self):
        """Rebuild the dnsmasq config and signal the dnsmasq to reload."""

        # If all subnets turn off dhcp, kill the process.
        if not self._enable_dhcp():
            self.disable()
            LOG.debug('Killing dhcpmasq for network since all subnets have '
                      'turned off DHCP: %s', self.network.id)
            return

        self._release_unused_leases()
        self._spawn_or_reload_process(reload_with_HUP=True)
        LOG.debug('Reloading allocations for network: %s', self.network.id)
        self.device_manager.update(self.network, self.interface_name)

    def _iter_hosts(self):
        """Iterate over hosts.

        For each host on the network we yield a tuple containing:
        (
            port,  # a DictModel instance representing the port.
            alloc,  # a DictModel instance of the allocated ip and subnet.
            host_name,  # Host name.
            name,  # Canonical hostname in the format 'hostname[.domain]'.
        )
        """
        v6_nets = dict((subnet.id, subnet) for subnet in
                       self.network.subnets if subnet.ip_version == 6)
        for port in self.network.ports:
            for alloc in port.fixed_ips:
                # Note(scollins) Only create entries that are
                # associated with the subnet being managed by this
                # dhcp agent
                if alloc.subnet_id in v6_nets:
                    addr_mode = v6_nets[alloc.subnet_id].ipv6_address_mode
                    if addr_mode != constants.DHCPV6_STATEFUL:
                        continue
                hostname = 'host-%s' % alloc.ip_address.replace(
                    '.', '-').replace(':', '-')
                fqdn = hostname
                if self.conf.dhcp_domain:
                    fqdn = '%s.%s' % (fqdn, self.conf.dhcp_domain)
                yield (port, alloc, hostname, fqdn)

    def _output_hosts_file(self):
        """Writes a dnsmasq compatible dhcp hosts file.

        The generated file is sent to the --dhcp-hostsfile option of dnsmasq,
        and lists the hosts on the network which should receive a dhcp lease.
        Each line in this file is in the form::

            'mac_address,FQDN,ip_address'

        IMPORTANT NOTE: a dnsmasq instance does not resolve hosts defined in
        this file if it did not give a lease to a host listed in it (e.g.:
        multiple dnsmasq instances on the same network if this network is on
        multiple network nodes). This file is only defining hosts which
        should receive a dhcp lease, the hosts resolution in itself is
        defined by the `_output_addn_hosts_file` method.
        """
        buf = six.StringIO()
        filename = self.get_conf_file_name('host')

        LOG.debug('Building host file: %s', filename)
        dhcp_enabled_subnet_ids = [s.id for s in self.network.subnets
                                   if s.enable_dhcp]
        for (port, alloc, hostname, name) in self._iter_hosts():
            # don't write ip address which belongs to a dhcp disabled subnet.
            if alloc.subnet_id not in dhcp_enabled_subnet_ids:
                continue

            # (dzyu) Check if it is legal ipv6 address, if so, need wrap
            # it with '[]' to let dnsmasq to distinguish MAC address from
            # IPv6 address.
            ip_address = alloc.ip_address
            if netaddr.valid_ipv6(ip_address):
                ip_address = '[%s]' % ip_address

            LOG.debug('Adding %(mac)s : %(name)s : %(ip)s',
                      {"mac": port.mac_address, "name": name,
                       "ip": ip_address})

            if getattr(port, 'extra_dhcp_opts', False):
                buf.write('%s,%s,%s,%s%s\n' %
                          (port.mac_address, name, ip_address,
                           'set:', port.id))
            else:
                buf.write('%s,%s,%s\n' %
                          (port.mac_address, name, ip_address))

        utils.replace_file(filename, buf.getvalue())
        LOG.debug('Done building host file %s', filename)
        return filename

    def _read_hosts_file_leases(self, filename):
        leases = set()
        if os.path.exists(filename):
            with open(filename) as f:
                for l in f.readlines():
                    host = l.strip().split(',')
                    leases.add((host[2].strip('[]'), host[0]))
        return leases

    def _release_unused_leases(self):
        filename = self.get_conf_file_name('host')
        old_leases = self._read_hosts_file_leases(filename)

        new_leases = set()
        for port in self.network.ports:
            for alloc in port.fixed_ips:
                new_leases.add((alloc.ip_address, port.mac_address))

        for ip, mac in old_leases - new_leases:
            self._release_lease(mac, ip)

    def _output_addn_hosts_file(self):
        """Writes a dnsmasq compatible additional hosts file.

        The generated file is sent to the --addn-hosts option of dnsmasq,
        and lists the hosts on the network which should be resolved even if
        the dnsmaq instance did not give a lease to the host (see the
        `_output_hosts_file` method).
        Each line in this file is in the same form as a standard /etc/hosts
        file.
        """
        buf = six.StringIO()
        for (port, alloc, hostname, fqdn) in self._iter_hosts():
            # It is compulsory to write the `fqdn` before the `hostname` in
            # order to obtain it in PTR responses.
            buf.write('%s\t%s %s\n' % (alloc.ip_address, fqdn, hostname))
        addn_hosts = self.get_conf_file_name('addn_hosts')
        utils.replace_file(addn_hosts, buf.getvalue())
        return addn_hosts

    def _output_opts_file(self):
        """Write a dnsmasq compatible options file."""

        if self.conf.enable_isolated_metadata:
            subnet_to_interface_ip = self._make_subnet_interface_ip_map()

        options = []

        isolated_subnets = self.get_isolated_subnets(self.network)
        dhcp_ips = collections.defaultdict(list)
        subnet_idx_map = {}
        for i, subnet in enumerate(self.network.subnets):
            if (not subnet.enable_dhcp or
                (subnet.ip_version == 6 and
                 getattr(subnet, 'ipv6_address_mode', None)
                 in [None, constants.IPV6_SLAAC])):
                continue
            if subnet.dns_nameservers:
                options.append(
                    self._format_option(
                        subnet.ip_version, i, 'dns-server',
                        ','.join(
                            Dnsmasq._convert_to_literal_addrs(
                                subnet.ip_version, subnet.dns_nameservers))))
            else:
                # use the dnsmasq ip as nameservers only if there is no
                # dns-server submitted by the server
                subnet_idx_map[subnet.id] = i

            if self.conf.dhcp_domain and subnet.ip_version == 6:
                options.append('tag:tag%s,option6:domain-search,%s' %
                               (i, ''.join(self.conf.dhcp_domain)))

            gateway = subnet.gateway_ip
            host_routes = []
            for hr in subnet.host_routes:
                if hr.destination == "0.0.0.0/0":
                    if not gateway:
                        gateway = hr.nexthop
                else:
                    host_routes.append("%s,%s" % (hr.destination, hr.nexthop))

            # Add host routes for isolated network segments

            if (isolated_subnets[subnet.id] and
                    self.conf.enable_isolated_metadata and
                    subnet.ip_version == 4):
                subnet_dhcp_ip = subnet_to_interface_ip[subnet.id]
                host_routes.append(
                    '%s/32,%s' % (METADATA_DEFAULT_IP, subnet_dhcp_ip)
                )

            if subnet.ip_version == 4:
                if host_routes:
                    if gateway:
                        host_routes.append("%s,%s" % ("0.0.0.0/0", gateway))
                    options.append(
                        self._format_option(subnet.ip_version, i,
                                            'classless-static-route',
                                            ','.join(host_routes)))
                    options.append(
                        self._format_option(subnet.ip_version, i,
                                            WIN2k3_STATIC_DNS,
                                            ','.join(host_routes)))

                if gateway:
                    options.append(self._format_option(subnet.ip_version,
                                                       i, 'router',
                                                       gateway))
                else:
                    options.append(self._format_option(subnet.ip_version,
                                                       i, 'router'))

        for port in self.network.ports:
            if getattr(port, 'extra_dhcp_opts', False):
                for ip_version in (4, 6):
                    if any(
                        netaddr.IPAddress(ip.ip_address).version == ip_version
                            for ip in port.fixed_ips):
                        options.extend(
                            # TODO(xuhanp):Instead of applying extra_dhcp_opts
                            # to both DHCPv4 and DHCPv6, we need to find a new
                            # way to specify options for v4 and v6
                            # respectively. We also need to validate the option
                            # before applying it.
                            self._format_option(ip_version, port.id,
                                                opt.opt_name, opt.opt_value)
                            for opt in port.extra_dhcp_opts)

            # provides all dnsmasq ip as dns-server if there is more than
            # one dnsmasq for a subnet and there is no dns-server submitted
            # by the server
            if port.device_owner == constants.DEVICE_OWNER_DHCP:
                for ip in port.fixed_ips:
                    i = subnet_idx_map.get(ip.subnet_id)
                    if i is None:
                        continue
                    dhcp_ips[i].append(ip.ip_address)

        for i, ips in dhcp_ips.items():
            for ip_version in (4, 6):
                vx_ips = [ip for ip in ips
                          if netaddr.IPAddress(ip).version == ip_version]
                if vx_ips:
                    options.append(
                        self._format_option(
                            ip_version, i, 'dns-server',
                            ','.join(
                                Dnsmasq._convert_to_literal_addrs(ip_version,
                                                                  vx_ips))))

        name = self.get_conf_file_name('opts')
        utils.replace_file(name, '\n'.join(options))
        return name

    def _make_subnet_interface_ip_map(self):
        ip_dev = ip_lib.IPDevice(
            self.interface_name,
            self.root_helper,
            self.network.namespace
        )

        subnet_lookup = dict(
            (netaddr.IPNetwork(subnet.cidr), subnet.id)
            for subnet in self.network.subnets
        )

        retval = {}

        for addr in ip_dev.addr.list():
            ip_net = netaddr.IPNetwork(addr['cidr'])

            if ip_net in subnet_lookup:
                retval[subnet_lookup[ip_net]] = addr['cidr'].split('/')[0]

        return retval

    def _format_option(self, ip_version, tag, option, *args):
        """Format DHCP option by option name or code."""
        option = str(option)
        pattern = "(tag:(.*),)?(.*)$"
        matches = re.match(pattern, option)
        extra_tag = matches.groups()[0]
        option = matches.groups()[2]

        if isinstance(tag, int):
            tag = self._TAG_PREFIX % tag

        if not option.isdigit():
            if ip_version == 4:
                option = 'option:%s' % option
            else:
                option = 'option6:%s' % option
        if extra_tag:
            tags = ('tag:' + tag, extra_tag[:-1], '%s' % option)
        else:
            tags = ('tag:' + tag, '%s' % option)
        return ','.join(tags + args)

    @staticmethod
    def _convert_to_literal_addrs(ip_version, ips):
        if ip_version == 4:
            return ips
        return ['[' + ip + ']' for ip in ips]

    @classmethod
    def get_isolated_subnets(cls, network):
        """Returns a dict indicating whether or not a subnet is isolated

        A subnet is considered non-isolated if there is a port connected to
        the subnet, and the port's ip address matches that of the subnet's
        gateway. The port must be owned by a nuetron router.
        """
        isolated_subnets = collections.defaultdict(lambda: True)
        subnets = dict((subnet.id, subnet) for subnet in network.subnets)

        for port in network.ports:
            if port.device_owner not in constants.ROUTER_INTERFACE_OWNERS:
                continue
            for alloc in port.fixed_ips:
                if subnets[alloc.subnet_id].gateway_ip == alloc.ip_address:
                    isolated_subnets[alloc.subnet_id] = False

        return isolated_subnets

    @classmethod
    def should_enable_metadata(cls, conf, network):
        """Determine whether the metadata proxy is needed for a network

        This method returns True for truly isolated networks (ie: not attached
        to a router), when the enable_isolated_metadata flag is True.

        This method also returns True when enable_metadata_network is True,
        and the network passed as a parameter has a subnet in the link-local
        CIDR, thus characterizing it as a "metadata" network. The metadata
        network is used by solutions which do not leverage the l3 agent for
        providing access to the metadata service via logical routers built
        with 3rd party backends.
        """
        if conf.enable_metadata_network and conf.enable_isolated_metadata:
            # check if the network has a metadata subnet
            meta_cidr = netaddr.IPNetwork(METADATA_DEFAULT_CIDR)
            if any(netaddr.IPNetwork(s.cidr) in meta_cidr
                   for s in network.subnets):
                return True

        if not conf.use_namespaces or not conf.enable_isolated_metadata:
            return False

        isolated_subnets = cls.get_isolated_subnets(network)
        return any(isolated_subnets[subnet.id] for subnet in network.subnets)

    @classmethod
    def lease_update(cls):
        network_id = os.environ.get(cls.NEUTRON_NETWORK_ID_KEY)
        dhcp_relay_socket = os.environ.get(cls.NEUTRON_RELAY_SOCKET_PATH_KEY)

        action = sys.argv[1]
        if action not in ('add', 'del', 'old'):
            sys.exit()

        mac_address = sys.argv[2]
        ip_address = sys.argv[3]

        if action == 'del':
            lease_remaining = 0
        else:
            lease_remaining = int(os.environ.get('DNSMASQ_TIME_REMAINING', 0))

        data = dict(network_id=network_id, mac_address=mac_address,
                    ip_address=ip_address, lease_remaining=lease_remaining)

        if os.path.exists(dhcp_relay_socket):
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(dhcp_relay_socket)
            sock.send(jsonutils.dumps(data))
            sock.close()


class DeviceManager(object):

    def __init__(self, conf, root_helper, plugin):
        self.conf = conf
        self.root_helper = root_helper
        self.plugin = plugin
        if not conf.interface_driver:
            LOG.error(_LE('An interface driver must be specified'))
            raise SystemExit(1)
        try:
            self.driver = importutils.import_object(
                conf.interface_driver, conf)
        except Exception as e:
            LOG.error(_LE("Error importing interface driver '%(driver)s': "
                          "%(inner)s"),
                      {'driver': conf.interface_driver,
                       'inner': e})
            raise SystemExit(1)

    def get_interface_name(self, network, port):
        """Return interface(device) name for use by the DHCP process."""
        return self.driver.get_device_name(port)

    def get_device_id(self, network):
        """Return a unique DHCP device ID for this host on the network."""
        # There could be more than one dhcp server per network, so create
        # a device id that combines host and network ids
        return commonutils.get_dhcp_agent_device_id(network.id, self.conf.host)

    def _set_default_route(self, network, device_name):
        """Sets the default gateway for this dhcp namespace.

        This method is idempotent and will only adjust the route if adjusting
        it would change it from what it already is.  This makes it safe to call
        and avoids unnecessary perturbation of the system.
        """
        device = ip_lib.IPDevice(device_name,
                                 self.root_helper,
                                 network.namespace)
        gateway = device.route.get_gateway()
        if gateway:
            gateway = gateway['gateway']

        for subnet in network.subnets:
            skip_subnet = (
                subnet.ip_version != 4
                or not subnet.enable_dhcp
                or subnet.gateway_ip is None)

            if skip_subnet:
                continue

            if gateway != subnet.gateway_ip:
                LOG.debug('Setting gateway for dhcp netns on net %(n)s to '
                          '%(ip)s',
                          {'n': network.id, 'ip': subnet.gateway_ip})

                device.route.add_gateway(subnet.gateway_ip)

            return

        # No subnets on the network have a valid gateway.  Clean it up to avoid
        # confusion from seeing an invalid gateway here.
        if gateway is not None:
            LOG.debug('Removing gateway for dhcp netns on net %s', network.id)

            device.route.delete_gateway(gateway)

    def setup_dhcp_port(self, network):
        """Create/update DHCP port for the host if needed and return port."""

        device_id = self.get_device_id(network)
        subnets = {}
        dhcp_enabled_subnet_ids = []
        for subnet in network.subnets:
            if subnet.enable_dhcp:
                dhcp_enabled_subnet_ids.append(subnet.id)
                subnets[subnet.id] = subnet

        dhcp_port = None
        for port in network.ports:
            port_device_id = getattr(port, 'device_id', None)
            if port_device_id == device_id:
                port_fixed_ips = []
                for fixed_ip in port.fixed_ips:
                    port_fixed_ips.append({'subnet_id': fixed_ip.subnet_id,
                                           'ip_address': fixed_ip.ip_address})
                    if fixed_ip.subnet_id in dhcp_enabled_subnet_ids:
                        dhcp_enabled_subnet_ids.remove(fixed_ip.subnet_id)

                # If there are dhcp_enabled_subnet_ids here that means that
                # we need to add those to the port and call update.
                if dhcp_enabled_subnet_ids:
                    port_fixed_ips.extend(
                        [dict(subnet_id=s) for s in dhcp_enabled_subnet_ids])
                    dhcp_port = self.plugin.update_dhcp_port(
                        port.id, {'port': {'network_id': network.id,
                                           'fixed_ips': port_fixed_ips}})
                    if not dhcp_port:
                        raise exceptions.Conflict()
                else:
                    dhcp_port = port
                # break since we found port that matches device_id
                break

        # check for a reserved DHCP port
        if dhcp_port is None:
            LOG.debug('DHCP port %(device_id)s on network %(network_id)s'
                      ' does not yet exist. Checking for a reserved port.',
                      {'device_id': device_id, 'network_id': network.id})
            for port in network.ports:
                port_device_id = getattr(port, 'device_id', None)
                if port_device_id == constants.DEVICE_ID_RESERVED_DHCP_PORT:
                    dhcp_port = self.plugin.update_dhcp_port(
                        port.id, {'port': {'network_id': network.id,
                                           'device_id': device_id}})
                    if dhcp_port:
                        break

        # DHCP port has not yet been created.
        if dhcp_port is None:
            LOG.debug('DHCP port %(device_id)s on network %(network_id)s'
                      ' does not yet exist.', {'device_id': device_id,
                                               'network_id': network.id})
            port_dict = dict(
                name='',
                admin_state_up=True,
                device_id=device_id,
                network_id=network.id,
                tenant_id=network.tenant_id,
                fixed_ips=[dict(subnet_id=s) for s in dhcp_enabled_subnet_ids])
            dhcp_port = self.plugin.create_dhcp_port({'port': port_dict})

        if not dhcp_port:
            raise exceptions.Conflict()

        # Convert subnet_id to subnet dict
        fixed_ips = [dict(subnet_id=fixed_ip.subnet_id,
                          ip_address=fixed_ip.ip_address,
                          subnet=subnets[fixed_ip.subnet_id])
                     for fixed_ip in dhcp_port.fixed_ips]

        ips = [DictModel(item) if isinstance(item, dict) else item
               for item in fixed_ips]
        dhcp_port.fixed_ips = ips

        return dhcp_port

    def setup(self, network):
        """Create and initialize a device for network's DHCP on this host."""
        port = self.setup_dhcp_port(network)
        interface_name = self.get_interface_name(network, port)

        if ip_lib.ensure_device_is_ready(interface_name,
                                         self.root_helper,
                                         network.namespace):
            LOG.debug('Reusing existing device: %s.', interface_name)
        else:
            self.driver.plug(network.id,
                             port.id,
                             interface_name,
                             port.mac_address,
                             namespace=network.namespace)
        ip_cidrs = []
        for fixed_ip in port.fixed_ips:
            subnet = fixed_ip.subnet
            net = netaddr.IPNetwork(subnet.cidr)
            ip_cidr = '%s/%s' % (fixed_ip.ip_address, net.prefixlen)
            ip_cidrs.append(ip_cidr)

        if (self.conf.enable_isolated_metadata and
            self.conf.use_namespaces):
            ip_cidrs.append(METADATA_DEFAULT_CIDR)

        self.driver.init_l3(interface_name, ip_cidrs,
                            namespace=network.namespace)

        # ensure that the dhcp interface is first in the list
        if network.namespace is None:
            device = ip_lib.IPDevice(interface_name,
                                     self.root_helper)
            device.route.pullup_route(interface_name)

        if self.conf.use_namespaces:
            self._set_default_route(network, interface_name)

        return interface_name

    def update(self, network, device_name):
        """Update device settings for the network's DHCP on this host."""
        if self.conf.use_namespaces:
            self._set_default_route(network, device_name)

    def destroy(self, network, device_name):
        """Destroy the device used for the network's DHCP on this host."""
        self.driver.unplug(device_name, namespace=network.namespace)

        self.plugin.release_dhcp_port(network.id,
                                      self.get_device_id(network))
