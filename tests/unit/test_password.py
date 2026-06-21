import pytest

from xinyi_platform.auth.password import (
    PasswordStrengthError,
    hash_password,
    validate_password_strength,
    verify_password,
)


def test_hash_password_creates_bcrypt_hash():
    h = hash_password("MyStrong123!")
    assert h != "MyStrong123!"
    assert h.startswith("$2")


def test_verify_password_correct():
    h = hash_password("MyStrong123!")
    assert verify_password("MyStrong123!", h) is True


def test_verify_password_wrong():
    h = hash_password("MyStrong123!")
    assert verify_password("wrong", h) is False


def test_validate_password_strength_rejects_short():
    with pytest.raises(PasswordStrengthError, match="at least"):
        validate_password_strength("Ab1!")


def test_validate_password_strength_rejects_no_uppercase():
    with pytest.raises(PasswordStrengthError, match="uppercase"):
        validate_password_strength("stronglower123!")


def test_validate_password_strength_rejects_no_digit():
    with pytest.raises(PasswordStrengthError, match="digit"):
        validate_password_strength("Stronglower!")


def test_validate_password_strength_accepts_strong():
    validate_password_strength("MyStrong123!")
