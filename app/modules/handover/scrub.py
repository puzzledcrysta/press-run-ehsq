import csv
from copy import deepcopy
from hashlib import sha256
from io import StringIO
from app.modules.contract.schema import mapping, MISSING
from app.modules.intake.reader import decode, records

NOTE = '原始备注'
SECTIONS = ('accepted', 'quarantine', 'suppressed')


def credential(note):
    # 可核对凭据：归一（去首尾空白）备注的 SHA-256，争议时按同一规则复算比对。
    return sha256(note.encode()).hexdigest()


def marker(proof):
    return f'‹已清理#{proof[:8]}›'


def sensitive(cell):
    return cell.strip().casefold() not in MISSING


def locate(source):
    text, _ = decode(source)
    _, header = next(records(text), (0, []))
    names = mapping([part.strip().removeprefix('\ufeff') for part in header])
    return text, names, names.index(NOTE) if NOTE in names else None


def data_rows(text):
    header = None
    for line, row in records(text):
        values = [part.strip().removeprefix('\ufeff') for part in row]
        if header is None and any(values):
            header = values
        if values == header:
            continue
        yield line, row


def scrub_result(result, names, note_idx):
    cleaned, proofs = deepcopy(result), []
    if note_idx is None:
        return cleaned, proofs
    width = len(names)
    for section in SECTIONS:
        for record in cleaned[section]:
            raw = record.get('raw') or []
            if len(raw) != width:
                continue
            note = raw[note_idx].strip()
            if not sensitive(note):
                continue
            proof = credential(note)
            raw[note_idx] = marker(proof)
            record['note_proof'] = {'sha256': proof, 'chars': len(note)}
            proofs.append({'line': record['line'], 'sha256': proof})
    return cleaned, proofs


def scrub_source(text, names, note_idx):
    if note_idx is None:
        return text
    width = len(names)
    header = None
    out = StringIO(newline='')
    writer = csv.writer(out, lineterminator='\n')
    for _, row in records(text):
        values = [part.strip().removeprefix('\ufeff') for part in row]
        if header is None and any(values):
            header = values
        if values != header and len(row) == width and sensitive(row[note_idx]):
            row[note_idx] = marker(credential(row[note_idx].strip()))
        writer.writerow(row)
    return out.getvalue()
