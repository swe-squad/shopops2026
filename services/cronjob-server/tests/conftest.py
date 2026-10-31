import os
import re

import pytest

from app.config import Settings
from app.storage.db import connect


@pytest.fixture
def database():
    settings = Settings.from_env()
    if (
        os.getenv("SHOP_OPS_TEST_DATABASE") != "1"
        or not re.fullmatch(r"shopops_test_[a-z0-9]+", settings.database)
        or settings.host not in {"127.0.0.1", "localhost"}
    ):
        pytest.fail("Database tests require the isolated test runner")
    with connect() as conn:
        conn.execute("DROP SCHEMA IF EXISTS mart,core,raw,access,sync CASCADE")
        conn.execute("DROP TABLE IF EXISTS public.sentinel")
    yield settings
