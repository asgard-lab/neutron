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
        self.switches_dic = {}

        self.xml = ManagedXml()

    def setup(self):
        # Setup specific configurations
        oslo_parser = cfg.MultiConfigParser()
        parsed_buf = oslo_parser.read(cfg.CONF.config_file)

        if not len(parsed_buf) == len(cfg.CONF.config_file):
            raise ValueError("Parsing problem")
            # TODO :create a proper exception!

        config = oslo_parser.parsed[0]

        # get each switch from config file
        switches = [i for i in config if str(i) != 'ml2_datacom']

        # create the actualy dictionary
        for switch in switches:
            sw_dic = config[switch]
            # each field is a list, when it should be a value
            for i in sw_dic:
                sw_dic[i] = sw_dic[i][0]

            # get each global configuration, when not mentioned in the specific
            for field in cfg.CONF.ml2_datacom:
                if not field in sw_dic:
                    sw_dic[field] = cfg.CONF.ml2_datacom[field]

            sw_dic['rpc'] = rpc.RPC(str(sw_dic['dm_username']),
                                    str(sw_dic['dm_password']),
                                    str(switch),
                                    str(sw_dic['dm_method']))

            self.switches_dic[switch] = sw_dic

    def _update(self):
        for switch in self.switches_dic:
            self.switches_dic[switch]['rpc'].send_xml(self.xml.tostring())

    def create_network(self, vlan, name=''):
        """ Creates a new network on the switch, if it does not exist already.
        """
        try:
            self.xml.addVlan(vlan, name=name)
            self._update()
        except:
            LOG.info("Trying to create already existing network %d:", vlan)
