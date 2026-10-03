from collections.abc import Mapping
from typing import override

from codetaster.domain.domain_model.environment import VariableName, VariableValue
from codetaster.domain.secondary_ports.environment_variables import (
    EnvironmentVariables,
)


class InMemoryEnvironmentVariables(EnvironmentVariables):
    def __init__(self, variables: Mapping[VariableName, VariableValue]) -> None:
        self._variables = dict(variables)

    @override
    def value_of(self, name: VariableName) -> VariableValue | None:
        return self._variables.get(name)
