"""state.json: какие записи каждого источника уже опубликованы (или увидены при инициализации).

Формат:
  {"version": 1, "sources": {"claude_code": {"seen": ["2.1.311", "2.1.312", ...]}}}

Список `seen` идёт от старых к новым и обрезается до `keep` последних ID. В файле
нет меток времени, поэтому он меняется (и коммитится) только когда есть новые записи.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

STATE_VERSION = 1


class StateError(Exception):
    pass


class State:
    def __init__(self, path: str | Path, keep: int = 200):
        self.path = Path(path)
        self.keep = keep
        self._data = self._load()
        self._saved = self._dump()

    def _load(self) -> dict:
        if not self.path.exists():
            return {"version": STATE_VERSION, "sources": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8") or "{}")
        except (OSError, json.JSONDecodeError) as exc:
            # Не переинициализируем молча: так можно потерять неопубликованные записи.
            raise StateError(f"{self.path} повреждён: {exc}") from exc
        if not isinstance(data, dict) or not isinstance(data.get("sources", {}), dict):
            raise StateError(f"{self.path}: неожиданный формат")
        data.setdefault("version", STATE_VERSION)
        data.setdefault("sources", {})
        return data

    def _dump(self) -> str:
        return json.dumps(self._data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    def has_source(self, source_id: str) -> bool:
        return source_id in self._data["sources"]

    def seen_ids(self, source_id: str) -> set[str]:
        return set(self._seen_list(source_id))

    def _seen_list(self, source_id: str) -> list[str]:
        return self._data["sources"].setdefault(source_id, {}).setdefault("seen", [])

    def initialize(self, source_id: str, entry_ids_oldest_first: list[str]) -> None:
        """Первый запуск источника: запомнить текущие записи, ничего не публикуя."""
        self._data["sources"][source_id] = {"seen": []}
        for entry_id in entry_ids_oldest_first:
            self.mark_seen(source_id, entry_id)

    def mark_seen(self, source_id: str, entry_id: str) -> None:
        seen = self._seen_list(source_id)
        if entry_id in seen:
            seen.remove(entry_id)
        seen.append(entry_id)
        del seen[: max(0, len(seen) - self.keep)]

    def save(self) -> bool:
        """Атомарно записать файл, если что-то изменилось. Возвращает True, если записали."""
        text = self._dump()
        if text == self._saved:
            return False
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, self.path)
        self._saved = text
        return True
