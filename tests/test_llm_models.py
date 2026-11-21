# Each AI feature runs on the model config.MODELS_BY_PROVIDER names for it.
from pathlib import Path

import pytest

from enclothed import config, llm


class Recorder(llm.Client):
    """A client whose messages.parse and messages.create remember the model they were asked for, then stop the call."""
    def __init__(self):
        super().__init__("anthropic", self)
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
    "insights": lambda c, photo: llm.InsightsChat(c, [], "how many coats?").next_turn(),
    "look": lambda c, photo: llm.tag_look(c, [photo]),
}


@pytest.mark.parametrize("feature", CALLS)
def test_each_feature_uses_its_configured_model(feature, photo, monkeypatch):
    monkeypatch.setitem(config.MODELS_BY_PROVIDER["anthropic"], feature, f"model-for-{feature}")
    client = Recorder()
    with pytest.raises(StopCall):
        CALLS[feature](client, photo)
    assert client.models == [f"model-for-{feature}"]


def test_weigh_shares_the_outfit_model_so_they_share_the_cached_wardrobe(monkeypatch):
    monkeypatch.setitem(config.MODELS_BY_PROVIDER["anthropic"], "outfits", "shared-model")
    client = Recorder()
    with pytest.raises(StopCall):
        llm.weigh_candidate(client, [{"type": "text", "text": "x"}])
    assert client.models == ["shared-model"]


def test_matching_a_look_shares_the_outfit_model_so_it_shares_the_cached_wardrobe(monkeypatch):
    monkeypatch.setitem(config.MODELS_BY_PROVIDER["anthropic"], "outfits", "shared-model")
    client = Recorder()
    with pytest.raises(StopCall):
        llm.match_look(client, [{"type": "text", "text": "x"}])
    assert client.models == ["shared-model"]


def test_every_provider_has_a_model_for_every_feature():
    for models in config.MODELS_BY_PROVIDER.values():
        assert set(models) == set(CALLS)


def test_every_anthropic_feature_has_a_claude_model():
    assert all(model.startswith("claude-") for model in config.MODELS_BY_PROVIDER["anthropic"].values())



class OpenAIRecorder(llm.Client):
    """The same, for OpenAI's responses.create."""
    def __init__(self):
        super().__init__("openai", self)
        self.models = []
        recorder = self
        class Responses:
            def create(self, **kwargs):
                recorder.models.append(kwargs["model"]); raise StopCall
        self.responses = Responses()


@pytest.mark.parametrize("feature", CALLS)
def test_each_feature_uses_its_configured_openai_model(feature, photo, monkeypatch):
    monkeypatch.setitem(config.MODELS_BY_PROVIDER["openai"], feature, f"model-for-{feature}")
    client = OpenAIRecorder()
    with pytest.raises(StopCall):
        CALLS[feature](client, photo)
    assert client.models == [f"model-for-{feature}"]

