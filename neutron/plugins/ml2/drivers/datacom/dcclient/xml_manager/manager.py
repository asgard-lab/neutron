""" Methos to create and manipulate the XML
"""
import data_structures
import neutron.plugins.ml2.drivers.datacom.utils as utils

class ManagedXml:
    def __init__(self):
        self.xml = data_structures.Cfg_data()

    def findVlan(self, vid):
        """ Find the vlan with the specified vid
        """

        reduced_list = [i for i in self.xml.vlans if i.vid == vid]
        if reduced_list:
            return reduced_list[0]
        else:
            return None

    def addVlan(self, vid, name='', ports=[]):
        """ This method adds a vlan to the XML an returns it's instance.
        """

        if self.findVlan(vid):
            raise XMLVlanError("Vlan already exists "+str(vid))

        vlan = data_structures.Vlan_global(vid)

        if name:
            vlan.name = name

        if ports:
            vlan.ports = data_structures.Pbits(ports)

        self.xml.vlans.append(vlan)

        return vlan

    def removeVlan(self, vid):
        """ This method revmoes a vlan on the XML if it exists.
        """

        if not self.findVlan(vid):
            raise XMLVlanError("Vlan does not exsits or the vid " + vid + \
                    " is invalid")

        vlan = self.findVlan(vid)
        del vlan.active

    def addPortsToVlan(self, vid, ports):
        """ This method adds ports to an existing vlan
        """

        vlan = self.findVlan(vid)
        if vlan:
            vlan.ports.add_bits(ports)
        else:
            raise XMLPortError("No such vlan "+str(vid))

    def removePortsFromVlan(self, vid, ports):
        """ This method removoes ports from an existing vlan
        """

        vlan = self.findVlan(vid)
        if vlan:
            vlan.ports.remove_bits(ports)
        else:
            raise XMLVlanError("No such vlan "+str(vid))

    def as_xml(self):
        """ This method returns the xml version of the object
        """
        return self.tostring()

    def tostring(self):
        """ An alias to as_xml()
        """
        return self.xml.as_xml_text()

if __name__ == '__main__':
    xml = ManagedXml()
    vlan = xml.addVlan(42, name='aaa')

    xml.addPortsToVlan(42, [2])

    from dcclient.rpc import RPC
    switch = RPC('admin', 'admin', '192.168.0.11', 'http')
