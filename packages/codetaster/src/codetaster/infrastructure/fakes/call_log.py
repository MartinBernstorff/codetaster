from enum import Enum, auto

from pydantic import RootModel


class RecordedCall(Enum):
    INSTALL_PINNED_TOOLS = auto()
    SYNC_DEPENDENCIES = auto()
    INSTALL_HOOKS = auto()


class CallLog(RootModel[list[RecordedCall]]):
    """Shared by the fakes, so a test can assert the order calls happened in."""

    def record(self, call: RecordedCall) -> None:
        self.root.append(call)

    @staticmethod
    def fake() -> CallLog:
        return CallLog([])
