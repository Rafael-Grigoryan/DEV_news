"""Выжимка записи на русском через Gemini (Interactions API) с фоллбэком на оригинал.

Модели перебираются по цепочке (GEMINI_MODEL="a,b,c"): если модель зависла, перегружена,
исчерпала квоту или ответила не на русском, та же запись уходит следующей. Зависшая
или перегруженная модель пропускается до конца прогона.

`summarize()` никогда не бросает исключений: если ключа нет, все модели недоступны
или кончился бюджет времени, возвращается обрезанный английский оригинал, и запись
всё равно публикуется.
"""

from __future__ import annotations

import logging
import random
import re
import time

import requests

from bot.config import SourceConfig
from bot.models import Entry, Summary

log = logging.getLogger(__name__)

API_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
# Проверено 30.10.2026 на free tier: gemini-3.8-flash и 3.7-flash не отвечали за 90 с
# (high demand), 3.6-flash отвечала за секунды. flash-lite быстрая, но на длинных
# записях хуже держит русский язык, поэтому она запасная.
DEFAULT_MODELS = ("gemini-3.6-flash", "gemini-3.5-flash-lite")
THINKING_LEVEL = "low"  # для выжимки рассуждения почти не нужны, а время ответа растёт
MAX_INPUT_CHARS = 30_000
MAX_ITEMS = 10
RETRY_STATUSES = {429, 500, 502, 503, 504}
MAX_RETRY_DELAY = 60.0  # дольше ждать не имеет смысла: скорее всего, кончилась дневная квота
REQUEST_TIMEOUT = 60.0
# Сколько секунд за прогон можно потратить на Gemini (запросы + паузы). Остальное время
# workflow (timeout-minutes: 10) остаётся на загрузку источников и Telegram.
DEFAULT_TIME_BUDGET = 300.0
MIN_REQUEST_TIME = 15.0  # меньше этого остатка бюджета новый запрос не начинаем

SYSTEM_PROMPT = """\
Ты — редактор русскоязычного Telegram-канала о новостях инструментов разработки.
По тексту записи из официального changelog сделай краткую выжимку на русском языке.

Правила:
- 3–7 пунктов о самом важном: новые возможности, важные исправления, breaking changes.
  Мелкие исправления объединяй или опускай.
- Если в записи всего 1–2 изменения, просто аккуратно переведи их, не раздувая текст.
- Ничего не выдумывай: только факты из текста, без оценок, советов и выводов.
- Названия продуктов, моделей, API, эндпоинтов, флагов, команд, параметров, файлов
  и любой код оставляй на английском и оборачивай в обратные кавычки:
  `--dry-run`, `GET /v1/models`, `flutter build`.
- Breaking changes начинай словом «Breaking:».
- Каждый пункт — одно-два коротких предложения.
- Формат ответа: только список, каждый пункт на новой строке и начинается с «- ».
  Без заголовков, вступлений, заключений, ссылок, эмодзи, HTML и markdown,
  кроме обратных кавычек.
"""

_BULLET_RE = re.compile(r"^\s*(?:[-*+•–—]|\d+[.)])\s+")
_LINK_DEF_RE = re.compile(r"^\s*\[[^\]]+\]:\s*\S+")
_TAG_LINE_RE = re.compile(r"^\s*</?[A-Za-z][^>]*>\s*$|^\s*<!--.*-->\s*$")
_MD_LINK_RE = re.compile(r"!?\[([^\]]*)\](?:\([^)]*\)|\[[^\]]*\])")
_HEADING_RE = re.compile(r"^#{1,6}\s+")
_CODE_SPAN_RE = re.compile(r"`[^`]*`")
_CYRILLIC_RE = re.compile(r"[а-яё]", re.I)
_LATIN_RE = re.compile(r"[a-z]", re.I)


class GeminiError(Exception):
    """Gemini не годится до конца прогона: ключ отклонён или кончился бюджет времени."""


class ModelUnavailable(GeminiError):
    """Эта модель сейчас не отвечает (таймаут, 5xx, квота, не найдена): пробуем следующую."""


def parse_models(value: str | list[str] | None) -> list[str]:
    if isinstance(value, str):
        value = value.split(",")
    models = [m.strip() for m in value or [] if m.strip()]
    return models or list(DEFAULT_MODELS)


