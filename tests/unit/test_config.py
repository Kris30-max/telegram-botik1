from pathlib import Path

import pytest
from pydantic import ValidationError

from bot.config import Settings

BASE = {
    "BOT_TOKEN": "123:abc",
    "ANTHROPIC_API_KEY": "sk-test",
    "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
    "ALLOWED_USER_IDS": "111",
}


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    for key, value in BASE.items():
        monkeypatch.setenv(key, value)
    return monkeypatch


def make() -> Settings:
    return Settings(_env_file=None)  # type: ignore[call-arg]


def test_defaults(env: pytest.MonkeyPatch) -> None:
    settings = make()
    assert settings.llm_model == "claude-opus-5-5"
    assert settings.ask_daily_limit == 30


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("111", {111}), ("111, 222", {111, 222}), ("111,222,", {111, 222})],
)
def test_allowed_user_ids_parsing(env: pytest.MonkeyPatch, raw: str, expected: set[int]) -> None:
    env.setenv("ALLOWED_USER_IDS", raw)
    assert make().allowed_user_ids == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("postgresql://u:p@h:5432/db", "postgresql+asyncpg://u:p@h:5432/db"),
        ("postgres://u:p@h/db", "postgresql+asyncpg://u:p@h/db"),
        ("postgresql+asyncpg://u:p@h/db", "postgresql+asyncpg://u:p@h/db"),
        ("sqlite+aiosqlite:///./dev.db", "sqlite+aiosqlite:///./dev.db"),
    ],
)
def test_database_url_normalized(env: pytest.MonkeyPatch, raw: str, expected: str) -> None:
    env.setenv("DATABASE_URL", raw)
    assert make().database_url == expected


@pytest.mark.parametrize("missing", ["BOT_TOKEN", "ANTHROPIC_API_KEY", "ALLOWED_USER_IDS"])
def test_required_vars(env: pytest.MonkeyPatch, missing: str) -> None:
    env.delenv(missing)
    with pytest.raises(ValidationError):
        make()


def test_empty_required_var_rejected(env: pytest.MonkeyPatch) -> None:
    env.setenv("BOT_TOKEN", "")
    with pytest.raises(ValidationError):
        make()


def test_load_settings_exits_with_missing_names(env: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from bot import config

    env.delenv("BOT_TOKEN")
    env.setenv("ALLOWED_USER_IDS", "not-a-number")
    env.chdir(tmp_path)
    config.get_settings.cache_clear()
    with pytest.raises(SystemExit) as exc_info:
        config.load_settings()
    config.get_settings.cache_clear()
    message = str(exc_info.value.code)
    assert "BOT_TOKEN" in message
    assert "ALLOWED_USER_IDS" in message
    assert "sk-test" not in message
