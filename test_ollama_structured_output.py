from pydantic import BaseModel, Field

from config.llm import create_llm
from config.settings import settings


class LocalModelTest(BaseModel):
    status: str = Field(
        description="Return the word ready."
    )

    items: list[str] = Field(
        description=(
            "Return exactly two items: "
            "intent and reporting."
        ),
        min_length=2,
        max_length=2,
    )


def main() -> None:
    print(
        f"Provider: {settings.llm_provider}"
    )

    print(
        f"Model: {settings.ollama_model}"
    )

    llm = create_llm()

    structured_llm = (
        llm.with_structured_output(
            LocalModelTest,
            method="json_schema",
        )
    )

    result = structured_llm.invoke(
        (
            "Return status as ready and exactly "
            "two items: intent and reporting."
        )
    )

    if not isinstance(
        result,
        LocalModelTest,
    ):
        result = LocalModelTest.model_validate(
            result
        )

    print(
        result.model_dump_json(
            indent=2
        )
    )


if __name__ == "__main__":
    main()