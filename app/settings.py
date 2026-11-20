import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_ROOT = ROOT / 'sample_data'
DB = Path(os.getenv('WORKBENCH_DB', str(ROOT/'state/ledger.sqlite3')))
TITLE = '印刷损耗稽核'
SLUG = 'press-run'
KEY = '工单'
FIELDS = ('上机纸张', '刀版拼数', '上机废纸', '裁切废件', '每包张数')
ROLE = '印厂生产统计员'
UNIT = '合格张'
SIGNATURE = '印版色带'
RULE_VERSION = 'press-run-1.0'
TABS = {'intake': '来源采信', 'contract': '字段解释', 'quality': '隔离裁决', 'domain': '成品折算', 'reconcile': '独立对账', 'runs': '批次复算', 'review': '交付复核'}
