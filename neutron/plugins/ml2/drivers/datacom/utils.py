MIN_VLAN = 2
MAX_VLAN = 1000

# It is still used the constant bag type, but it will transit to the class bagef class vlan:
class vlan:
    def __init__(self):
        self.MIN_INDEX = 2
        self.MAX_INDEX = 1000

class ExceptionTemplate(Exception):
    def __call__(self, *args):
        return self.__class__(*(self.args + args))

class XMLVlanError(ExceptionTemplate): pass

class XMLPortError(ExceptionTemplate): pass

class RPCError(ExceptionTemplate): pass

class DMConfigError(ExceptionTemplate): pass
