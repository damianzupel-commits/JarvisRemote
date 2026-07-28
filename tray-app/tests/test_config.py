import config


def test_available_models_are_the_three_project_tiers():
    assert [m["label"] for m in config.AVAILABLE_MODELS] == ["Lite", "Medio", "Hard"]
    assert [m["id"] for m in config.AVAILABLE_MODELS] == [
        "jarvis-text-lite",
        "jarvis-text-v2",
        "jarvis-text-hard",
    ]
