# Changelog → Telegram

Бот раз в час проверяет официальные changelog'и, находит новые версии и записи, делает
краткую выжимку на русском через Gemini API и публикует пост в Telegram-канал.
Работает бесплатно на GitHub Actions по расписанию, свой сервер не нужен.

Пример поста:

```
⌨️ Claude Code 2.1.314

• Новая настройка `permissions.blockWritesOutsideWorkingDirectories` запрещает
  Write, Edit и NotebookEdit писать за пределами рабочих директорий
• В VS Code и вкладке Code в Claude Desktop появилось сжатие простаивающих диалогов
• `claude -p` при ошибке запуска теперь печатает ошибку и выходит с кодом 1
• ...

🔗 Полный changelog
#ClaudeCode
```

## Источники

Только официальные. Где у источника есть удобный машиночитаемый формат, бот берёт его, а не HTML.

| id | Что | Откуда | Тип парсера |
|---|---|---|---|
| `claude_code` | Claude Code | [`CHANGELOG.md`](https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md) в `anthropics/claude-code` | `markdown_changelog` |
| `claude_api` | Claude API, SDK, Console | [Release notes платформы](https://platform.claude.com/docs/en/release-notes/overview), markdown-версия `.../overview.md` | `markdown_changelog` (по датам) |
| `claude_apps` | Приложения Claude | [Release notes в Help Center](https://support.claude.com/en/articles/12138966-release-notes) | `html_release_notes` |
| `flutter` | Flutter stable | [официальный JSON релизов](https://storage.googleapis.com/flutter_infra_release/releases/releases_linux.json) + [`CHANGELOG.md`](https://github.com/flutter/flutter/blob/master/CHANGELOG.md) + пост в [блоге flutter.dev](https://flutter.dev/blog) для x.y.0 | `flutter_releases` |
| `dart` | Dart SDK stable | [`CHANGELOG.md`](https://github.com/dart-lang/sdk/blob/stable/CHANGELOG.md) на ветке `stable` | `markdown_changelog` |

Почему так:

- **Flutter не через GitHub Releases.** В `flutter/flutter` больше не публикуют релизы на
  GitHub: последняя запись там — бета от января 2024. Список версий бот берёт из того же
  JSON, которым пользуется `flutter upgrade`, а текст — из секции `### [x.y.z]` в
  CHANGELOG. Версия публикуется только после того, как появилась в JSON, поэтому записи,
  добавленные в CHANGELOG заранее, раньше релиза не утекут. Для мажорных релизов (x.y.0)
  в CHANGELOG одна строка со ссылкой на пост в блоге, поэтому бот подтягивает текст этого
  поста. Парсер `github_releases` всё равно есть: он пригодится для других репозиториев.
- **Dart — ветка `stable`, а не `main`.** На `main` нет патч-релизов (например, 3.13.4–3.13.7),
  зато есть незарелизенные секции (`Released on: Unreleased`). Такие секции и версии
  с суффиксом (`-dev`, `-wip`) бот пропускает в любом случае.

## Как это работает

1. GitHub Actions запускает `python -m bot` каждый час в :17.
2. Для каждого включённого источника парсер скачивает данные и отдаёт последние 30 записей
   (`max_entries`).
3. Записи сравниваются с `state.json`: там для каждого источника лежат уже опубликованные ID
   (версии, даты или теги; хранятся последние 200).
4. **Первый запуск источника** ничего не публикует, а только запоминает текущие записи.
   Иначе в канал вывалилась бы вся история. Флаг `publish_latest_on_init: true` дополнительно
   публикует самую свежую запись.
5. Новые записи публикуются от старых к новым, не больше `max_posts_per_run` (по умолчанию 5)
   от источника за запуск. Остальные уходят в следующие запуски.
6. Gemini делает выжимку: 3–7 пунктов на русском, термины и код остаются на английском.
   Если ключа нет, квота кончилась или API недоступен, бот публикует обрезанный оригинал
   с пометкой «Автоперевод недоступен». Запись при этом не теряется.
7. Запись помечается опубликованной только после успешной отправки в Telegram. Если
   отправка упала, она повторится в следующем запуске.
8. Workflow коммитит `state.json` обратно в репозиторий, только если файл изменился.

Ошибка одного источника не мешает остальным: она попадает в лог и в аннотации запуска.
Запуск помечается красным, только если не ответил ни один источник или Telegram
отклонил пост.

## Настройка

### 1. Репозиторий

Создайте **публичный** репозиторий на GitHub и запушьте в него этот проект. Для публичных
репозиториев минуты Actions бесплатны без лимита. Про приватные см. раздел
[«Лимиты»](#лимиты-и-расход).

### 2. Бот в @BotFather

1. Откройте [@BotFather](https://t.me/BotFather) и отправьте `/newbot`.
2. Задайте имя и username (должен заканчиваться на `bot`).
3. Сохраните токен вида `123456789:AAH...`: это `TELEGRAM_BOT_TOKEN`.

### 3. Бот — администратор канала

1. Откройте канал → **Управление каналом** → **Администраторы** → **Добавить администратора**.
2. Найдите бота по username и оставьте ему право **«Публикация сообщений»**. Остальные
   права не нужны.
3. `TELEGRAM_CHAT_ID`:
   - для публичного канала — его `@username`, например `@my_dev_news`;
   - для приватного — числовой id вида `-1001234567890`. Чтобы его узнать, опубликуйте в
     канале любое сообщение и откройте
     `https://api.telegram.org/bot<ТОКЕН>/getUpdates`: id будет в поле `channel_post.chat.id`.

### 4. Ключ Gemini

1. Откройте [Google AI Studio → API keys](https://aistudio.google.com/apikey) и войдите
   Google-аккаунтом.
2. Нажмите **Create API key** и сохраните ключ: это `GEMINI_API_KEY`.

Бесплатного тарифа хватает с запасом: один запрос на запись, обычно 0–3 записи в час.
Лимиты своего проекта можно посмотреть в AI Studio на странице Rate limits. На free tier
Google может использовать запросы для улучшения своих моделей; здесь это публичные
changelog'и, так что это не страшно.

Модели перебираются по цепочке. По умолчанию это `gemini-3.6-flash` → `gemini-3.5-flash-lite`.
Если модель не ответила за 60 секунд, перегружена (503), исчерпала квоту или ответила
не на русском, та же запись уходит следующей модели. Зависшая или перегруженная модель
пропускается до конца прогона.

Почему не самая новая `gemini-3.8-flash`: при проверке 30.10.2026 она и `gemini-3.7-flash`
на free tier не отвечали даже на короткие запросы (таймауты и «high demand»), а 3.6-flash
отвечала за секунды. `gemini-3.5-flash-lite` самая быстрая, но на длинных записях иногда
отвечает по-английски, поэтому она запасная. Свою цепочку можно задать переменной
`GEMINI_MODEL` через запятую, например `gemini-3.8-flash,gemini-3.6-flash,gemini-3.5-flash-lite`.

### 5. Секреты репозитория

**Settings → Secrets and variables → Actions → вкладка Secrets → New repository secret:**

| Имя | Значение |
|---|---|
| `TELEGRAM_BOT_TOKEN` | токен из шага 2 |
| `TELEGRAM_CHAT_ID` | `@username` или `-100…` из шага 3 |
| `GEMINI_API_KEY` | ключ из шага 4 |

Цепочка моделей (необязательно): вкладка **Variables** → `GEMINI_MODEL`, например
`gemini-3.8-flash,gemini-3.6-flash`.

`GITHUB_TOKEN` создавать не нужно: Actions выдаёт его сам. Права на коммит `state.json`
workflow запрашивает в своём блоке `permissions`. Если push всё-таки падает с 403,
проверьте **Settings → Actions → General → Workflow permissions**: настройки организации
могут запрещать запись.

### 6. Первый запуск в dry-run

**Actions → Check changelogs → Run workflow**:

- `dry_run` — отмечено (по умолчанию);
- `preview_latest` — `1`.

В логе шага *Check sources and publish* появится по одному посту на источник в том виде,
в котором они уйдут в Telegram. В Telegram ничего не отправляется, `state.json` не меняется.
Так можно проверить, что все источники доступны из Actions и Gemini отвечает.

### 7. Боевой запуск

Снова **Run workflow**, но со снятым `dry_run`. Первый боевой запуск ничего не публикует:
он запоминает текущие записи всех источников и коммитит `state.json`
(`chore(state): update published entries`). Дальше бот работает сам каждый час и
публикует только то, что появится после этого момента.

Чтобы сразу увидеть пост в канале, перед первым боевым запуском поставьте у нужного
источника `publish_latest_on_init: true`.

## Локальный запуск

Нужен Python 3.12+.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env        # впишите GEMINI_API_KEY (Telegram для dry-run не нужен)

python -m bot --dry-run --preview-latest 1    # по одному свежему посту от каждого источника
python -m bot --dry-run --only flutter,dart   # обычная проверка новых записей, только эти источники
pytest                                        # тесты
```

Флаги `python -m bot`:

| Флаг | Что делает |
|---|---|
| `--dry-run` | печатает посты в stdout, ничего не отправляет и не меняет `state.json` |
| `--preview-latest N` | только с `--dry-run`: показать N последних записей каждого источника как посты, даже если они уже опубликованы |
| `--only id1,id2` | проверить только эти источники; так можно проверить и отключённый (`enabled: false`) |
| `--config`, `--state` | другие пути к `sources.yaml` и `state.json` |
| `-v` | подробный лог |

Без `--dry-run` локальный запуск по-настоящему публикует и меняет локальный `state.json`.
Источник правды — `state.json` в репозитории, который коммитит workflow. Поэтому не
коммитьте локальный state поверх него.

## Настройки `sources.yaml`

Блок `settings`:

| Ключ | По умолчанию | Смысл |
|---|---|---|
| `max_entries` | 30 | сколько последних записей источника рассматривать |
| `max_posts_per_run` | 5 | максимум постов от одного источника за запуск |
| `state_keep` | 200 | сколько ID хранить на источник; должно быть больше `max_entries` |
| `post_delay_seconds` | 3 | пауза между постами |
| `disable_web_page_preview` | true | отключить превью ссылок в постах |
| `fallback_max_chars` | 1500 | сколько оригинального текста класть в пост без Gemini |
| `link_text` | Полный changelog | текст ссылки в конце поста |

`max_entries`, `max_posts_per_run` и `link_text` можно переопределить у конкретного источника.

Зачем окно `max_entries` меньше `state_keep`: в changelog'е Claude Code сотни версий.
Если бы бот смотрел на все, то версии, вытесненные из хвоста state, снова выглядели бы
новыми и попадали бы в канал повторно.

## Как добавить новый источник

### Тип парсера уже есть — только `sources.yaml`

Добавьте запись в `sources:` и закоммитьте. При первом запуске источник проинициализируется
без постов.

Пример: релизы Python SDK Anthropic с GitHub.

```yaml
  - id: anthropic_python_sdk
    name: Anthropic Python SDK
    emoji: "🐍"
    hashtag: "#AnthropicSDK"
    type: github_releases
    url: https://api.github.com/repos/anthropics/anthropic-sdk-python/releases?per_page=30
    include_prereleases: false
    enabled: true
```

Пример: только релизные посты из официального блога Flutter (Atom).

```yaml
  - id: flutter_blog_releases
    name: Flutter Blog
    emoji: "📰"
    hashtag: "#Flutter"
    type: rss
    url: https://flutter.dev/blog/feed.xml
    title_regex: "^What.s new in Flutter"
    enabled: true
```

Перед коммитом проверьте источник локально:

```bash
python -m bot --dry-run --preview-latest 2 --only anthropic_python_sdk
```

Параметры типов:

| `type` | Для чего | Параметры |
|---|---|---|
| `markdown_changelog` | markdown с секциями по версиям или датам | `heading_level` (2 для `##`), `id_kind` (`version`/`date`), `link_template` (`...#{anchor}`), `skip_unreleased` |
| `html_release_notes` | HTML-страница с записями под заголовками-датами | `container_selector` (`article`), `entry_heading` (`h3`), `stop_at` (`[h1, h2, h3]`) |
| `flutter_releases` | релизы Flutter | `changelog_url`, `enrich_from_blog`, `blog_max_chars`, `blog_content_selector`, шаблоны ссылок |
| `github_releases` | GitHub Releases API | `title_from` (`tag`/`name`) |
| `rss` | RSS 2.0 и Atom | `title_regex`, `title_prefix` |

Общие для всех: `id`, `name`, `emoji`, `hashtag`, `type`, `url`, `enabled`,
`include_prereleases`, `publish_latest_on_init`. Подробности — в начале файла каждого
парсера в `bot/parsers/`.

### Нужен новый тип — один файл и одна строка

1. Создайте `bot/parsers/my_type.py`:

   ```python
   from bot.models import Entry
   from bot.parsers.base import Parser


   class MyTypeParser(Parser):
       type = "my_type"

       def parse(self, payload: str) -> list[Entry]:
           # payload — содержимое self.source.url; если нужно несколько запросов,
           # переопределите fetch(). Записи возвращать от новых к старым.
           return [
               self.make_entry(
                   entry_id="1.2.3",                 # стабильный ключ
                   title=f"{self.source.name} 1.2.3",
                   raw_text="- Added ...",            # текст для выжимки
                   url="https://.../#1.2.3",
               )
           ]
   ```

   Параметры из `sources.yaml` доступны через `self.source.opt("key", default)`. Если для
   поста нужен дорогой дополнительный запрос (например, полная статья), делайте его
   в `enrich(entry)`: он вызывается только для записей, которые реально публикуются.

2. Зарегистрируйте класс в `bot/parsers/__init__.py`: добавьте импорт и класс в кортеж `PARSERS`.
3. Сохраните реальный фрагмент источника в `tests/fixtures/` и напишите тест по образцу
   `tests/test_markdown_changelog.py`.

## Лимиты и расход

- **Публичный репозиторий**: минуты GitHub Actions бесплатны и не ограничены.
- **Приватный репозиторий**: на бесплатном плане 2000 минут в месяц. Каждый запуск job
  округляется вверх до целой минуты. Обычный прогон занимает 20–40 секунд, то есть 1 минуту.
  Раз в час это 24 × 30 = **~720 минут в месяц (~36% лимита)**. Прогоны с несколькими
  постами и паузами Gemini могут занимать 2–3 минуты, поэтому закладывайте 750–800.
  Чтобы сэкономить, запускайте раз в 2 часа (`17 */2 * * *`), это примерно 360 минут.
- **Расписание GitHub неточное**: под нагрузкой запуск может опоздать на 5–30 минут,
  изредка запуск пропускается. Для новостного канала это не критично.
- **Telegram**: в канал не больше ~20 сообщений в минуту. Бот делает паузу между постами
  и выполняет `retry_after` при ответе 429.
- **Gemini free tier**: бот ставит паузу не меньше 4 секунд между запросами. На 429/5xx
  он один раз повторяет запрос к той же модели, а после этого, при таймауте или исчерпанной
  квоте переходит к следующей модели цепочки. Посты идут с оригиналом, если все модели
  недоступны или если запросы и паузы Gemini за прогон заняли больше 5 минут (job ограничена
  10 минутами).

## Защита от отключения через 60 дней

В публичном репозитории GitHub отключает `schedule`, если 60 дней не было активности.
Здесь от этого две защиты:

1. Коммиты `state.json` с каждой новой записью: Claude Code выходит почти каждый день.
2. Шаг **Keepalive** в конце каждого запланированного запуска вызывает
   `PUT /repos/{owner}/{repo}/actions/workflows/check.yml/enable`. Повторное включение
   workflow сбрасывает счётчик неактивности без фиктивных коммитов (так же работает
   [gh-workflow-keepalive](https://github.com/liskin/gh-workflow-keepalive)). Для этого
   в `permissions` есть `actions: write`.

Если workflow всё-таки отключился, на вкладке Actions появится кнопка **Enable workflow**.

## Структура

```
.github/workflows/check.yml   расписание, dry-run, коммит state, keepalive
bot/__main__.py               CLI и итоговый отчёт
bot/runner.py                 один прогон: опрос, дедупликация, лимиты, публикация
bot/parsers/                  парсеры источников + реестр в __init__.py
bot/summarizer.py             Gemini (Interactions API) и фоллбэк на оригинал
bot/formatter.py              Telegram HTML, экранирование, обрезка до 4096
bot/telegram.py               sendMessage, 429/retry_after
bot/state.py                  state.json
sources.yaml                  список источников
state.json                    опубликованные записи (коммитится workflow)
tests/                        pytest + реальные фрагменты источников в fixtures/
```

## Ограничения и диагностика

- **Записи по датам** (Claude API, Claude Apps) идентифицируются датой. Если Anthropic
  допишет пункт в уже опубликованную дату, отдельного поста не будет.
- **Claude Apps парсится из HTML.** Если Help Center сменит вёрстку и парсер не найдёт ни
  одной записи, источник отметится ошибкой в логе (остальные продолжат работать). Чинится
  параметрами `container_selector` / `entry_heading` или правкой парсера.
- **«Автоперевод недоступен» в постах.** Проверьте секрет `GEMINI_API_KEY` и `GEMINI_MODEL`.
  Причина, по каждой модели цепочки, есть в предупреждениях запуска (аннотации на странице run).
- **`403 Forbidden: bot is not a member of the channel chat`.** Бот не добавлен администратором
  или нет права на публикацию.
- **`400 Bad Request: chat not found`.** Неверный `TELEGRAM_CHAT_ID`; для приватного канала
  нужен числовой id с `-100`.
- **Переопубликовать запись:** удалите её ID из `state.json` и закоммитьте.
- **Сбросить источник:** удалите его ключ из `state.json`. Следующий запуск проинициализирует
  его заново, без постов.
