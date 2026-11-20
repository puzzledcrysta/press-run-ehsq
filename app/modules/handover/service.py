import json
from datetime import datetime, timezone
from hashlib import sha256
from app.errors import DataError
from app.store import connection
from app.modules.runs.repository import lookup
from .scrub import SECTIONS, credential, data_rows, locate, scrub_result, scrub_source, sensitive

MODES = ('withdraw', 'retain')


def current(db, run_id):
    row = db.execute('SELECT * FROM handovers WHERE run_id=? ORDER BY version DESC LIMIT 1',
                     (run_id,)).fetchone()
    return dict(row) if row else None


def cleared(run_id):
    with connection() as db:
        return current(db, run_id) is not None


def state(db, run_id):
    versions = [dict(row) for row in db.execute(
        'SELECT version,mode,notes,changed FROM handovers WHERE run_id=? ORDER BY version DESC',
        (run_id,))]
    sealed = db.execute('SELECT COUNT(*) FROM sealed_evidence WHERE run_id=?', (run_id,)).fetchone()[0] > 0
    latest = versions[0] if versions else {}
    return {'run_id': run_id, 'cleared': bool(versions), 'mode': latest.get('mode'),
            'notes': latest.get('notes', 0), 'changed': latest.get('changed'),
            'sealed': sealed, 'versions': versions}


def status(run_id):
    with connection() as db:
        lookup(db, run_id)
        return state(db, run_id)


def apply(run_id, mode):
    if mode not in MODES:
        raise DataError('HANDOVER_MODE', '清理方式无效')
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        run = lookup(db, run_id)
        existing = current(db, run_id)
        now = datetime.now(timezone.utc).isoformat()
        if existing:
            if existing['mode'] == mode:
                return state(db, run_id)
            if existing['mode'] == 'retain' and mode == 'withdraw':
                db.execute('DELETE FROM sealed_evidence WHERE run_id=?', (run_id,))
                db.execute('INSERT INTO handovers VALUES (?,?,?,?,?)',
                           (run_id, existing['version'] + 1, 'withdraw', existing['notes'], now))
                return state(db, run_id)
            raise DataError('HANDOVER_CONFLICT', '原文已撤回，无法改为保留受控证据', 409)
        text, names, note_idx = locate(run['source'])
        result = json.loads(run['result'])
        cleaned, proofs = scrub_result(result, names, note_idx)
        if any(len(cleaned[section]) != len(result[section]) for section in SECTIONS):
            raise RuntimeError('交班清理后记录数无法闭合')
        if proofs:
            scrubbed = scrub_source(text, names, note_idx)
            db.execute('UPDATE runs SET result=?, source=? WHERE id=?',
                       (json.dumps(cleaned, ensure_ascii=False), scrubbed.encode(), run_id))
        if mode == 'retain':
            db.execute('INSERT INTO sealed_evidence VALUES (?,?,?)', (run_id, run['source'], now))
        db.execute('INSERT INTO handovers VALUES (?,?,?,?,?)', (run_id, 1, mode, len(proofs), now))
        return state(db, run_id)


def verify(run_id, line, note):
    with connection() as db:
        run = lookup(db, run_id)
        if not current(db, run_id):
            raise DataError('HANDOVER_PENDING', '尚未交班清理，请先完成清理再核对凭据', 409)
        result = json.loads(run['result'])
    for section in SECTIONS:
        for record in result[section]:
            if record['line'] == line:
                proof = record.get('note_proof')
                if proof is None:
                    return {'line': line, 'credential': False, 'match': None}
                return {'line': line, 'credential': True,
                        'match': credential(note.strip()) == proof['sha256']}
    raise DataError('LINE_UNKNOWN', '没有此行号的记录', 404)


def reveal(run_id):
    with connection() as db:
        lookup(db, run_id)
        if not current(db, run_id):
            raise DataError('HANDOVER_PENDING', '尚未交班清理，没有受控证据', 409)
        row = db.execute('SELECT source,sealed FROM sealed_evidence WHERE run_id=?', (run_id,)).fetchone()
        if row is None:
            raise DataError('HANDOVER_WITHDRAWN', '原文已撤回，仅留可核对凭据', 409)
        text, names, note_idx = locate(row['source'])
        notes = []
        if note_idx is not None:
            width = len(names)
            for line, raw in data_rows(text):
                if len(raw) == width and sensitive(raw[note_idx]):
                    note = raw[note_idx].strip()
                    notes.append({'line': line, 'note': note, 'sha256': credential(note)})
        return {'run_id': run_id, 'sealed': row['sealed'],
                'source_sha256': sha256(row['source']).hexdigest(), 'notes': notes}
