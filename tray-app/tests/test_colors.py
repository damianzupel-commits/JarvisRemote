from ui.colors import color_for_severity


def test_color_for_severity_known_tiers():
    assert color_for_severity("critical") == "#ef4444"
    assert color_for_severity("high") == "#f97316"
    assert color_for_severity("medium") == "#eab308"


def test_color_for_severity_none_for_low_info_and_unscanned():
    # "low"/"info" y `None` (sin escanear o sin hallazgos) no llevan halo --
    # a propósito, ver ui/codebase_view.py::RiskLegend.
    assert color_for_severity("low") is None
    assert color_for_severity("info") is None
    assert color_for_severity(None) is None
