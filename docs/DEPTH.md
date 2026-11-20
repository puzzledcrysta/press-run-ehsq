# 印刷损耗稽核深度登记

- 规模：中型
- 核心规则：按刀版拼数及前后独立损耗求可交成品，换算为整包与尾包并对照工单目标。
- 使用者与工作流：印厂生产统计员按工单复算来源批次，对照外部记录后提交复核。

## 功能模块

| 模块 | 使用者动作 | 入口 | 核心文件 | 测试 |
|---|---|---|---|---|
| M1 来源采信 | 接收分段记录、定位坏行 | `POST /api/intake` | `app/modules/intake/service.py` | `tests/test_intake.py` |
| M2 字段解释 | 归一主键、版本、时间和原字段 | `POST /api/contract` | `app/modules/contract/service.py` | `tests/test_contract.py` |
| M3 隔离裁决 | 归并重复、隔离争议版本 | `POST /api/quality` | `app/modules/quality/versions.py` | `tests/test_quality.py` |
| M4 成品折算 | 复算业务明细与边界证据 | `POST /api/domain` | `app/modules/domain/rule.py` | `tests/test_domain.py` |
| M5 独立对账 | 核对外部记录并分别计量 | `POST /api/reconcile` | `app/modules/reconcile/service.py` | `tests/test_reconcile.py` |
| M6 批次复算 | 保存运行、查询历史、复算原输入 | `POST /api/runs` | `app/modules/runs/service.py` | `tests/test_runs.py` |
| M7 交付复核 | 复核差异、阻止陈旧提交、导出证据 | `GET /api/export` | `app/modules/review/decisions.py` | `tests/test_review.py` |
| M8 交班清理 | 复核员决定撤回原文留凭据或保留受控证据并隔离 | `POST /api/runs/{id}/handover` | `app/modules/handover/service.py` | `tests/test_handover.py` |

## 陷阱登记

| TRAP | 现象 | 样例 | 处理位置 | 测试 |
|---|---|---|---|---|
| TRAP-02 | BOM | shift.csv | `app/modules/intake/service.py` | `tests/test_intake.py::test_bom` |
| TRAP-03 | 引号内换行 | shift.csv | `app/modules/intake/service.py` | `tests/test_intake.py::test_multiline` |
| TRAP-04 | 重复表头 | shift.csv | `app/modules/intake/service.py` | `tests/test_intake.py::test_repeated` |
| TRAP-05 | 列数不齐 | shift.csv | `app/modules/intake/service.py` | `tests/test_intake.py::test_width` |
| TRAP-07 | 空值哨兵 | shift.csv | `app/modules/contract/service.py` | `tests/test_contract.py::test_missing` |
| TRAP-08 | 主键前导零 | shift.csv | `app/modules/contract/service.py` | `tests/test_contract.py::test_leading_zero` |
| TRAP-11 | 偏移时间归一 | shift.csv | `app/modules/contract/service.py` | `tests/test_contract.py::test_offsets` |
| TRAP-14 | 等版本冲突 | shift.csv | `app/modules/quality/versions.py` | `tests/test_quality.py::test_conflicting` |
| TRAP-18 | 三种空态 | 测试构造输入 | `app/modules/intake/service.py` | `tests/test_intake.py::test_empty_states` |
| TRAP-26 | 陈旧复核 | 测试构造输入 | `app/modules/review/decisions.py` | `tests/test_review.py::test_stale` |

## 对账规则

输入记录数 = 计入 + 隔离 + 去重和替换 + 空白记录 + 重复表头。
业务账按工单全外连接。差异分别标记漏记、外部单边和数值不符，以合格张对差。

## 交班清理

班次备注可能夹着客户名与配方片段。复核员在交付复核页选择清理方式，两种
方式得到同一份可复核结论：备注单元格替换为 `‹已清理#摘要›`，记录附带
`note_proof`（归一备注的 SHA-256 与长度），工作台、导出与来源回取都不再
出现原文。撤回方式销毁原文；保留方式把原始来源封存于受控证据表，仅
`POST /api/runs/{id}/handover/reveal` 可取回，`verify` 接口按行号核对凭据。
清理在单事务内完成，失败回滚保留旧版结论；重跑与同方式重复提交都是幂等
的，保留可升级为撤回，反向不允许。列数不齐的坏行无法定位备注列，原样保留。

## 范围

本地文件与单机复核。单次来源文本限 128 KiB。复合字段单项最多 240 段。
