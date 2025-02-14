class BadRequestError(Exception):
    pass


class AuthenticationError(Exception):
    pass


class PermissionDeniedError(Exception):
    pass


class NotFoundError(Exception):
    pass


class ConflictError(Exception):
    pass


class UnprocessableEntityError(Exception):
    pass


class RateLimitError(Exception):
    pass
