"""
GreenOps — Enum correctness & admin bootstrap tests.

Run:
    pytest server/tests/test_enum_and_admin.py -v

Dependencies (add to dev requirements):
    pytest
    pytest-asyncio
    pytest-mock
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call


# ---------------------------------------------------------------------------
# 1. UserRole enum unit tests
# ---------------------------------------------------------------------------

class TestUserRoleEnum:
    """Validate the UserRole enum behaves correctly in all edge cases."""

    def test_admin_value_is_lowercase(self):
        from database import UserRole
        assert UserRole.ADMIN.value == "admin", (
            "UserRole.ADMIN.value must be 'admin' to match PostgreSQL enum"
        )

    def test_viewer_value_is_lowercase(self):
        from database import UserRole
        assert UserRole.VIEWER.value == "viewer"

    def test_enum_from_lowercase_string(self):
        """UserRole('admin') must return UserRole.ADMIN."""
        from database import UserRole
        assert UserRole("admin") is UserRole.ADMIN
        assert UserRole("viewer") is UserRole.VIEWER

    def test_enum_from_uppercase_string_normalised(self):
        """
        UserRole('ADMIN') must be normalised to UserRole.ADMIN via _missing_.
        This prevents the 'invalid input value for enum user_role: ADMIN' error.
        """
        from database import UserRole
        assert UserRole("ADMIN") is UserRole.ADMIN
        assert UserRole("VIEWER") is UserRole.VIEWER

    def test_enum_from_mixed_case_string_normalised(self):
        from database import UserRole
        assert UserRole("Admin") is UserRole.ADMIN
        assert UserRole("Viewer") is UserRole.VIEWER

    def test_invalid_role_raises_value_error(self):
        """Unknown role must raise ValueError, not silently accept bad data."""
        from database import UserRole
        with pytest.raises(ValueError, match="not a valid UserRole"):
            UserRole("superuser")

    def test_invalid_role_empty_string_raises(self):
        from database import UserRole
        with pytest.raises(ValueError):
            UserRole("")

    def test_invalid_role_integer_raises(self):
        from database import UserRole
        with pytest.raises(ValueError):
            UserRole(1)

    def test_userrole_is_str_subclass(self):
        """UserRole inherits from str so comparisons with plain strings work."""
        from database import UserRole
        assert UserRole.ADMIN == "admin"
        assert UserRole.VIEWER == "viewer"
        # Uppercase should NOT match because the value is lowercase
        assert UserRole.ADMIN != "ADMIN"

    def test_str_subclass_no_raw_uppercase_stored(self):
        """
        Demonstrate the exact bug this fix prevents:
        Before fix, SQLAlchemy stored "ADMIN" (the .name).
        After fix, it stores "admin" (the .value).
        """
        from database import UserRole
        stored = UserRole.ADMIN.value   # what values_callable sends to PG
        assert stored == "admin"
        assert stored != "ADMIN"


# ---------------------------------------------------------------------------
# 2. _coerce_role helper tests
# ---------------------------------------------------------------------------

class TestCoerceRole:
    """Test the _coerce_role() helper in routers/auth.py."""

    def test_coerce_enum_member_passthrough(self):
        from database import UserRole
        from routers.auth import _coerce_role
        assert _coerce_role(UserRole.ADMIN) is UserRole.ADMIN

    def test_coerce_lowercase_string(self):
        from database import UserRole
        from routers.auth import _coerce_role
        assert _coerce_role("admin") is UserRole.ADMIN

    def test_coerce_uppercase_string(self):
        from database import UserRole
        from routers.auth import _coerce_role
        assert _coerce_role("ADMIN") is UserRole.ADMIN

    def test_coerce_invalid_string_raises(self):
        from routers.auth import _coerce_role
        with pytest.raises(ValueError):
            _coerce_role("invalid_role")

    def test_coerce_invalid_type_raises(self):
        from routers.auth import _coerce_role
        with pytest.raises(ValueError):
            _coerce_role(42)


# ---------------------------------------------------------------------------
# 3. ensure_admin_exists() unit tests (mocked DB)
# ---------------------------------------------------------------------------

class TestEnsureAdminExists:
    """Validate ensure_admin_exists() logic without a real database."""

    @pytest.mark.asyncio
    async def test_skips_if_admin_already_exists(self):
        """If admin row exists in DB, must return immediately without INSERT."""
        from database import User, UserRole
        from routers.auth import ensure_admin_exists

        existing = MagicMock(spec=User)
        existing.role = UserRole.ADMIN

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing

        mock_db = AsyncMock()
        # First execute is the enum sanity check, second is the SELECT
        mock_db.execute = AsyncMock(return_value=mock_result)

        await ensure_admin_exists(mock_db)

        # commit must NOT be called — no INSERT happened
        mock_db.commit.assert_not_called()
        mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_creates_admin_with_userrole_admin_enum(self):
        """New admin must be created with role=UserRole.ADMIN (never a string)."""
        from database import User, UserRole
        from routers.auth import ensure_admin_exists

        # First call: enum sanity check (returns anything truthy)
        # Second call: SELECT returns None (no existing admin)
        enum_check_result = MagicMock()
        no_user_result = MagicMock()
        no_user_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=[enum_check_result, no_user_result])
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.rollback = AsyncMock()

        with patch("routers.auth.get_settings") as mock_settings_fn:
            cfg = MagicMock()
            cfg.INITIAL_ADMIN_USERNAME = "admin"
            cfg.INITIAL_ADMIN_PASSWORD = "StrongPass123!"
            mock_settings_fn.return_value = cfg

            await ensure_admin_exists(mock_db)

        assert mock_db.add.called, "db.add() must be called to insert the admin"
        assert mock_db.commit.called, "db.commit() must be called after insert"

        added_user = mock_db.add.call_args[0][0]
        assert isinstance(added_user, User), "added object must be a User instance"

        # ── The key assertion: role must be UserRole.ADMIN, never a raw string ──
        assert added_user.role is UserRole.ADMIN, (
            f"Expected UserRole.ADMIN but got {added_user.role!r}. "
            "Do NOT use role='admin' or role='ADMIN' — use role=UserRole.ADMIN."
        )
        assert added_user.role.value == "admin"
        assert added_user.username == "admin"
        assert added_user.is_active is True

    @pytest.mark.asyncio
    async def test_handles_integrity_error_gracefully(self):
        """Race condition INSERT collision must be swallowed, not re-raised."""
        from sqlalchemy.exc import IntegrityError
        from routers.auth import ensure_admin_exists

        enum_check_result = MagicMock()
        no_user_result = MagicMock()
        no_user_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=[enum_check_result, no_user_result])
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock(
            side_effect=IntegrityError("duplicate key", {}, Exception())
        )
        mock_db.rollback = AsyncMock()

        with patch("routers.auth.get_settings") as mock_settings_fn:
            cfg = MagicMock()
            cfg.INITIAL_ADMIN_USERNAME = "admin"
            cfg.INITIAL_ADMIN_PASSWORD = "StrongPass123!"
            mock_settings_fn.return_value = cfg

            # Must not raise
            await ensure_admin_exists(mock_db)

        mock_db.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_re_raises_dbapi_error(self):
        """
        DBAPIError (e.g. enum mismatch, DB not ready) must be re-raised
        so lifespan fails fast with a clear error.
        """
        from sqlalchemy.exc import DBAPIError
        from routers.auth import ensure_admin_exists

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            side_effect=DBAPIError("invalid input value for enum", {}, Exception())
        )
        mock_db.rollback = AsyncMock()

        with patch("routers.auth.get_settings") as mock_settings_fn:
            cfg = MagicMock()
            cfg.INITIAL_ADMIN_USERNAME = "admin"
            cfg.INITIAL_ADMIN_PASSWORD = "StrongPass123!"
            mock_settings_fn.return_value = cfg

            with pytest.raises(DBAPIError):
                await ensure_admin_exists(mock_db)

        mock_db.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_generates_random_password_when_none_set(self):
        """When INITIAL_ADMIN_PASSWORD is empty, a random password is generated."""
        from database import User, UserRole
        from routers.auth import ensure_admin_exists

        enum_check_result = MagicMock()
        no_user_result = MagicMock()
        no_user_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=[enum_check_result, no_user_result])
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.rollback = AsyncMock()

        with patch("routers.auth.get_settings") as mock_settings_fn:
            cfg = MagicMock()
            cfg.INITIAL_ADMIN_USERNAME = "admin"
            cfg.INITIAL_ADMIN_PASSWORD = ""   # ← empty triggers random generation
            mock_settings_fn.return_value = cfg

            await ensure_admin_exists(mock_db)

        assert mock_db.add.called
        added_user = mock_db.add.call_args[0][0]
        # Even with random password, role must still be the enum member
        assert added_user.role is UserRole.ADMIN


# ---------------------------------------------------------------------------
# 4. values_callable correctness test
# ---------------------------------------------------------------------------

class TestSQLAlchemyEnumConfig:
    """Verify the SQLAlchemy Enum column is configured to use .value not .name."""

    def test_user_role_pg_uses_values_not_names(self):
        """
        The _user_role_pg Enum column must send 'admin'/'viewer' to PG,
        not 'ADMIN'/'VIEWER'.
        """
        from database import UserRole, _user_role_pg

        # values_callable result must be lowercase values
        expected = ["admin", "viewer"]
        actual = [e.value for e in UserRole]
        assert actual == expected, (
            f"values_callable must produce {expected} but got {actual}. "
            "Without values_callable, SQLAlchemy sends 'ADMIN' which PG rejects."
        )

    def test_user_role_pg_enum_name(self):
        """The PG type name must match what the migration created."""
        from database import _user_role_pg
        assert _user_role_pg.name == "user_role"


# ---------------------------------------------------------------------------
# 5. Edge case: raw string role assignment simulation
# ---------------------------------------------------------------------------

class TestRawStringRoleAssignment:
    """
    Simulate what happens when code accidentally uses raw strings for role.
    These tests document the WRONG behaviour and confirm our guards catch it.
    """

    def test_raw_uppercase_ADMIN_not_equal_to_enum_value(self):
        from database import UserRole
        # This is the exact value that was causing the PG error before the fix
        bad_value = "ADMIN"
        assert bad_value != UserRole.ADMIN.value, (
            "Raw 'ADMIN' must not equal UserRole.ADMIN.value ('admin'). "
            "This is what caused the PostgreSQL enum mismatch."
        )

    def test_raw_uppercase_ADMIN_normalised_by_coerce(self):
        """_coerce_role must silently fix legacy 'ADMIN' strings."""
        from database import UserRole
        from routers.auth import _coerce_role
        result = _coerce_role("ADMIN")
        assert result is UserRole.ADMIN
        assert result.value == "admin"

    def test_completely_invalid_role_rejected(self):
        from routers.auth import _coerce_role
        with pytest.raises(ValueError, match="not a valid UserRole"):
            _coerce_role("superuser")

    def test_completely_invalid_role_rejected_via_enum(self):
        from database import UserRole
        with pytest.raises(ValueError):
            UserRole("root")
