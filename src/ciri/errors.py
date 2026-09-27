"""Platform errors. Callers log these and stop the stage that raised them."""


class CiriError(Exception):
    """Base class for expected platform failures."""


class DataValidationError(CiriError):
    """A dataset failed a quality gate and was not loaded."""


class WarehouseError(CiriError):
    """The warehouse is missing or a query could not be completed."""


class ModelError(CiriError):
    """A model artifact is missing or could not be scored."""
