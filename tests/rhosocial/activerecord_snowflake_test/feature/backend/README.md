# feature/backend — Snowflake 测试科目矩阵

> 依据：核心库 `.claude/plan/2026-09-03/cross-backend-test-taxonomy.md` §3.3 / §5.8。
> 目录即覆盖矩阵：有目录+文件 = 已覆盖；仅有 README = 科目保留位（Tier-2 Fill 缺口）。

## 科目矩阵（§3.3 通用科目清单）

| 科目 | 状态 | 文件 | 备注 |
|------|------|------|------|
| core/ | ✅ 已有 | `test_clause_pair_guard.py`、`test_driver_error_mapping.py`、`test_execute_error_contract.py`、`test_generated_column_capabilities.py`、`test_identifier_quoting.py`、`test_introspection_data_profile.py`、`test_snowflake_constraint_switches.py`、`test_snowflake_database_ddl.py`、`test_snowflake_ddl_improvements.py` | 后端专属后端级测试（原位于 `backend/` 根下）；按「测试文件与子目录不得并存」规则收敛到 `core/`。`expression_roundtrip_harness.py` 留在 `backend/` 根，供 `expression/`、`types/` 以顶层模块名导入 |
| adapters/ | ✅ 已有 | `test_adapters.py` | VARIANT/ARRAY/Boolean/Decimal/Timestamp 适配器 |
| backend/ | ✅ 已有 | `test_backend_mock.py`、`test_config.py` | mock 驱动测试；**缺** `test_error_handling.py`(+async)（§6 矩阵 F） |
| cli/ | 🕳️ 空（README） | — | Tier-2 Fill（无 CLI 工具，暂不适用） |
| concurrency/ | ❌ 缺失 | — | §6 矩阵标记 F（Tier-2 Fill） |
| ddl/ | ✅ 已有 | `test_alter_table_if_exists.py`、`test_create_table_expression_diff.py`、`test_table_modifier.py`、`test_object_kind_refused.py` | `test_object_kind_refused.py` 断言传错对象种类必须拒绝渲染 |
| dialect/ | ✅ 已有 | `test_dialect.py`、`test_identifier_dynamic.py`、`test_namespace_rendering.py` | `test_namespace_rendering.py` 钉住「有 database 但不单独使用」的命名空间决定 |
| dml/ | ✅ 已有 | `test_insert_overwrite.py` | **缺** `test_crud_backend.py`(+`_async`)、`test_execute_many.py`（§6 矩阵 F） |
| expression/ | ✅ 已有 | `test_expression_signatures.py`、`test_expression_roundtrip_all.py` | 往返矩阵覆盖 core + snowflake 两个表达式包，无连接依赖 |
| extensions/ | ✅ 已有 | `test_file_format.py`、`test_routine.py`、`test_stream_task_pipe.py`、`test_undrop_clone_materialized_view.py`、`test_warehouse_stage_copy.py` | Snowflake 专属按 P8 归入 vendor 思路；对应 src `extensions/` |
| functions/ | 🕳️ 空（README） | — | Tier-2 Fill |
| introspection/ | ✅ 已有 | `test_introspection.py` | **缺** 规范拆分文件（tables/columns/indexes/…，Tier-2） |
| named_connection/ | ❌ 缺失 | — | Tier-2 Fill |
| protocol/ | ✅ 已有 | `test_protocol_conformance.py` | §6 矩阵 ✅ |
| query/ | ✅ 已有 | `test_pivot_unpivot.py`、`test_sample_tablesample.py` | Snowflake 专属查询子句 |
| schema/ | ✅ 已有 | `test_schema_diff.py` | **缺** `test_schema_support.py`（§5.8 Fill，孪生为 test_schema_diff.py） |
| snowflake/ | ✅ 已有 | `test_partition.py`、`test_show.py` | vendor 专属（partition、SHOW） |
| transactions/ | 🕳️ 空（README） | — | **缺** `test_transaction_backend.py`(+`_async`)（§5.8 Fill 重点；Snowflake 仅 READ COMMITTED，isolation 矩阵子集） |
| types/ | ✅ 已有 | `test_types.py`、`test_data_type_parsing.py` | vendor 专属（parse_type、类型助手） |
| views/ | 🕳️ 空（README） | — | `test_view_execution.py` 归 vendor（Snowflake 视图测试目前在 extensions/test_undrop_clone_materialized_view.py 内），常规视图执行测试 Tier-2 Fill |

