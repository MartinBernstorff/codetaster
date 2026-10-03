import os
from typing import override

from codetaster.domain.domain_model.environment import VariableName, VariableValue
from codetaster.domain.secondary_ports.environment_variables import (
    EnvironmentVariables,
)


class OsEnvironmentVariables(EnvironmentVariables):
    @override
    def value_of(self, name: VariableName) -> VariableValue | None:
        value = os.environ.get(name.root)
        return None if value is None else VariableValue(value)
