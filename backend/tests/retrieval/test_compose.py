"""Static checks of the deployment files R1 owns: LLM network isolation, the pinned Ollama image,
the default model kept in one place, the nginx stream settings, and documented settings."""

import re
from pathlib import Path
from typing import Any

import pytest

from sanad.llm.settings import DEFAULT_OLLAMA_MODEL, OLLAMA_BASE_MODEL, LlmSettings
from sanad.retrieval.settings import RetrievalSettings

REPO = Path(__file__).resolve().parents[3]


def load(name: str) -> dict[str, Any]:
    yaml = pytest.importorskip("yaml")  # a dev dependency
    data: dict[str, Any] = yaml.safe_load((REPO / name).read_text(encoding="utf-8"))
    return data


@pytest.fixture(scope="module")
def base() -> dict[str, Any]:
    return load("docker-compose.yml")


def default_of(value: str) -> str:
    """`${NAME:-default}` -> default."""
    match = re.fullmatch(r"\$\{\w+:-(.*)\}", value)
    assert match, value
    return match.group(1)


def test_ollama_and_api_have_no_route_out(base: dict[str, Any]) -> None:
    assert base["networks"]["backend"]["internal"] is True
    services = base["services"]
    assert services["ollama"]["networks"] == ["backend"]
    assert services["api"]["networks"] == ["backend"]
    assert "ollama" in services["api"]["depends_on"]


def test_ollama_init_is_egress_only_and_never_on_the_backend(base: dict[str, Any]) -> None:
    init = base["services"]["ollama-init"]
    assert init["networks"] == ["egress"]
    assert base["networks"]["egress"].get("internal") is not True
    assert init["restart"] == "no"


def test_ollama_image_is_pinned(base: dict[str, Any]) -> None:
    for name in ("ollama", "ollama-init"):
        image = base["services"][name]["image"]
        assert re.fullmatch(r"ollama/ollama:\d+\.\d+\.\d+", image), image


def test_default_model_is_the_same_everywhere(base: dict[str, Any]) -> None:
    env = base["services"]["ollama-init"]["environment"]
    assert default_of(env["LLM_MODEL"]) == DEFAULT_OLLAMA_MODEL
    assert default_of(env["OLLAMA_BASE_MODEL"]) == OLLAMA_BASE_MODEL
    assert default_of(env["OLLAMA_NUM_CTX"]) == str(LlmSettings().ollama_num_ctx)
    script = (REPO / "deploy" / "ollama-init.sh").read_text(encoding="utf-8")
    assert f"TEXT_MODEL={DEFAULT_OLLAMA_MODEL}\n" in script


def test_api_llm_override_is_the_only_way_out_for_api() -> None:
    override = load("docker-compose.api-llm.yml")
    api = override["services"]["api"]
    assert set(api["networks"]) == {"backend", "egress"}
    assert api["environment"]["LLM_PROVIDER"].startswith("${LLM_PROVIDER:?")
    dev = load("docker-compose.dev.yml")
    assert "ollama" not in dev["services"]


def test_nginx_does_not_buffer_the_answer_stream() -> None:
    conf = (REPO / "deploy" / "nginx.conf").read_text(encoding="utf-8")
    block = conf.split("location = /api/ask/stream {", 1)[1].split("}", 1)[0]
    for directive in ("proxy_buffering off;", "proxy_cache off;", "gzip off;"):
        assert directive in block
    timeout = re.search(r"proxy_read_timeout (\d+)s;", block)
    assert timeout and int(timeout.group(1)) > 60


@pytest.mark.parametrize("settings_class", [LlmSettings, RetrievalSettings])
def test_every_setting_is_in_env_example(settings_class: type[Any]) -> None:
    documented = (REPO / ".env.example").read_text(encoding="utf-8")
    missing = [
        name.upper()
        for name in settings_class.model_fields
        if not re.search(rf"^#? ?{name.upper()}=", documented, re.MULTILINE)
    ]
    assert missing == [], f".env.example lacks {missing}"
