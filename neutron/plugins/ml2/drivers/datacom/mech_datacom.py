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
import neutron.db.api as db

from dcclient.dcclient import Manager
from dcclient.xml_manager.data_structures import Pbits
from db.models import DatacomNetwork, DatacomPort

import config
config.setup_config()

class DatacomDriver(api.MechanismDriver):
    """    """
    def __init__(self):
        self.dcclient = Manager()
        pass

    def initialize(self):
        self.dcclient.setup()

    def _find_ports(self, compute):
        """Returns dictionary with the switches containing the compute,
        and each respective port.
        """
        ports = {}
        switches_dic = self.dcclient.switches_dic
        for switch in switches_dic:
            if compute in switches_dic[switch]:
                if switch not in ports:
                    ports[switch] = [switches_dic[switch][compute]]
                else:
                    ports[switch].append(switches_dic[switch][compute])
        return ports

    def _add_ports_to_db(self, ports, context):
        vlan = int(context.bound_segment['segmentation_id'])
        session = db.get_session()
        with session.begin(subtransactions=True):
            vlan =  context.network.network_segments[0]['segmentation_id']
            query = session.query(DatacomNetwork)
            resultset = query.filter(DatacomNetwork.vlan == vlan)
            dcnetwork = resultset.first()
            for ip in ports:
                for port in ports[ip]:
                    dcport = DatacomPort(network = dcnetwork,
                                         switch = ip,
                                         interface = port)
                    session.add(dcport)


    def create_network_precommit(self, context):
        """Within transaction."""
        session = db.get_session()
        with session.begin(subtransactions=True):
            dm_network = DatacomNetwork(
                    vlan = int(context.network_segments[0]['segmentation_id']),
                    name = context.current['name'])
            session.add(dm_network)

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
        if context.bound_segment is not None and \
           str(context.bound_segment['network_type']) == "vxlan":
            ports = self._find_ports(context.host)
            if ports:
                self._add_ports_to_db(ports, context)

    def update_port_postcommit(self, context):
        """After transaction."""
        pass


    def delete_port_precommit(self, context):
        """Within transaction."""
        pass

    def delete_port_postcommit(self, context):
        """After transaction."""
        pass
