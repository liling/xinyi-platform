from xinyi_platform.crypto import decrypt_sm4, encrypt_sm4

KEY = "00112233445566778899aabbccddeeff"


def test_encrypt_decrypt_roundtrip():
    plaintext = "my-secret-api-key-12345"
    ciphertext = encrypt_sm4(plaintext, KEY)
    assert ciphertext != plaintext
    assert decrypt_sm4(ciphertext, KEY) == plaintext


def test_decrypt_with_wrong_key_fails():
    ciphertext = encrypt_sm4("hello", KEY)
    wrong_key = "ff112233445566778899aabbccddeeff"
    try:
        result = decrypt_sm4(ciphertext, wrong_key)
        assert result != "hello"
    except (ValueError, UnicodeDecodeError):
        pass


def test_encrypt_empty_string():
    ciphertext = encrypt_sm4("", KEY)
    assert decrypt_sm4(ciphertext, KEY) == ""


def test_encrypt_unicode():
    plaintext = "中文密钥 🔑"
    ciphertext = encrypt_sm4(plaintext, KEY)
    assert decrypt_sm4(ciphertext, KEY) == plaintext


def test_invalid_key_length():
    import pytest
    with pytest.raises(ValueError, match="SM4 key must be 16 bytes"):
        encrypt_sm4("x", "short")
