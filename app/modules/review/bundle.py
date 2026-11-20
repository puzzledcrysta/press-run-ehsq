import json
from app.modules.runs.service import get
from app.modules.handover.service import status
from .decisions import timeline


def bundle(run_id):
    history = timeline(run_id)
    run = get(run_id)
    handover = status(run_id)
    # The export carries source line evidence and the applicable decision version.
    # 交班清理后导出只含凭据与清理状态，不含备注原文。
    return json.dumps({'manifest':run['manifest'],'counts':run['counts'],'results':run['accepted'],
                       'quarantine':run['quarantine'],'suppressed':run['suppressed'],
                       'reconciliation':run['book'],'review':history,'handover':handover},
                      ensure_ascii=False,indent=2)
