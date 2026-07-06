import bcrypt


class PasswordStrengthError(ValueError):
    pass


def hash_password(plaintext: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(plaintext.encode("utf-8"), salt).decode("ascii")


def verify_password(plaintext: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plaintext.encode("utf-8"), hashed.encode("ascii"))
    except (ValueError, TypeError):
        return False


def validate_password_strength(plaintext: str) -> None:
    if len(plaintext) < 8:
        raise PasswordStrengthError("Password must be at least 8 characters")
    if not any(c.isupper() for c in plaintext):
        raise PasswordStrengthError("Password must contain at least one uppercase letter")
    if not any(c.isdigit() for c in plaintext):
        raise PasswordStrengthError("Password must contain at least one digit")
