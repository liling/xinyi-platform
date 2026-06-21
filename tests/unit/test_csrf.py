from xinyi_platform.auth.csrf import generate_csrf_token, verify_csrf


def test_generate_csrf_token_unique():
    a = generate_csrf_token()
    b = generate_csrf_token()
    assert a != b
    assert len(a) >= 32


def test_verify_csrf_match():
    t = generate_csrf_token()
    assert verify_csrf(t, t) is True


def test_verify_csrf_mismatch():
    assert verify_csrf(generate_csrf_token(), generate_csrf_token()) is False


def test_verify_csrf_missing():
    assert verify_csrf("", "x") is False
    assert verify_csrf("x", "") is False
