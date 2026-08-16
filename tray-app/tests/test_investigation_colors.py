from ui.investigation_colors import color_for_confidence, halo_style_for_centrality, investigation_halo


def test_color_for_confidence_none_means_no_color():
    assert color_for_confidence(None) is None


def test_color_for_confidence_zero_is_the_neutral_gray():
    assert color_for_confidence(0.0) == "#6b7280"


def test_color_for_confidence_one_is_the_jarvis_blue():
    assert color_for_confidence(1.0) == "#3b82f6"


def test_color_for_confidence_interpolates_between_the_two():
    mid = color_for_confidence(0.5)
    assert mid not in ("#6b7280", "#3b82f6")
    assert mid.startswith("#") and len(mid) == 7


def test_color_for_confidence_clamps_out_of_range_values():
    assert color_for_confidence(-1.0) == color_for_confidence(0.0)
    assert color_for_confidence(2.0) == color_for_confidence(1.0)


def test_halo_style_is_none_below_the_minimum_centrality_threshold():
    assert halo_style_for_centrality(0.0) is None
    assert halo_style_for_centrality(0.01) is None


def test_halo_style_grows_in_radius_and_opacity_with_centrality():
    low = halo_style_for_centrality(0.1)
    high = halo_style_for_centrality(0.9)

    assert low["radiusScale"] < high["radiusScale"]
    assert low["opacity"] < high["opacity"]


def test_halo_style_at_max_centrality_hits_the_max_bounds():
    style = halo_style_for_centrality(1.0)
    assert style["radiusScale"] == 1.6
    assert style["opacity"] == 0.60


def test_investigation_halo_combines_color_and_style():
    result = investigation_halo(centrality=0.8, confidence=1.0)

    assert result["color"] == "#3b82f6"
    assert "radiusScale" in result
    assert "opacity" in result


def test_investigation_halo_is_none_when_confidence_is_unknown():
    """Nunca fabricar una senal visual para 'no hay dato todavia' -- mismo
    principio que color_for_severity con archivos sin escanear."""
    result = investigation_halo(centrality=0.9, confidence=None)
    assert result is None


def test_investigation_halo_is_none_when_centrality_is_negligible():
    result = investigation_halo(centrality=0.0, confidence=0.9)
    assert result is None


def test_a_big_gray_halo_means_a_real_pivot_with_weak_evidence():
    """Lectura practica del diseño: centralidad alta + confianza baja =
    halo grande y gris -- justo lo primero que un investigador deberia
    revisar."""
    result = investigation_halo(centrality=0.9, confidence=0.1)

    assert result["radiusScale"] > 1.4
    # a confianza 0.1, el color deberia estar mucho mas cerca del gris que del azul
    r, g, b = int(result["color"][1:3], 16), int(result["color"][3:5], 16), int(result["color"][5:7], 16)
    gray_r, gray_g, gray_b = 0x6B, 0x72, 0x80
    blue_r, blue_g, blue_b = 0x3B, 0x82, 0xF6
    dist_to_gray = abs(r - gray_r) + abs(g - gray_g) + abs(b - gray_b)
    dist_to_blue = abs(r - blue_r) + abs(g - blue_g) + abs(b - blue_b)
    assert dist_to_gray < dist_to_blue
