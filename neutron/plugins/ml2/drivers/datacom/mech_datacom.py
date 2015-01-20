# Copyright (c) 2013 OpenStack Foundation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from oslo.config import cfg

from neutron.plugins.ml2 import driver_api as api

from dcclient.dcclient import Manager


import config
config.setup_config()

class DatacomDriver(api.MechanismDriver):
    """    """
    def __init__(self):
        self.dcclient = Manager()
        pass

    def initialize(self):
        self.dcclient.setup()

    def _find_ports(compute):
        """Returns dictionary with the switches containing the compute, 
        and each respective port.
        """
        ports = {}
        for switch in self.dcclient.switches_dic:
            if compute in self.dcclient.switches_dic[switch]:
                ports[switch] = self.dcclient.switches_dic[switch][compute]
        return ports

    def create_network_precommit(self, context):
        """Within transaction."""
        pass

    def create_network_postcommit(self, context):
        """After transaction is done."""
        vlan = int(context.network_segments[0]['segmentation_id'])
        self.dcclient.create_network(vlan, name=str(context.current['name']))

    def update_network_precommit(self, context):
        """Within transaction."""
        pass

    def update_network_postcommit(self, context):
        """After transaction is done."""
        pass

    def delete_network_precommit(self, context):
        """Within transaction."""
        pass

    def delete_network_postcommit(self, context):
        """After transaction is done."""
        pass

    def create_port_precommit(self, context):
        """Within transaction."""
        pass

    def create_port_postcommit(self, context):
        """After transaction is done."""
        pass

    def update_port_precommit(self, context):
        """Within transaction."""
        pass

    def update_port_postcommit(self, context):
        """After transaction."""
        import ipdb; ipdb.set_trace() # BREAKPOINT
        if context.bound_segment is not None and \
           str(context.bound_segment['network_type']) == "vxlan":
            ports = _find_ports(context.host)
            if ports:
                vlan = int(context.bound_segment['segmentation_id'])
                self.dcclient.update_port(vlan,ports)

    def delete_port_precommit(self, context):
        """Within transaction."""
        pass

    def delete_port_postcommit(self, context):
        """After transaction."""
        pass
