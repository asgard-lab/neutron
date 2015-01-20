from sqlalchemy import Column, String, ForeignKey, Integer
from sqlalchemy.orm import relationship, backref

from neutron.db.model_base import BASEV2
from neutron.db.models_v2 import HasId

class DatacomNetwork(BASEV2, HasId):
    """Each VLAN represent a Network
    a network may have multiple ports
    """
    vid = Column(Integer)
    name = Column(String(30))

class DatacomPort(BASEV2, HasId):
    """Each port is connected to a network
    """
    port = Column(Integer)

    network_id = Column(String(36), ForeignKey('datacomnetworks.id'))
    network = relationship('DatacomNetwork', backref=backref('ports'))
