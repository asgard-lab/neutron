""" Main class from dcclient. Manages XML interaction, as well as switch and
creates the actual networks
"""

import rpc
from xml_manager.manager import ManagedXml


from neutron.openstack.common import log as logger
from oslo.config import cfg


LOG = logger.getLogger(__name__)

class Manager:
    def __init__(self):
         self.rpc = rpc.RPC(cfg.CONF.ml2_datacom.dm_username,
                         cfg.CONF.ml2_datacom.dm_password,
                         cfg.CONF.ml2_datacom.dm_host,
                         cfg.CONF.ml2_datacom.dm_method)

         self.xml = ManagedXml()

    def _update(self):
        self.rpc.send_xml(self.xml.xml.as_xml_text())

    def create_network(self, vlan, name=''):
        """ Creates a new network on the switch, if it does not exist already.
        """
        try:
            self.xml.addVlan(vlan, name=name)
            self._update()
        except:
            LOG.info("Trying to create already existing network %d:", vlan)
