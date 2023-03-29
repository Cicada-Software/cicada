class CicadaException(Exception):
    pass


class Unauthorized(CicadaException):
    pass


class NotFound(CicadaException):
    pass


class InvalidRequest(CicadaException):
    pass
