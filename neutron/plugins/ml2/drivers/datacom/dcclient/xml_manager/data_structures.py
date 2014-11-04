""" Data structures used to build the XML
"""

import xml.etree.ElementTree as ET
import neutron.plugins.ml2.drivers.datacom.utils as utils


class Pbits(object):
    """ Class pbits represents bitmasks (usually from ports)

        This class has one property:
            bits: Internally this property is implemented as an integer.
                  It can be set by using either an integer or a list that
                  will be converted to the corresponding integer.
                  For example using it with class.bits = [1,3,4] will
                  result in an integer with the bits 1, 3, 4 set (1101)=13.

        To instantiate this class you need the following parameters:
            bits (required): int or list.
    """

    def __init__(self, bits):
        self.bits = bits

    @property
    def bits(self):
        return self._bits

    @bits.setter
    def bits(self, bits):
        assert type(bits) is int or type(bits) is list
        if type(bits) is int:
            self._bits = bits
        else:
            self._bits = sum([1 << (i-1) for i in set(bits)])

    @bits.deleter
    def bits(self):
        self._bits = 0

    def as_xml(self):
        """ Method that returns the xml form of the object
        """
        xml = ET.Element("pbits")
        xml.attrib["id0"] = "0"
        xml.text = str(self.bits)
        return xml

    def as_xml_text(self):
        return ET.tostring(self.as_xml())

    def add_bits(self, bits):
        assert type(bits) is int or type(bits) is list
        if type(bits) is int:
            new_bits = bits
        else:
            new_bits = sum([1 << (i-1) for i in set(bits)])

        self.bits = self.bits | new_bits

    def remove_bits(self, bits):
        assert type(bits) is int or type(bits) is list
        if type(bits) is int:
            new_bits = bits
        else:
            new_bits = sum([1 << (i-1) for i in set(bits)])

        self.bits = self.bits & ~ new_bits


class Vlan_global(object):
    """ Class vlanglobal represents a VLan.

        This class has three properties:
            vid: This property is an integer. It is used as the id of the vlan.
            ports: This property is a pbits. Ultimatly is used as a binary,
                   this binary is what defines wich ports asociated with the
                   vlan. the add_bits and remove_birs methods are used to
                   change this property hence changing the ports.
            name: This property is a string. It is used to refer to the vlan
                  in a more friendly way, rather then using the vid.

        To instantiate this class you need the following parameters:
            vid (required): int.
            name (optional): string.
            ports (optional): Pbits.
    """
    # TODO: adicionar checagens de limites nas properties

    def __init__(self, vid, name='', ports=None):
        self.vid = vid
        if ports:
            self.ports = ports
        else:
            self.ports = Pbits(0)
        self.name = name

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name):
        assert type(name) is str
        self._name = name

    @name.deleter
    def name(self):
        self._name = ''

    @property
    def vid(self):
        return self._vid

    @vid.setter
    def vid(self, vid):
        assert type(vid) is int
        assert vid >= utils.MIN_VLAN and vid <= utils.MAX_VLAN
        self._vid = vid

    @vid.deleter
    def vid(self):
        self._vid = 0

    @property
    def ports(self):
        return self._ports

    @ports.setter
    def ports(self, ports):
        assert isinstance(ports, Pbits)
        self._ports = ports

    @ports.deleter
    def ports(self):
        self.ports = None

    def as_xml(self):
        """ Method that returns the xml form of the object
        """
        xml = ET.Element("vlan_global")
        xml.attrib["id0"] = str(self.vid)
        ET.SubElement(xml, "vid").text = str(self.vid)
        ET.SubElement(xml, "active").text = "1"
        if self.name:
            ET.SubElement(xml, "name").text = self.name
        if self.ports:
            pbmp_untagged = ET.SubElement(xml, "pbmp_untagged", {"id0": "0"})
            pbmp_untagged.append(self.ports.as_xml())
        return xml

    def as_xml_text(self):
        return ET.tostring(self.as_xml())


class Cfg_data(object):
    """ One class to contain them all

        This class has one property:
            vlans: This property is a vlan_global. The cfg_data is the main
                   class to the xml, so it will receive everything that is
                   needed to the xml.

        To instantiate this class you need the following parameters:
            vlans (optional): list (elements of type Vlan_global).
    """

    def __init__(self, vlans=None):
        if vlans:
            self.vlans = vlans
        else:
            self.vlans = []

    @property
    def vlans(self):
        return self._vlans

    @vlans.setter
    def vlans(self, vlans):
        assert type(vlans) is list
        # first check if every member of the list is a vlan
        for vlan in vlans:
            assert isinstance(vlan, Vlan_global)

        # now create the list and add each vlan
        self._vlans = []

        for vlan in vlans:
            self._vlans.append(vlan)

    @vlans.deleter
    def vlans(self):
        self._vlans = []

    def as_xml(self):
        xml = ET.Element("cfg_data")
        for vlan in self.vlans:
            xml.append(vlan.as_xml())
        return xml

    def as_xml_text(self):
        return ET.tostring(self.as_xml())


class Interface(object):
    """ Class interface represents a switch interface
    """
    pass


if __name__ == '__main__':
    vlan = Vlan_global(42)
    ports = Pbits([2, 3, 6])

    vlan.ports = ports

    c = Cfg_data()
    c.vlans = [vlan]
