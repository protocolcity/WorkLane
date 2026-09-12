import json
from unittest.mock import patch

import pytest

from worklane.api.tasks.helpers import (
    _workforce_workers_for_product,
    _workforce_products_for_workers,
)


@pytest.mark.parametrize('contents', [None, '{broken', '{}', 'valid'])
def test_local_authority_never_consults_service(tmp_path, monkeypatch, contents):
    roster = tmp_path / 'roster.json'
    if contents == 'valid':
        contents = json.dumps({'workers': {
            'local-agent': {'kind': 'lane', 'queue_url': 'http://unused/ready?product=example'},
            'other-agent': {'kind': 'lane', 'queue_url': 'http://unused/ready?product=other'},
        }})
    if contents is not None:
        roster.write_text(contents)
    monkeypatch.setenv('WL_WORKFORCE_LOCAL_ONLY', '1')
    monkeypatch.setenv('WL_WORKFORCE_ROSTER', str(roster))
    with patch('urllib.request.urlopen') as network:
        workers = _workforce_workers_for_product('example')
        products = _workforce_products_for_workers()
        network.assert_not_called()
    expected = contents is not None and 'local-agent' in contents
    assert workers == (['worker:local-agent'] if expected else [])
    assert products == ({'local-agent': 'example', 'other-agent': 'other'} if expected else {})


def test_local_authority_requires_explicit_roster(tmp_path, monkeypatch):
    monkeypatch.setenv('WL_WORKFORCE_LOCAL_ONLY', '1')
    monkeypatch.delenv('WL_WORKFORCE_ROSTER', raising=False)
    monkeypatch.setenv('WORKFORCE_PREDIRTY', str(tmp_path / 'run/predirty.txt'))
    with patch('urllib.request.urlopen') as network:
        assert _workforce_workers_for_product('example') == []
        assert _workforce_products_for_workers() == {}
        network.assert_not_called()
