"""Contract for EnvironmentVariables, run against every implementation."""

from collections.abc import Callable, Mapping

import pytest

from codetaster.domain.domain_model.environment import VariableName, VariableValue
from codetaster.domain.secondary_ports.environment_variables import (
    EnvironmentVariables,
)
from codetaster.infrastructure.environment_variables.in_memory import (
    InMemoryEnvironmentVariables,
)
from codetaster.infrastructure.environment_variables.os_environment import (
    OsEnvironmentVariables,
)

type VariablesFactory = Callable[
    [Mapping[VariableName, VariableValue]], EnvironmentVariables
]


@pytest.fixture(params=["os", "in_memory"])
def build_variables(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> VariablesFactory:
    def build_os_variables(
        variables: Mapping[VariableName, VariableValue],
    ) -> EnvironmentVariables:
        for name, value in variables.items():
            monkeypatch.setenv(name.root, value.root)
        return OsEnvironmentVariables()

    return build_os_variables if request.param == "os" else InMemoryEnvironmentVariables


def test_returns_value_of_set_variable(build_variables: VariablesFactory) -> None:
    name = VariableName("CODETASTER_CONTRACT_TEST_SET")
    variables = build_variables({name: VariableValue("hello")})

    assert variables.value_of(name) == VariableValue("hello")


def test_unset_variable_is_none(build_variables: VariablesFactory) -> None:
    variables = build_variables({})

    assert variables.value_of(VariableName("CODETASTER_CONTRACT_TEST_UNSET")) is None


def test_empty_value_is_returned_as_is(build_variables: VariablesFactory) -> None:
    name = VariableName("CODETASTER_CONTRACT_TEST_EMPTY")
    variables = build_variables({name: VariableValue("")})

    assert variables.value_of(name) == VariableValue("")
