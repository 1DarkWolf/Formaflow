class ConflitoWorkflow(Exception):
    """Raised when an optimistic workflow version no longer matches."""


class TransicaoInvalida(Exception):
    """Raised when a transition is not allowed from the current state."""
