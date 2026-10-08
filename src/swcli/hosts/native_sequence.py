"""Scope SOLIDWORKS' out-of-process API update suppression to one request."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator, Optional

from .native_trace import native_call
from .windows import _com_value


class NativeCommandRestoreFailed(RuntimeError):
    """The host's command state is unknown; do not dispatch another request."""

    def __init__(self, restore_error: Exception, operation_error: Optional[BaseException]):
        self.restore_error = restore_error
        self.operation_error = operation_error
        previous = (
            f" after {type(operation_error).__name__}"
            if operation_error is not None else ""
        )
        super().__init__(
            "could not restore SOLIDWORKS CommandInProgress"
            f"{previous}; explicit daemon restart is required: {restore_error}"
        )


@contextmanager
def native_api_sequence(app: Any, *, enabled: bool) -> Iterator[None]:
    """Only owned hosts opt in; preserve any pre-existing command state."""

    if not enabled or bool(_com_value(app, "CommandInProgress")):
        yield
        return
    operation_error = None
    try:
        # Even a setter exception can follow a server-side change. Restoration
        # therefore covers entering the scope as well as the operation body.
        native_call("api-sequence", "SldWorks.CommandInProgress.enter",
                    lambda: setattr(app, "CommandInProgress", True))
        if not bool(_com_value(app, "CommandInProgress")):
            raise RuntimeError("SOLIDWORKS did not enter CommandInProgress")
        yield
    except BaseException as error:
        operation_error = error
        raise
    finally:
        try:
            native_call("api-sequence", "SldWorks.CommandInProgress.restore",
                        lambda: setattr(app, "CommandInProgress", False))
            if bool(_com_value(app, "CommandInProgress")):
                raise RuntimeError("SOLIDWORKS CommandInProgress is still set")
        except Exception as error:
            raise NativeCommandRestoreFailed(error, operation_error) from error
