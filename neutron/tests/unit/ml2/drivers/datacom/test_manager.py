import testtools
import neutron.plugins.ml2.drivers.datacom.dcclient.xml_manager.manager as mg
import neutron.plugins.ml2.drivers.datacom.dcclient.xml_manager.data_structures as ds
import neutron.plugins.ml2.drivers.datacom.utils as utils

class main_test(testtools.TestCase):
    def test_as_xml(self):
        # tests if a xml is correct
        xml = mg.ManagedXml()
        xml.addVlan(42, name='testVlan', ports=[1,3,4,5,6,8,11])
        expected_xml = '<cfg_data><vlan_global id0="42"><vid>42</vid>' + \
                       '<active>1</active><name>testVlan</name>' + \
                       '<pbmp_untagged id0="0"><pbits id0="0">1213</pbits>' + \
                       '</pbmp_untagged></vlan_global></cfg_data>'
        self.assertEquals(expected_xml, xml.as_xml())

    def test_tostring(self):
        # tests if the method tostring is correct
        xml = mg.ManagedXml()
        xml.addVlan(42, name='testVlan', ports=[1,3,4,5,6,8,11])
        expected_xml = '<cfg_data><vlan_global id0="42"><vid>42</vid>' + \
                       '<active>1</active><name>testVlan</name>' + \
                       '<pbmp_untagged id0="0"><pbits id0="0">1213</pbits>' + \
                       '</pbmp_untagged></vlan_global></cfg_data>'
        self.assertEquals(expected_xml, xml.tostring())

    def test_findVlan(self):
        # tests if none type is return when vlan is not found
        xml = mg.ManagedXml()

        answer = xml.findVlan(61)
        self.assertEquals(answer, None)

        # tests if Vlan_global object is return when vlan is found
        xml.addVlan(60, name='vlan_test', ports=[1, 5, 9])

        answer = xml.findVlan(60)
        self.assertIsInstance(answer, ds.Vlan_global)

        # tests if found vlan xml is correct
        expected_xml = '<vlan_global id0="60"><vid>60</vid><active>1' + \
                       '</active><name>vlan_test</name>' + \
                       '<pbmp_untagged id0="0"><pbits id0="0">273</pbits>' + \
                       '</pbmp_untagged></vlan_global>'

        self.assertEquals(expected_xml, answer.as_xml_text())

    def test_addVlan(self):
        # tests if is raised an exception if a already added vlan is added
        xml = mg.ManagedXml()
        xml.addVlan(42)
        self.assertRaises(utils.XMLVlanError, xml.addVlan,42)

        # tests if non existent vlan is added correctly given vid
        xml = mg.ManagedXml()
        xml.addVlan(42)
        expected_xml = '<cfg_data><vlan_global id0="42"><vid>42</vid>' + \
                       '<active>1</active><pbmp_untagged id0="0">' + \
                       '<pbits id0="0">0</pbits></pbmp_untagged>' + \
                       '</vlan_global></cfg_data>'
        self.assertEquals(expected_xml, xml.as_xml())

	    # tests if non existent vlan is added correctly given vid and name
        xml = mg.ManagedXml()
        xml.addVlan(42, name='vlan_test')
        expected_xml = '<cfg_data><vlan_global id0="42"><vid>42</vid>' + \
                       '<active>1</active><name>vlan_test</name>' + \
                       '<pbmp_untagged id0="0"><pbits id0="0">0</pbits>' + \
                       '</pbmp_untagged></vlan_global></cfg_data>'
        self.assertEquals(expected_xml, xml.as_xml())

        # tests if non existent vlan is added correclty given vid and ports
        xml = mg.ManagedXml()
        xml.addVlan(42, ports=[1,5,9])
        expected_xml = '<cfg_data><vlan_global id0="42"><vid>42</vid>' + \
                       '<active>1</active><pbmp_untagged id0="0">' + \
                       '<pbits id0="0">273</pbits></pbmp_untagged>' + \
                       '</vlan_global></cfg_data>'
        self.assertEquals(expected_xml, xml.as_xml())

        # tests if non existent vlan is added correctly given vid, name and ports
        xml = mg.ManagedXml()
        xml.addVlan(42, name='vlan_test', ports=[1,5,9])
        expected_xml = '<cfg_data><vlan_global id0="42"><vid>42</vid>' + \
                       '<active>1</active><name>vlan_test</name>' + \
                       '<pbmp_untagged id0="0"><pbits id0="0">273</pbits>' + \
                       '</pbmp_untagged></vlan_global></cfg_data>'
        self.assertEquals(expected_xml, xml.as_xml())

    def test_removeVlan(self):
        # tests if an exception is raised if a non existent Vlan is attempted
        # to be removed
        xml = mg.ManagedXml()
        self.assertRaises(utils.XMLVlanError, xml.removeVlan, 42)

        # tests if a Vlan is properly removed
        xml = mg.ManagedXml()
        xml.addVlan(60, name='vlan_test', ports=[1, 5, 9])
        xml.removeVlan(60)
        expected_xml = '<cfg_data><vlan_global id0="60"><vid>60</vid>' + \
                       '<active>0</active><name>vlan_test</name>' + \
                       '<pbmp_untagged id0="0"><pbits id0="0">273</pbits>' + \
                       '</pbmp_untagged></vlan_global></cfg_data>'
        self.assertEquals(expected_xml, xml.as_xml())

    def test_addPortsToVlan(self):
        # tests to add a port in an invalid vlan, receiveing an exception
        xml = mg.ManagedXml()
        xml.addVlan(42, 'testVlan')
        self.assertRaises(utils.XMLPortError, xml.addPortsToVlan, 43, [2])

        # tests the add of a series of ports in an existent vlan
        xml = mg.ManagedXml()
        xml.addVlan(42, 'testVlan')
        xml.addPortsToVlan(42, [2])
        expected_xml = '<cfg_data><vlan_global id0="42"><vid>42</vid>' + \
                       '<active>1</active><name>testVlan</name>' + \
                       '<pbmp_untagged id0="0"><pbits id0="0">2</pbits>' + \
                       '</pbmp_untagged></vlan_global></cfg_data>'
        self.assertEquals(expected_xml, xml.as_xml())

    def test_removePortsFromVlan(self):
        # tests to remove a port from an invalid vlan, receiving an exception
        xml = mg.ManagedXml()
        self.assertRaises(utils.XMLVlanError, xml.removePortsFromVlan, 42, 2)

        # tests to remove a port from a valid vlan
        xml = mg.ManagedXml()
        xml.addVlan(42, 'testVlan', ports=[1,5,9])
        xml.removePortsFromVlan(42, 5)
        expected_xml = '<cfg_data><vlan_global id0="42"><vid>42</vid>' + \
                       '<active>1</active><name>testVlan</name>' + \
                       '<pbmp_untagged id0="0"><pbits id0="0">272</pbits>' + \
                       '</pbmp_untagged></vlan_global></cfg_data>'
        self.assertEquals(expected_xml, xml.as_xml())