class GeminiSummarizer:
    def __init__(
        self,
        api_key: str | None,
        models: str | list[str] | None = None,
        *,
        fallback_max_chars: int = 1500,
        min_interval: float = 4.0,  # free tier: ~10–15 RPM на flash-модели
        max_retries: int = 1,  # повторов одной модели на 5xx/429 до перехода к следующей
        timeout: float = REQUEST_TIMEOUT,
        time_budget: float = DEFAULT_TIME_BUDGET,
        session: requests.Session | None = None,
        sleep=time.sleep,
        clock=time.monotonic,
    ):
        self.api_key = api_key or None
        self.models = parse_models(models)
        self.fallback_max_chars = fallback_max_chars
        self.min_interval = min_interval
        self.max_retries = max_retries
        self.timeout = timeout
        self.time_budget = time_budget
        self.session = session or requests.Session()
        self._sleep = sleep
        self._clock = clock
        self._spent = 0.0  # секунды на запросы и паузы Gemini за этот прогон
        self._unavailable: set[str] = set()  # модели, пропускаемые до конца прогона
        self._no_thinking: set[str] = set()  # модели, не принимающие THINKING_LEVEL
        self._last_request: float | None = None
        self._disabled_reason: str | None = None if self.api_key else "GEMINI_API_KEY не задан"
        self._reported = False

    def summarize(self, entry: Entry, source: SourceConfig) -> Summary:
        if self._disabled_reason:
            if not self._reported:
                log.warning("Gemini отключён (%s): посты пойдут с оригинальным текстом", self._disabled_reason)
                self._reported = True
            return fallback_summary(entry, self.fallback_max_chars)
        problems: list[str] = []
        try:
            prompt = build_input(entry, source)
            for model in self.models:
                if model in self._unavailable:
                    continue
                try:
                    items = parse_items(self._generate(model, prompt))
                except ModelUnavailable as exc:
                    self._unavailable.add(model)
                    log.warning("Gemini %s пропускается до конца прогона: %s", model, exc)
                    problems.append(f"{model}: {exc}")
                    continue
                if items and is_russian(items):
                    if problems:
                        log.info("Выжимку для %s сделала %s", entry.title, model)
                    return Summary(items=items, translated=True)
                problem = "ответ не на русском" if items else "пустой ответ"
                log.info("Gemini %s: %s для %s", model, problem, entry.title)
                problems.append(f"{model}: {problem}")
            if all(model in self._unavailable for model in self.models):
                self._disabled_reason = "все модели недоступны"
                self._reported = True  # причины уже в логе выше
        except Exception as exc:  # noqa: BLE001 — любая проблема с Gemini не должна терять запись
            problems.append(str(exc) or type(exc).__name__)
        log.warning("Gemini не сделал выжимку для %s (%s), публикую оригинал",
                    entry.title, "; ".join(problems) or "все модели недоступны")
        return fallback_summary(entry, self.fallback_max_chars)

    def _generate(self, model: str, prompt: str) -> str:
        body = {
            "model": model,
            "system_instruction": SYSTEM_PROMPT,
            "input": prompt,
            "generation_config": {"max_output_tokens": 4096},
            "store": False,
        }
        if model not in self._no_thinking:
            body["generation_config"]["thinking_level"] = THINKING_LEVEL
        headers = {"x-goog-api-key": self.api_key, "Content-Type": "application/json"}
        retries = 0
        while True:
            self._throttle()
            remaining = self.time_budget - self._spent
            if remaining < MIN_REQUEST_TIME:
                # Без бюджета зависшие запросы съели бы весь timeout-minutes workflow.
                self._disabled_reason = f"исчерпан бюджет {self.time_budget:.0f} с на Gemini за прогон"
                raise GeminiError(self._disabled_reason)
            timeout = min(self.timeout, remaining)
            started = self._clock()
            try:
                resp = self.session.post(API_URL, json=body, headers=headers, timeout=timeout)
            except requests.Timeout as exc:
                raise ModelUnavailable(f"нет ответа за {timeout:.0f} с") from exc
            except requests.RequestException as exc:
                error, delay = f"сетевая ошибка {type(exc).__name__}", _backoff(retries)
            else:
                if resp.status_code == 200:
                    try:
                        return extract_text(resp.json())
                    except (ValueError, AttributeError, TypeError) as exc:
                        raise ModelUnavailable(f"неожиданный ответ: {exc}") from exc
                error = f"HTTP {resp.status_code}: {_error_message(resp)}"
                config = body["generation_config"]
                if resp.status_code == 400 and "thinking" in error.lower() and "thinking_level" in config:
                    log.info("Gemini %s не принимает thinking_level=%s, повторяю без него",
                             model, config.pop("thinking_level"))
                    self._no_thinking.add(model)
                    continue
                if resp.status_code == 401 or "api key" in error.lower():
                    self._disabled_reason = error  # ключ не подходит ни к одной модели
                    raise GeminiError(error)
                if resp.status_code not in RETRY_STATUSES:
                    raise ModelUnavailable(error)  # 404 — модели нет, 400/403 — не для этого ключа
                delay = _retry_delay(resp) or _backoff(retries)
                if delay > MAX_RETRY_DELAY:
                    raise ModelUnavailable(f"{error} (квота исчерпана)")
            finally:
                self._spent += self._clock() - started
            if retries >= self.max_retries:
                raise ModelUnavailable(error)
            retries += 1
            log.info("Gemini %s: %s, повтор через %.0f с", model, error, delay)
            self._wait(delay)

    def _throttle(self) -> None:
        if self._last_request is not None:
            self._wait(self.min_interval - (self._clock() - self._last_request))
        self._last_request = self._clock()

    def _wait(self, seconds: float) -> None:
        if seconds > 0:
            self._sleep(seconds)
            self._spent += seconds


