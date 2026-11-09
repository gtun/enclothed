# Each AI feature runs on the model config.MODELS names for it.
from pathlib import Path

import pytest

from enclothed import config, llm


class Recorder:
    """A client whose messages.parse and messages.create remember the model they were asked for, then stop the call."""
    def __init__(self):
        self.models = []
        recorder = self
        class Messages:
            def parse(self, **kwargs):
                recorder.models.append(kwargs["model"]); raise StopCall
            def create(self, **kwargs):
                recorder.models.append(kwargs["model"]); raise StopCall
        self.messages = Messages()


class StopCall(Exception):
    pass


@pytest.fixture
def photo(tmp_path):
    path = tmp_path / "front.jpg"
    path.write_bytes(b"jpeg")
    return path


CALLS = {
    "tag": lambda c, photo: llm.tag_garment(c, [photo]),
    "mend": lambda c, photo: llm.fill_blanks(c, [photo], {"category": "top"}, ["hem"]),
    "outfits": lambda c, photo: llm.recommend_outfits(c, [{"type": "text", "text": "x"}]),
    "describe": lambda c, photo: llm.describe_outfit(c, [{"type": "text", "text": "x"}]),
    "preferences": lambda c, photo: llm.improve_preferences(c, "I like navy"),
    "insights": lambda c, photo: llm.insights_turn(c, [{"role": "user", "content": "how many coats?"}]),
}


@pytest.mark.parametrize("feature", CALLS)
def test_each_feature_uses_its_configured_model(feature, photo, monkeypatch):
    monkeypatch.setitem(config.MODELS, feature, f"model-for-{feature}")
    client = Recorder()
    with pytest.raises(StopCall):
        CALLS[feature](client, photo)
    assert client.models == [f"model-for-{feature}"]


def test_weigh_shares_the_outfit_model_so_they_share_the_cached_wardrobe(monkeypatch):
    monkeypatch.setitem(config.MODELS, "outfits", "shared-model")
    client = Recorder()
    with pytest.raises(StopCall):
        llm.weigh_candidate(client, [{"type": "text", "text": "x"}])
    assert client.models == ["shared-model"]


def test_every_feature_has_a_claude_model():
    assert set(config.MODELS) == set(CALLS)
    assert all(model.startswith("claude-") for model in config.MODELS.values())
