from uuid import UUID


class DomainError(Exception):
    """Base exception for expected business rule failures."""


class OrderNotFound(DomainError):
    def __init__(self, order_id: UUID) -> None:
        super().__init__(f"Order {order_id} was not found")


class AccountNotFound(DomainError):
    def __init__(self, account_id: UUID) -> None:
        super().__init__(f"Account {account_id} was not found")


class InvalidStateTransition(DomainError):
    def __init__(self, current: str, target: str) -> None:
        super().__init__(f"Order cannot transition from {current} to {target}")


class InsufficientBuyingPower(DomainError):
    def __init__(self) -> None:
        super().__init__("Insufficient buying power")


class DuplicateOrder(DomainError):
    def __init__(self, client_order_id: str) -> None:
        super().__init__(f"Order {client_order_id} already exists")


class DuplicateAccount(DomainError):
    def __init__(self, user_id: str) -> None:
        super().__init__(f"Account for user {user_id} already exists")


class InvalidCancellation(DomainError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)


class InvalidFill(DomainError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)


class BrokerUnavailable(DomainError):
    def __init__(self) -> None:
        super().__init__("Broker is temporarily unavailable")
