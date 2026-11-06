class HelpdeskError(Exception):
    pass


class TicketNotFoundError(HelpdeskError):
    pass


class InvalidTicketStateError(HelpdeskError):
    pass


class DeliveryFailedError(HelpdeskError):
    pass
