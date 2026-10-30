from __future__ import annotations

import os
import re
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

import yaml


class ConfigError(Exception):
    pass


@dataclass
class Settings:
    """Общие настройки; любую из помеченных ниже можно переопределить в источнике."""

    max_entries: int = 30  # (*) сколько последних записей источника рассматривать
    max_posts_per_run: int = 5  # (*) максимум постов от одного источника за запуск
    link_text: str = "Полный changelog"  # (*) текст ссылки в посте
    state_keep: int = 200  # сколько ID хранить в state.json на источник
    post_delay_seconds: float = 3.0  # пауза между постами в Telegram
    disable_web_page_preview: bool = True
    fallback_max_chars: int = 1500  # длина оригинала в посте, если Gemini недоступен
    request_timeout: float = 30.0


# Настройки, которые источник может переопределить своим значением.
PER_SOURCE_SETTINGS = ("max_entries", "max_posts_per_run", "link_text")


@dataclass
class SourceConfig:
    id: str
    name: str
    type: str
    url: str
    max_entries: int
    max_posts_per_run: int
    link_text: str
    enabled: bool = True
    emoji: str = ""
    hashtag: str = ""
    include_prereleases: bool = False
    publish_latest_on_init: bool = False
    options: dict[str, Any] = field(default_factory=dict)  # параметры конкретного парсера

    def opt(self, key: str, default: Any = None) -> Any:
        return self.options.get(key, default)

    @classmethod
    def from_dict(cls, raw: dict[str, Any], settings: Settings) -> SourceConfig:
        if not isinstance(raw, dict):
            raise ConfigError(f"источник должен быть словарём, получено: {raw!r}")
        data = dict(raw)
        for key in ("id", "name", "type", "url"):
            if not data.get(key):
                raise ConfigError(f"у источника {raw.get('id', '?')!r} не задано поле {key!r}")
        if not re.fullmatch(r"[a-z0-9_]+", str(data["id"])):
            raise ConfigError(f"id источника {data['id']!r}: допустимы только a-z, 0-9 и _")
        for key in PER_SOURCE_SETTINGS:
            data.setdefault(key, getattr(settings, key))
        known = {f.name for f in fields(cls)} - {"options"}
        kwargs = {k: v for k, v in data.items() if k in known}
        kwargs["options"] = {k: v for k, v in data.items() if k not in known}
        source = cls(**kwargs)
        source.id, source.name, source.type, source.url = (
            str(source.id), str(source.name), str(source.type), str(source.url)
        )
        if source.max_entries < 1 or source.max_posts_per_run < 1:
            raise ConfigError(f"{source.id}: max_entries и max_posts_per_run должны быть >= 1")
        if source.max_entries >= settings.state_keep:
            # Иначе записи, вытесненные из state, снова окажутся «новыми».
            raise ConfigError(
                f"{source.id}: max_entries ({source.max_entries}) должен быть меньше "
                f"state_keep ({settings.state_keep})"
            )
        return source


@dataclass
class Config:
    settings: Settings
    sources: list[SourceConfig]


def load_config(path: str | Path) -> Config:
    from bot.parsers import PARSERS  # локальный импорт: parsers зависят от config

    path = Path(path)
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"не удалось прочитать {path}: {exc}") from exc

    settings_raw = raw.get("settings") or {}
    known_settings = {f.name for f in fields(Settings)}
    unknown = set(settings_raw) - known_settings
    if unknown:
        raise ConfigError(f"неизвестные ключи в settings: {', '.join(sorted(unknown))}")
    settings = Settings(**settings_raw)

    sources = [SourceConfig.from_dict(item, settings) for item in raw.get("sources") or []]
    if not sources:
        raise ConfigError(f"в {path} нет ни одного источника")
    seen: set[str] = set()
    for source in sources:
        if source.id in seen:
            raise ConfigError(f"повторяющийся id источника: {source.id}")
        seen.add(source.id)
        if source.type not in PARSERS:
            raise ConfigError(
                f"{source.id}: неизвестный type {source.type!r}; доступны: {', '.join(sorted(PARSERS))}"
            )
    return Config(settings=settings, sources=sources)


def load_dotenv(path: str | Path) -> None:
    """Минимальный загрузчик .env: KEY=value, без перезаписи уже заданных переменных."""
    path = Path(path)
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :]
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        if key and not os.environ.get(key):
            os.environ[key] = value
