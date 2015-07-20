import testtools
import neutron.plugins.ml2.drivers.datacom.dcclient.xml_manager.manager as mg
import neutron.plugins.ml2.drivers.datacom.dcclient.xml_manager.\
                                                        data_structures as ds


class main_test(testtools.TestCase):
    def test_findVlan(self):
        # tests if none type is return when vlan is not found
        xml = mg.ManagedXml()

        answer = xml.findVlan(61)
        self.assertIs(answer, None)

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
