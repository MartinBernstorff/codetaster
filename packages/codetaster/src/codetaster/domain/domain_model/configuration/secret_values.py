from pydantic import BaseModel, ConfigDict, RootModel, SecretStr


class ApiToken(RootModel[SecretStr]):
    @staticmethod
    def fake() -> ApiToken:
        return ApiToken(SecretStr("fake-api-token"))


class Secrets(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    api_token: ApiToken | None = None

    @staticmethod
    def fake() -> Secrets:
        return Secrets(api_token=ApiToken.fake())
