from typing import Protocol

from codetaster.domain.domain_model.environment import VariableName, VariableValue


class EnvironmentVariables(Protocol):
    def value_of(self, name: VariableName) -> VariableValue | None:
        """The variable's value, or `None` if it is not set."""
        ...
