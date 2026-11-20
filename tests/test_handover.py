import json
from hashlib import sha256
import pytest
from fastapi.testclient import TestClient
from app import settings
from app.main import app

NOTE_LINE2 = '交班底单\n二次校对'
ORIGINALS = ('东班复核', '交班底单', '乙方更新', '甲方更新', '未补录时间', '领料登记', '裁刀末件复核')


@pytest.fixture
def anchor(client):
    return client.post('/api/runs', json={}).json()['manifest']['run_id']


def handover(client, anchor, mode='withdraw'):
    return client.post(f'/api/runs/{anchor}/handover', json={'mode': mode})


def conclusion(report):
    keys = ('counts', 'balanced', 'accepted', 'quarantine', 'suppressed', 'reasons', 'book', 'encoding')
    return {key: report[key] for key in keys}


def test_withdraw_hides_originals_keeps_credentials(client, anchor):
    state = handover(client, anchor).json()
    assert (state['cleared'], state['mode'], state['sealed']) == (True, 'withdraw', False)
    assert state['notes'] == 33
    report = client.get(f'/api/runs/{anchor}').json()
    payload = json.dumps(report, ensure_ascii=False)
    assert all(text not in payload for text in ORIGINALS)
    assert payload.count('已清理#') == 33
    row = next(item for item in report['accepted'] if item['line'] == 2)
    proof = sha256(NOTE_LINE2.encode()).hexdigest()
    assert row['note_proof'] == {'sha256': proof, 'chars': len(NOTE_LINE2)}
    assert row['raw'][-1] == f'‹已清理#{proof[:8]}›'
    # 坏行没有可定位的备注列，原样保留，记录一条不丢
    bad = next(item for item in report['quarantine'] if item['code'] == 'WIDTH')
    assert bad['raw'] == ['残行', '2'] and 'note_proof' not in bad
    assert report['counts'] == {'input': 36, 'accepted': 26, 'rejected': 6,
                                'suppressed': 2, 'blank': 1, 'repeated_header': 1}


def test_export_and_source_are_clean_after_handover(client, anchor):
    handover(client, anchor, 'retain')
    exported = client.get(f'/api/export/{anchor}')
    assert exported.status_code == 200
    assert all(text not in exported.text for text in ORIGINALS)
    state = exported.json()['handover']
    assert (state['mode'], state['sealed'], state['notes']) == ('retain', True, 33)
    source = client.get(f'/api/runs/{anchor}/source').json()
    from base64 import b64decode
    text = b64decode(source['data_base64']).decode()
    assert all(item not in text for item in ORIGINALS) and '已清理#' in text


def test_same_conclusion_for_both_modes(client, anchor, monkeypatch, tmp_path):
    handover(client, anchor, 'retain')
    retained = client.get(f'/api/runs/{anchor}').json()
    monkeypatch.setattr(settings, 'DB', tmp_path / 'second.sqlite3')
    assert client.post('/api/runs', json={}).json()['manifest']['run_id'] == anchor
    handover(client, anchor, 'withdraw')
    withdrawn = client.get(f'/api/runs/{anchor}').json()
    assert conclusion(retained) == conclusion(withdrawn)


def test_handover_idempotent_no_extra_evidence(client, anchor):
    first = handover(client, anchor, 'retain').json()
    cleaned = client.get(f'/api/runs/{anchor}').json()
    second = handover(client, anchor, 'retain').json()
    assert second == first and second['versions'] == [first['versions'][0]]
    assert client.get(f'/api/runs/{anchor}').json() == cleaned
    assert len(client.get('/api/runs').json()) == 1


def test_replay_and_resubmit_keep_cleaned_conclusion(client, anchor):
    handover(client, anchor)
    cleaned = client.get(f'/api/runs/{anchor}').json()
    assert client.post(f'/api/runs/{anchor}/replay').json() == cleaned
    assert client.post('/api/runs', json={}).json() == cleaned
    assert len(client.get('/api/runs').json()) == 1


