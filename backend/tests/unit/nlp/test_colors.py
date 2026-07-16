from app.nlp.colors import canonical_color, colors_match, extract_color, extract_color_options


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


def test_pakistani_retail_shade_labels_are_classified_without_color_bleed():
    assert extract_color("a sapphire blue outfit") == "bright blue"
    assert extract_color("rani pink for mehndi") == "dark pink"
    assert extract_color("bottle green formal") == "dark green"
    assert extract_color("indigo kurta") == "dark purple"
    assert colors_match("dark purple", "Indigo Blue")
    assert not colors_match("blue", "Sapphire Blue")
    assert not colors_match("blue", "Indigo")


def test_neutral_and_metallic_labels_stay_in_their_own_families():
    assert colors_match("off white", "Ivory")
    assert colors_match("dark grey", "Slate Grey")
    assert colors_match("gold", "Champagne Gold")
    assert not colors_match("yellow", "Gold")
    assert not colors_match("white", "Cream")


def test_teal_crossover_does_not_bleed_into_plain_blue_or_green():
    assert colors_match("teal", "Turquoise")
    assert colors_match("teal", "Sea Green")
    assert not colors_match("blue", "Turquoise")
    assert not colors_match("green", "Sea Green")


def test_extracts_explicit_or_colors_but_not_colors_for_separate_outfit_pieces():
    assert extract_color_options("some knitted polos, brown or red") == ["brown", "red"]
    assert extract_color_options(
        "dark blue baggy jeans I can wear with a black shirt"
    ) == ["dark blue"]
