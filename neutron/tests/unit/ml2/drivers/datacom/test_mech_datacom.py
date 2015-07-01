import testtools
import neutron.plugins.ml2.drivers.datacom.mech_datacom as mech_datacom
from oslo.config import cfg
import mock
from neutron.db import model_base
from neutron.db import models_v2
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import neutron.db.api as db
import etc
from oslo.config import cfg
from neutron.plugins.ml2.drivers.datacom.db.models import\
                                            DatacomNetwork, DatacomPort

cfg.CONF.config_file = ''
cfg.MultiConfigParser = mock.Mock()
class mocked_context:
    network_segments = [{'segmentation_id':20}]
    current = {'name':'test'}

def add_network(session, vlan, name):
    dm_network = DatacomNetwork(vlan=vlan, name=name)
    session.add(dm_network)

# db decorator, creates the local engine and starts db
def uses_db(networks=[], ports=[]):
    def wrapp_func(func):
        def func_with_db(*args, **kwargs):
            engine = create_engine('sqlite:///:memory:')
            session = sessionmaker()
            session.configure(bind=engine)
            model_base.BASEV2.metadata.create_all(engine)
            ses = session()
            if (networks):
                for vlan,name in networks:
                    add_network(ses, vlan, name)
            ses.close()
            db.get_session = session
            func(*args, **kwargs)
            del engine
        return func_with_db
    return wrapp_func

class main_test(testtools.TestCase):

    @uses_db()
    def test_create_network_precommit(self):
        driver = mech_datacom.DatacomDriver()
        driver.dcclient = etc.base_manager(cfg.MultiConfigParser)
        driver.create_network_precommit(mocked_context())
        session = db.get_session()
        query = session.query(DatacomNetwork)
        resultset = query.filter(DatacomNetwork.vlan == 20)
        self.assertEquals(1, resultset.count())

    def test_create_network_postcommit(self):
        context = mocked_context()
        vlan = int(context.network_segments[0]['segmentation_id'])
        driver = mech_datacom.DatacomDriver()
        driver.dcclient = etc.base_manager(cfg.MultiConfigParser)
        driver.dcclient.create_network = mock.Mock()
        driver.create_network_postcommit(context)
        driver.dcclient.create_network.assertCalledOnceWith(20,'test')

