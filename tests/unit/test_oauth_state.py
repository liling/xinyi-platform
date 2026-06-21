from xinyi_platform.auth.oauth_state import (
    generate_oauth_state,
    sign_oauth_state,
    verify_oauth_state,
)

SECRET = "test-secret-with-at-least-32-characters!!"


def test_generate_oauth_state_unique():
    a = generate_oauth_state()
    b = generate_oauth_state()
    assert a != b
    assert len(a) >= 32


def test_sign_and_verify_oauth_state():
    state = generate_oauth_state()
    sig = sign_oauth_state(state, SECRET)
    assert verify_oauth_state(state, sig, SECRET) is True


def test_verify_oauth_state_wrong_sig():
    state = generate_oauth_state()
    assert verify_oauth_state(state, "wrong-sig", SECRET) is False


def test_verify_oauth_state_tampered():
    state = generate_oauth_state()
    sig = sign_oauth_state(state, SECRET)
    assert verify_oauth_state(state + "tampered", sig, SECRET) is False
