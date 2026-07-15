from app.nlp.colors import canonical_color, colors_match, extract_color


def test_basic_color_language_resolves_to_unshaded_base_color():
    assert extract_color("a basic blue shirt") == "blue"
    assert extract_color("plain blue please") == "blue"
    assert canonical_color("standard blue") == "blue"


def test_named_blue_shades_resolve_to_specific_families():
    assert extract_color("navy blue instead") == "dark blue"
    assert extract_color("something powder blue") == "light blue"
    assert extract_color("a royal blue kurta") == "bright blue"


def test_base_blue_does_not_match_light_or_dark_shades():
    assert colors_match("blue", "Blue")
    assert not colors_match("blue", "Dark Blue")
    assert not colors_match("blue", "Light Blue")
    assert not colors_match("blue", "Navy")


def test_explicit_shade_matches_its_named_family_only():
    assert colors_match("dark blue", "Navy Blue")
    assert colors_match("light blue", "Sky Blue")
    assert not colors_match("light blue", "Royal Blue")
