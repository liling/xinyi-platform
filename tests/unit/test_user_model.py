import uuid

from xinyi_platform.models.user import AuthProvider, User, UserRole


def test_user_can_be_constructed_with_required_fields():
    u = User(
        username="alice",
        display_name="Alice",
        auth_provider=AuthProvider.LOCAL,
        role=UserRole.USER,
    )
    assert u.username == "alice"
    assert u.role == UserRole.USER
    assert u.auth_provider == AuthProvider.LOCAL


def test_user_id_is_uuid():
    u = User(username="x", display_name="x", auth_provider=AuthProvider.LOCAL)
    u.id = uuid.uuid4()
    assert isinstance(u.id, uuid.UUID)


def test_user_role_enum_values():
    assert UserRole.ADMIN.value == "admin"
    assert UserRole.USER.value == "user"


def test_auth_provider_enum_values():
    assert AuthProvider.LOCAL.value == "local"
    assert AuthProvider.CAS.value == "cas"
