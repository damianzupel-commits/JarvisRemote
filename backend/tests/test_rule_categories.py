from app.security.rule_categories import CATEGORY_LABEL, CHECK_ID_TO_CATEGORY, category_for_rule


def test_category_for_rule_resolves_a_known_rule():
    assert category_for_rule("java.lang.security.audit.tainted-session-from-http-request.tainted-session-from-http-request") == "trustbound"


def test_category_for_rule_returns_none_for_an_unknown_rule():
    assert category_for_rule("some.rule.nobody.mapped") is None


def test_every_mapped_category_has_a_human_label():
    for category in set(CHECK_ID_TO_CATEGORY.values()):
        assert category in CATEGORY_LABEL
