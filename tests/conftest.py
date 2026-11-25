import pytest

from jev_decision.config import Settings


@pytest.fixture
def settings(tmp_path):
    return Settings(
        db_path=str(tmp_path / "history.db"),
        mcp_token="x" * 40,
        typesafe_api_key="test-key",
    )
