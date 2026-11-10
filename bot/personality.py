import random
from pathlib import Path
from typing import Any

import yaml


class Personality:
    def __init__(self, characters_dir: Path, rng: random.Random | None = None):
        self._rng = rng or random.Random()
        self._data: dict[str, dict[str, list[str]]] = {}
        for path in sorted(Path(characters_dir).glob("*.yaml")):
            self._data[path.stem] = yaml.safe_load(path.read_text(encoding="utf-8"))

    def names(self) -> list[str]:
        return sorted(self._data)

    def phrase(self, character: str, event: str, **placeholders: Any) -> str:
        variants = self._data.get(character, {}).get(event)
        if variants is None:
            variants = self._data["clean"][event]
        return self._rng.choice(variants).format(**placeholders)
