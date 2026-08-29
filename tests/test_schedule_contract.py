from pathlib import Path
import re


RUN_WORKFLOW = Path('.github/workflows/run.yml').read_text(encoding='utf-8')


def test_tehran_cron_matches_declared_publication_windows():
    crons = re.findall(r'- cron:\s*"([^"]+)"', RUN_WORKFLOW)
    assert crons == [
        '47 1 * * *',
        '17 7,10,14,17,19 * * *',
    ]


def test_schedule_is_explicitly_documented_as_utc_conversion():
    assert 'Tehran publication windows:' in RUN_WORKFLOW
    assert '05:17, 10:47, 13:47, 17:47, 20:47, 22:47' in RUN_WORKFLOW
    assert 'Tehran is UTC+3:30' in RUN_WORKFLOW
    assert 'first window needs :47 UTC' in RUN_WORKFLOW
    assert 'remaining windows map from :17 UTC to :47 Tehran' in RUN_WORKFLOW
