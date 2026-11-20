import json
from datetime import datetime, timezone
from time import perf_counter
from app.manifest import manifest
from app.pipeline import execute
from app.modules.handover.service import cleared
from .repository import fetch, persist


def run(source,book):
    proof = manifest(source,book)
    started = perf_counter()
    result = execute(source,book)
    created = datetime.now(timezone.utc).isoformat()
    proof.update(elapsed_ms=round((perf_counter()-started)*1000,2),created=created)
    result['manifest'] = proof
    stored = persist(proof['run_id'],source,book,result,created)
    return json.loads(stored['result'])


def replay(run_id):
    old = fetch(run_id)
    if cleared(run_id):
        # 交班清理后结论已封存：重跑返回同一份结论，不新增证据也不丢记录。
        return json.loads(old['result'])
    return run(old['source'],old['book'])


def get(run_id):
    return json.loads(fetch(run_id)['result'])