def test_retain_then_withdraw_upgrades(client, anchor):
    handover(client, anchor, 'retain')
    retained = client.get(f'/api/runs/{anchor}').json()
    state = handover(client, anchor, 'withdraw').json()
    assert [row['version'] for row in state['versions']] == [2, 1]
    assert state['sealed'] is False
    assert client.get(f'/api/runs/{anchor}').json() == retained
    gone = client.post(f'/api/runs/{anchor}/handover/reveal')
    assert (gone.status_code, gone.json()['code']) == (409, 'HANDOVER_WITHDRAWN')


def test_withdraw_then_retain_conflicts(client, anchor):
    handover(client, anchor, 'withdraw')
    response = handover(client, anchor, 'retain')
    assert (response.status_code, response.json()['code']) == (409, 'HANDOVER_CONFLICT')


def test_failed_cleanup_keeps_old_conclusion(client, anchor, monkeypatch):
    assert client.post(f'/api/review/{anchor}',
                       json={'version': 0, 'decision': '确认', 'note': '已逐条核对外部账'}).status_code == 200
    before = client.get(f'/api/runs/{anchor}').json()

    def boom(*args):
        raise RuntimeError('模拟清理中途失败')

    monkeypatch.setattr('app.modules.handover.service.scrub_result', boom)
    raw = TestClient(app, raise_server_exceptions=False)
    assert raw.post(f'/api/runs/{anchor}/handover', json={'mode': 'retain'}).status_code == 500
    assert client.get(f'/api/runs/{anchor}').json() == before
    assert client.get(f'/api/runs/{anchor}/handover').json()['cleared'] is False
    assert [row['version'] for row in client.get(f'/api/review/{anchor}').json()] == [1]


def test_reveal_returns_sealed_originals(client, anchor):
    handover(client, anchor, 'retain')
    sealed = client.post(f'/api/runs/{anchor}/handover/reveal').json()
    proof = client.get(f'/api/runs/{anchor}').json()['manifest']
    assert sealed['source_sha256'] == proof['source_sha256']
    notes = {row['line']: row for row in sealed['notes']}
    assert len(notes) == 33
    assert notes[2]['note'] == NOTE_LINE2
    assert notes[2]['sha256'] == sha256(NOTE_LINE2.encode()).hexdigest()


def test_reveal_requires_cleanup(client, anchor):
    pending = client.post(f'/api/runs/{anchor}/handover/reveal')
    assert (pending.status_code, pending.json()['code']) == (409, 'HANDOVER_PENDING')


def test_verify_note_against_credential(client, anchor):
    handover(client, anchor)
    match = client.post(f'/api/runs/{anchor}/handover/verify', json={'line': 2, 'note': NOTE_LINE2})
    assert match.json() == {'line': 2, 'credential': True, 'match': True}
    mismatch = client.post(f'/api/runs/{anchor}/handover/verify', json={'line': 2, 'note': '别家配方'})
    assert mismatch.json()['match'] is False
    plain = client.post(f'/api/runs/{anchor}/handover/verify', json={'line': 36, 'note': '残行'})
    assert plain.json() == {'line': 36, 'credential': False, 'match': None}
    missing = client.post(f'/api/runs/{anchor}/handover/verify', json={'line': 999, 'note': 'x'})
    assert (missing.status_code, missing.json()['code']) == (404, 'LINE_UNKNOWN')


def test_verify_requires_cleanup(client, anchor):
    response = client.post(f'/api/runs/{anchor}/handover/verify', json={'line': 2, 'note': NOTE_LINE2})
    assert (response.status_code, response.json()['code']) == (409, 'HANDOVER_PENDING')


def test_handover_unknown_run(client):
    response = handover(client, 'missing')
    assert (response.status_code, response.json()['code']) == (404, 'RUN_UNKNOWN')
    assert client.get('/api/runs/missing/handover').status_code == 404


def test_export_reproducible_after_handover(client, anchor):
    handover(client, anchor, 'retain')
    first, second = client.get(f'/api/export/{anchor}'), client.get(f'/api/export/{anchor}')
    assert first.content == second.content
