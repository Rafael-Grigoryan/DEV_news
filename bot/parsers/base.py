from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from bot.models import Entry

if TYPE_CHECKING:
    from bot.config import SourceConfig
    from bot.http import HttpClient


class Parser:
    """Базовый класс парсера источника.

    Контракт:
    - `fetch()` возвращает записи от новых к старым (порядок как в changelog'е);
    - `entry_id` стабилен между запусками, иначе дедупликация не сработает;
    - `enrich()` вызывается только для записей, которые реально пойдут в пост,
      поэтому дорогие запросы (например, текст статьи по ссылке) делаются там.
    """

    type: ClassVar[str]

    def __init__(self, source: SourceConfig, http: HttpClient):
        self.source = source
        self.http = http

    def fetch(self) -> list[Entry]:
        return self.parse(self.http.get_text(self.source.url))

    def parse(self, payload: str) -> list[Entry]:
        raise NotImplementedError

    def enrich(self, entry: Entry) -> Entry:
        return entry

    def make_entry(self, **kwargs) -> Entry:
        return Entry(source_id=self.source.id, **kwargs)
