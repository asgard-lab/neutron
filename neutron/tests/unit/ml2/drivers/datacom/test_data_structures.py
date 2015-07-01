import testtools
import neutron.plugins.ml2.drivers.datacom.dcclient.xml_manager.data_structures as ds


class main_test(testtools.TestCase):
    def test_pbits(self):
        # test constructor consistency
        int_cons = ds.Pbits(9)
        list_cons = ds.Pbits([1, 4])

        self.assertEquals(9, int_cons.bits,
                          'Pbits int constructor setting wrong number')
        self.assertEquals(9, list_cons.bits,
                          'Pbits list contructor setting wrong number')

        # test auxiliary methods
        list_cons.add_bits([2, 3])
        self.assertEquals(15, list_cons.bits,
                          '')

        list_cons = list_cons+[5]
        self.assertIs(31, list_cons.bits)

        list_cons = list_cons-[5]
        self.assertIs(15, list_cons.bits)

        list_cons.remove_bits([1, 4])
        self.assertIs(6, list_cons.bits)

        # test xml
        expected_xml = '<pbits id0="0">6</pbits>'
        actual_xml = list_cons.as_xml_text()
        self.assertEquals(expected_xml, actual_xml)

    def test_vlan_global(self):
        # test constructor consistency
        # simple constructor
        vlan = ds.Vlan_global(42)
        self.assertIs(42, vlan.vid)

        # test if vlan is active by default
        self.assertTrue(vlan.active)

        # test if name is empty by default
        self.assertIs('', vlan.name)

        # test if ports is 0 by default
        self.assertIs(0, vlan.ports.bits)

        # test if vlan can be initialized as not active
        vlan = ds.Vlan_global(42, active=False)
        self.assertFalse(vlan.active)

        # tests if vlan can be initialized with ports
        vlan = ds.Vlan_global(42, ports=ds.Pbits(9))
        self.assertIs(9, vlan.ports.bits)

        # tests if vlan can be initialized with name
        vlan = ds.Vlan_global(42, name='test')
        self.assertIs('test', vlan.name)


        # tests if vlan can be set as active
        vlan = ds.Vlan_global(42, active=False)
        vlan.active = True
        self.assertTrue(vlan.active)

        # tests if vlan can be set as inactive
        vlan.active = False
        self.assertFalse(vlan.active)

        # tests if name can be set
        vlan.name = 'true_test'
        self.assertIs('true_test', vlan.name)

        # tests if vid can be changed
        vlan.vid = 43
        self.assertIs(43, vlan.vid)

        # tests if ports can be changed
        vlan.ports = ds.Pbits(12)
        self.assertEquals(12, vlan.ports.bits)

        vlan = ds.Vlan_global(42)
        vlan.ports = ds.Pbits([1, 3, 4])
        vlan.name = "vlan_test"

        expected_xml = '<vlan_global id0="42"><vid>42</vid><active>1' + \
                       '</active><name>vlan_test</name>' + \
                       '<pbmp_untagged id0="0"><pbits id0="0">13</pbits>' + \
                       '</pbmp_untagged></vlan_global>'
        actual_xml = vlan.as_xml_text()
        self.assertEquals(expected_xml, actual_xml)

    def test_cfg_data(self):
        cfg = ds.Cfg_data()

        vlan = ds.Vlan_global(42, name="vlan_test", ports=ds.Pbits([1, 3, 4]))

        cfg.vlans.append(vlan)

        expected_xml = '<cfg_data><vlan_global id0="42"><vid>42</vid>' + \
                       '<active>1</active><name>vlan_test</name>' + \
                       '<pbmp_untagged id0="0"><pbits id0="0">13</pbits>' + \
                       '</pbmp_untagged></vlan_global></cfg_data>'

        actual_xml = cfg.as_xml_text()

        self.assertEquals(expected_xml, actual_xml)


        del cfg.vlans
        expected_xml = '<cfg_data><vlan_global id0="42"><vid>42</vid>' + \
                       '<active>0</active><name>vlan_test</name>' + \
                       '<pbmp_untagged id0="0"><pbits id0="0">13</pbits>' + \
                       '</pbmp_untagged></vlan_global></cfg_data>'
        actual_xml = cfg.as_xml_text()
        self.assertEquals(expected_xml, actual_xml)