def build_input(entry: Entry, source: SourceConfig) -> str:
    text = entry.raw_text
    if len(text) > MAX_INPUT_CHARS:
        text = text[:MAX_INPUT_CHARS] + "\n[...]"
    # Напоминание после текста: на длинных английских входах модели забывают про язык.
    return (
        f"Продукт: {source.name}\nЗапись: {entry.title}\n\nТекст записи:\n{text}\n\n"
        "Сделай выжимку этой записи по правилам. Ответ — только список пунктов на русском языке."
    )


def extract_text(data: dict) -> str:
    """Текст ответа Interactions API: steps[type=model_output].content[type=text].text."""
    status = data.get("status")
    if status and status != "completed":
        raise GeminiError(f"статус ответа {status}")
    texts = [
        part.get("text", "")
        for step in data.get("steps") or []
        if step.get("type", "model_output") == "model_output"
        for part in step.get("content") or []
        if part.get("type") == "text"
    ]
    if not any(texts):  # на случай другой формы ответа
        texts = [o.get("text", "") for o in data.get("outputs") or [] if o.get("type") == "text"]
    if not any(texts) and isinstance(data.get("output_text"), str):
        texts = [data["output_text"]]
    text = "\n".join(t for t in texts if t).strip()
    if not text:
        raise GeminiError("в ответе нет текста")
    return text


def parse_items(text: str) -> list[str]:
    """Ответ модели -> пункты. Вступление перед списком выбрасывается, переносы склеиваются."""
    lines = [line.strip() for line in text.splitlines() if line.strip() and line.strip() != "```"]
    has_bullets = any(_BULLET_RE.match(line) for line in lines)
    items: list[str] = []
    for line in lines:
        if _BULLET_RE.match(line):
            items.append(_BULLET_RE.sub("", line, count=1).strip())
        elif has_bullets and items:
            items[-1] += " " + line
        elif not has_bullets:
            items.append(_HEADING_RE.sub("", line))
    return [item for item in items if item][:MAX_ITEMS]


def is_russian(items: list[str]) -> bool:
    """Достаточно ли кириллицы вне `кода`: названия и термины на английском допустимы."""
    text = _CODE_SPAN_RE.sub("", " ".join(items))
    cyrillic = len(_CYRILLIC_RE.findall(text))
    latin = len(_LATIN_RE.findall(text))
    return cyrillic > 0 and cyrillic >= 0.4 * (cyrillic + latin)


def markdown_to_items(text: str) -> list[str]:
    """Markdown changelog'а -> пункты для фоллбэка: без кода, ссылок-сносок и тегов."""
    # Ссылки-сноски вида "(issue [#64696])" с определением "[#64696]: https://..." ниже.
    ref_labels = {m[1] for m in re.finditer(r"^\s*\[([^\]]+)\]:\s*\S+", text, re.M)}
    shortcut_ref = re.compile(r"\[(" + "|".join(map(re.escape, ref_labels)) + r")\]") if ref_labels else None
    items: list[str] = []
    current: int | None = None
    in_fence = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith(("```", "~~~")):
            in_fence, current = not in_fence, None
            continue
        if in_fence:
            continue
        if not line or line == "---" or _LINK_DEF_RE.match(line) or _TAG_LINE_RE.match(line):
            current = None
            continue
        line = _MD_LINK_RE.sub(r"\1", line)
        if shortcut_ref:
            line = shortcut_ref.sub(r"\1", line)
        if _HEADING_RE.match(line):
            items.append(_HEADING_RE.sub("", line))
            current = None
        elif m := _BULLET_RE.match(line):
            items.append(line[m.end() :])
            current = len(items) - 1
        elif current is not None:
            items[current] += " " + line  # перенос строки внутри пункта
        else:
            items.append(line)
            current = len(items) - 1
    return [item.strip() for item in items if item.strip()]


def fallback_summary(entry: Entry, max_chars: int) -> Summary:
    items: list[str] = []
    total = 0
    for item in markdown_to_items(entry.raw_text) or [entry.title]:
        if total + len(item) > max_chars:
            if not items:
                items.append(item[:max_chars].rsplit(" ", 1)[0] + "…")
            items.append("…")
            break
        items.append(item)
        total += len(item)
    return Summary(items=items, translated=False)


def _backoff(attempt: int) -> float:
    return min(MAX_RETRY_DELAY, 2.0 ** (attempt + 1)) + random.uniform(0, 1)


def _retry_delay(resp: requests.Response) -> float | None:
    if (header := resp.headers.get("Retry-After")) and header.replace(".", "", 1).isdigit():
        return float(header)
    try:
        details = resp.json().get("error", {}).get("details", [])
    except ValueError:
        return None
    for detail in details if isinstance(details, list) else []:
        if str(detail.get("@type", "")).endswith("RetryInfo"):
            if m := re.fullmatch(r"(\d+(?:\.\d+)?)s", str(detail.get("retryDelay", ""))):
                return float(m[1])
    return None


def _error_message(resp: requests.Response) -> str:
    try:
        error = resp.json().get("error", {})
        return str(error.get("message") or error.get("status") or "")[:200]
    except ValueError:
        return resp.text[:200]
