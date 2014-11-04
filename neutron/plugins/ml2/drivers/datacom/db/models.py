from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.orm import relationship, backref

from neutron.db.model_base import BASEV2
from neutron.db.models_v2 import HasId


class DatacomTenant(BASEV2, HasId):
    """Datacom Tenant table"""
    tenant = Column(String(50))


class DatacomNetwork(BASEV2, HasId):
    """Each VLAN represent a Network
    Multiple networks may be associated with a tenant
    """
    vlan = Column(String(10))
    tenant_id = Column(String(36), ForeignKey('datacomtenant.id'))
    tenant = relationship('DatacomTenant', backref=backref('datacomtenants'))


class DatacomPort(BASEV2, HasId):
    """Each port is connected to a network"""
    port = Column(String(36))

    network_id = Column(String(36), ForeignKey('datacomnetwork.id'))
    network = relationship('DatacomNetwork', backref=backref('ports'))
