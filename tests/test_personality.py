import random
from pathlib import Path

import pytest

from bot.personality import Personality

CHARACTERS = Path(__file__).parent.parent / "bot" / "characters"


@pytest.fixture(scope="module")
def personality():
    return Personality(CHARACTERS, rng=random.Random(42))


def test_names_contains_both(personality):
    assert set(personality.names()) == {"clean", "adult"}


def test_phrase_replaces_placeholders(personality):
    text = personality.phrase("clean", "pick", name="Олег", role="Олег")
    assert "{name}" not in text and "{role}" not in text
    assert "Олег" in text


def test_every_event_has_variants(personality):
    events = ["pick", "video_ok", "video_fail", "video_too_big", "video_too_long",
              "rating_header", "rating_empty", "help", "error"]
    for name in personality.names():
        for event in events:
            variants = personality._data[name][event]
            assert isinstance(variants, list) and len(variants) >= 1


def test_fallback_to_clean(personality):
    local = Personality(CHARACTERS, rng=random.Random(1))
    local._data["custom"] = {"pick": ["x {name}"]}
    text = local.phrase("custom", "help")
    assert isinstance(text, str) and text
    assert set(personality.names()) == {"clean", "adult"}


def test_missing_event_raises(personality):
    with pytest.raises(KeyError):
        personality.phrase("clean", "no_such_event")
