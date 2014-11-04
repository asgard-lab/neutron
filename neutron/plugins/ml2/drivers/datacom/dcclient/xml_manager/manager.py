""" Methos to create and manipulate the XML
"""
import data_structures


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
            raise ValueError("Vlan already exists "+str(vid))  # proper error

        vlan = data_structures.Vlan_global(vid)

        if name:
            vlan.name = name

        if ports:
            vlan.ports = data_structures.Pbits(ports)

        self.xml.vlans.append(vlan)

        return vlan

    def addPortsToVlan(self, vid, ports):
        """ This method adds ports to an existing vlan
        """

        vlan = self.findVlan(vid)
        if vlan:
            vlan.ports.add_bits(ports)
        else:
            raise ValueError("No such vlan "+str(vid))  # Create proper error

    def tostring(self):
        return self.xml.as_xml_text()

if __name__ == '__main__':
    xml = ManagedXml()
    vlan = xml.addVlan(42, name='aaa', ports=[1, 3, 4])

    xml.addPortsToVlan(42, [2])