## Sync/Async 对等（P4）—— Tier-2 Fill 遗留清单

`AsyncSnowflakeBackend` 是**真实实现**（thread-pool 包装，见
`src/rhosocial/activerecord/backend/impl/snowflake/async_backend.py`），但目前**零异步测试**；
无 `_async` 文件，故按 P4 不设 `async/` 目录（空目录已删除）。

本仓**无可用真实 Snowflake 服务实例**（CI 中 `SNOWFLAKE_*` 环境变量缺失时集成测试整体 skip；
fakesnow 模拟器仅覆盖部分场景），异步行为无法在本地验证，故本批**不新建**异步测试文件，
全部记为 Tier-2 Fill：

| 目标文件（Fill） | 同步孪生核对 |
|------------------|--------------|
| `dml/test_crud_backend_async.py` | 同步孪生 `dml/test_crud_backend.py` 亦缺 → 两者同批补（§5.8） |
| `transactions/test_transaction_backend_async.py` | 同步孪生 `transactions/test_transaction_backend.py` 亦缺 → 两者同批补（§5.8） |
| `backend/test_backend_async.py` | 同步孪生 `backend/test_backend.py` 亦缺；现有 `test_backend_mock.py` 为 mock 等价物 → 补齐时对齐 §5.8 |
| `schema/test_schema_support.py` | 孪生 `schema/test_schema_diff.py` 已有（§5.8 Fill，单侧补齐） |
| `basic/ddl/test_alter_table_basic_async.py` | testsuite 已有 async 契约（`basic/ddl/test_alter_table_if_exists_async.py`），bridge 待补 |
| basic/query/relation 等 testsuite 桥接的 `_async` 侧 | 随 testsuite 子目录化逐步补齐 |

> 补齐顺序建议：先 mock/表达式级（`dml`、`schema`、`backend`），再依赖连接的
> `transactions`（需 skipif 沿用 `conftest.py` 的 scenarios 机制）。

## Snowflake 场景限制说明

- **无真实服务实例**：CI（"Python Test" workflow）不提供 Snowflake 账号，
  `support/snowflake.py` 在既没有 `SNOWFLAKE_ACCOUNT`、又没有安装 `fakesnow`
  时不会注册任何场景，依赖数据库的测试因此整体 skip（根 `conftest.py` 的
  `backend_scenario` 参数集为空）。本地验证以 `pytest --co`（收集 0 error）为准。
- **场景与库名**：场景只提供账户级连接参数（`support/snowflake.py`，可用
  `SNOWFLAKE_SCENARIOS_CONFIG_PATH` 覆盖配置文件）；逻辑库名由测试目录派生，
  `feature/backend/conftest.py` 以目录名注入并只在该 (场景, 库) 的首个测试前
  重置一次，因此同一场景下各目录的表互不干扰。`backend/` 自身不声明 testsuite
  的目录契约（`prepare` / `teardown`）：这些测试只用自己的 `snowflake_backend`
  夹具，不请求 `environment`。
- **fakesnow**：`tests/snowflake_fakesnow/`、`tests/mock/` 提供模拟场景
  用于可离线运行的测试。
- **mock**：`backend/backend/test_backend_mock.py` 通过 patch `snowflake.connector` 验证行为，不建连接。
- **异步**：`AsyncSnowflakeBackend` 基于 `asyncio.run_in_executor()`，无原生异步驱动；
  其行为由同步路径 + mock 间接覆盖。
