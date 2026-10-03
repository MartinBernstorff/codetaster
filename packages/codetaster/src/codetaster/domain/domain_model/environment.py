from pydantic import ConfigDict, RootModel


class VariableName(RootModel[str]):
    model_config = ConfigDict(frozen=True)

    @staticmethod
    def fake() -> VariableName:
        return VariableName("CODETASTER_FAKE")


class VariableValue(RootModel[str]):
    @staticmethod
    def fake() -> VariableValue:
        return VariableValue("fake")

    def is_blank(self) -> bool:
        return self.root.strip() == ""
