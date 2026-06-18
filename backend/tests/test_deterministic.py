from verifier.checks.deterministic import check_link_in_desc, check_code_in_desc


def test_link_present_is_met():
    r = check_link_in_desc("Bajá el juego: https://DL.Game/x?utm=abc ¡ya!", "https://dl.game/x")
    assert r.met is True
    assert r.method == "deterministic"
    assert r.evidence == "https://dl.game/x"


def test_link_absent_is_not_met():
    r = check_link_in_desc("Mirá mi gameplay", "https://dl.game/x")
    assert r.met is False
    assert r.evidence is None


def test_code_present_case_insensitive():
    r = check_code_in_desc("Usá el código GAMER20 al pagar", "gamer20")
    assert r.met is True
    assert r.evidence == "gamer20"


def test_code_absent():
    r = check_code_in_desc("Sin códigos hoy", "gamer20")
    assert r.met is False


def test_empty_expected_link_is_not_met():
    # Un expected_link vacío (brief mal configurado) NO debe dar PASS.
    r = check_link_in_desc("Bajá el juego: https://dl.game/x", "")
    assert r.met is False
    assert r.evidence is None


def test_empty_expected_code_is_not_met():
    r = check_code_in_desc("Usá el código GAMER20", "")
    assert r.met is False
    assert r.evidence is None
