from oslo.config import cfg

""" Configuration for the datacom switch.
 
The options are used to locate datacom switches and identify
openstack. The dm_username and dm_password are the credentials
and the dm_host is the IP for the switch. The region name is the
identifier for the controller.
"""

DATACOM_DRIVER_OPTS = [
    cfg.StrOpt('dm_username',
               default='',
               help=_('(required) Username for the dm connection.'
                      'If not set, the identification will fail.')),
    cfg.StrOpt('dm_password',
               default='',
               secret=True,  # do not expose value in the logs
               help=_('(required) Password for the dm connection.'
                      'If not set, the identification will fail.')),
    cfg.StrOpt('dm_host',
               default='',
               help=_('(required) IP to be connected to..'
                      'If not set, the identification will fail.')),
    cfg.IntOpt('dm_port',
               default=443,
               help=_('Port to be connected to, default is 443.')),
    cfg.StrOpt('dm_method',
               default='https',
               help=_('Connection method (default is https)')),
    cfg.StrOpt('region_name',
               default='RegionOne',
               help=_('If multiple OpenStack/Neutron controllers are involved,'
                      'region_name identifies each one. Most of the times the '
                      'value will be "RegionOne", which is the default value '))
]

def setup_config():
    cfg.CONF.register_opts(DATACOM_DRIVER_OPTS, "ml2_datacom")
