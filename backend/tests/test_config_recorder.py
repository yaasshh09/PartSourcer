from config import Settings


def test_recorder_defaults_are_disabled():
    s = Settings(_env_file=None)
    assert s.database_url is None
    assert s.recorder_token is None


def test_recorder_batch_defaults():
    s = Settings(_env_file=None)
    assert s.recorder_batch_size == 500
    assert s.recorder_concurrency == 4
