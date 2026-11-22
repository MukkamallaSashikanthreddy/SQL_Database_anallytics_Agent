from __future__ import annotations

import pytest

from database.seed import seed_database


@pytest.fixture
def sample_db(tmp_path):
    path = tmp_path / "analytics_test.db"
    seed_database(path)
    return path
