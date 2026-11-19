from typing import Any

from config.llm import create_llm
from config.settings import settings


def extract_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts: list[str] = []

        for block in content:
            if isinstance(block, str):
                parts.append(block)

            elif isinstance(block, dict):
                text = block.get("text")

                if text:
                    parts.append(
                        str(text)
                    )

        return "\n".join(parts).strip()

    return str(content).strip()


def main() -> None:
    print(
        f"Provider: {settings.llm_provider}"
    )

    print(
        f"Model: {settings.ollama_model}"
    )

    llm = create_llm()

    print(
        "LLM class: "
        f"{llm.__class__.__module__}."
        f"{llm.__class__.__name__}"
    )

    response = llm.invoke(
        "Reply with exactly: CONNECTION_OK"
    )

    response_text = extract_text(
        response.content
    )

    print(f"Response: {response_text}")

    if "CONNECTION_OK" not in response_text:
        raise RuntimeError(
            "Expected CONNECTION_OK was not returned."
        )


if __name__ == "__main__":
    main()