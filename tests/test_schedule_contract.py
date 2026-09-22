import re
from pathlib import Path

RUN_WORKFLOW = Path('.github/workflows/run.yml').read_text(encoding='utf-8')


def test_tehran_cron_matches_declared_publication_windows():
    crons = re.findall(r'- cron:\s*"([^"]+)"', RUN_WORKFLOW)
    assert crons == [
        '47 1 * * *',
        '17 7,10,14,17,19 * * *',
    ]


def test_schedule_is_explicitly_documented_as_utc_conversion():
    assert 'Tehran publication windows:' in RUN_WORKFLOW
    for window in ('05:17', '10:47', '13:47', '17:47', '20:47', '22:47'):
        assert window in RUN_WORKFLOW
    assert 'UTC+3:30' in RUN_WORKFLOW
    assert 'GitHub Actions cron is UTC' in RUN_WORKFLOW


def test_production_runs_are_serialized_and_checkout_latest_main_state():
    assert 'cancel-in-progress: false' in RUN_WORKFLOW
    assert 'ref: main' in RUN_WORKFLOW
    assert 'fetch-depth: 50' in RUN_WORKFLOW
