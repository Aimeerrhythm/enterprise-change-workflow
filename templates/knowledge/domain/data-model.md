# {{Domain Name}} 数据模型

> extracted-from-commit: {{COMMIT_HASH}}
> last-verified: {{DATE}}

<!--
用途：本文档描述单个域的数据模型——所有数据库表（DO 类）、
列、关系和状态枚举。AI 助手在进行涉及查询、Schema 或
状态流转的变更前读取此文件以了解持久化层。

填充方法：
1. 对域中的每个 DO 类/数据库表，列出所有列及其 Java 字段名、JDBC 类型和描述。
2. 记录这些表使用的所有枚举类型。
3. 绘制实体关系（哪些表引用哪些表）。
4. 包含状态枚举定义及其整数编码和含义。
-->

---

## 实体总览

<!--
该域中所有实体（表）的快速索引。
-->

| 实体（DO 类） | 表名 | 描述 | 关键业务标识 |
|-------------|------|------|------------|
| {{EntityDO}} | `{{table_name}}` | {{简述}} | {{如 orderSn、entityId}} |
| {{AnotherEntityDO}} | `{{table_name}}` | {{简述}} | {{business_key}} |

---

## 实体详情

### {{EntityDO}} -- {{可读名称}}

**表名**：`{{schema.table_name}}`

<!--
列出所有列。包含：
- 数据库列名（snake_case）
- Java 字段名（camelCase）
- JDBC 类型
- 描述（涉及枚举时标注引用）
-->

| 列名 | Java 字段 | JDBC 类型 | 描述 |
|------|----------|----------|------|
| id | id | BIGINT | 主键 |
| {{column_name}} | {{javaField}} | VARCHAR | {{可读描述}} |
| type | type | INTEGER | 实体类型。见 `{{TypeEnum}}`：{{value1}}-{{meaning1}}、{{value2}}-{{meaning2}} |
| status | status | INTEGER | 实体状态。见下方 `{{StatusEnum}}` |
| version | version | INTEGER | 乐观锁版本号 |
| gmt_created | gmtCreated | TIMESTAMP | 创建时间 |
| gmt_modified | gmtModified | TIMESTAMP | 最后修改时间 |
| feature | feature | TEXT | 扩展 JSON（灵活属性） |

---

### {{AnotherEntityDO}} -- {{可读名称}}

**表名**：`{{schema.table_name}}`

| 列名 | Java 字段 | JDBC 类型 | 描述 |
|------|----------|----------|------|
| id | id | BIGINT | 主键 |
| {{parent_entity}}_id | {{parentEntity}}Id | BIGINT | 外键，关联 {{parent table}} |
| {{column}} | {{field}} | {{type}} | {{description}} |

---

## 状态枚举

<!--
对每个状态枚举，列出所有可能的值及其编码和含义。
如 business-rules.md 中未记录流转规则，在此包含。
-->

### {{StatusEnum}}

| 编码 | 名称 | 描述 |
|------|------|------|
| 1 | `CREATED` | 实体已创建但尚未处理 |
| 2 | `IN_PROGRESS` | 实体正在处理中 |
| 3 | `COMPLETED` | 实体处理完成 |
| 4 | `CANCELLED` | 实体在完成前被取消 |
| {{code}} | `{{NAME}}` | {{description}} |

### {{TypeEnum}}

| 编码 | 名称 | 描述 |
|------|------|------|
| 1 | `{{TYPE_A}}` | {{类型 A 的描述}} |
| 2 | `{{TYPE_B}}` | {{类型 B 的描述}} |

---

## 其他枚举

<!--
列出该域表中使用的其他枚举（如优先级、分类类型、标志枚举）。
-->

### {{OtherEnum}}

| 编码 | 名称 | 描述 |
|------|------|------|
| {{code}} | `{{NAME}}` | {{description}} |

---

## 实体关系

<!--
描述实体之间的关系。使用文本 ER 图或关系表。
标注基数（1:1、1:N、M:N）。
-->

```
{{ParentEntity}} 1 ---< N {{ChildEntity}}     （一个父实体对应多个子实体）
{{EntityA}} 1 ---< N {{EntityB}} ---< N {{EntityC}}
{{EntityX}} >--- 1 {{SharedEntity}}            （多个 X 引用同一个共享实体）
```

### 关系详情

| 父实体 | 子实体 | 关系 | 关联键 | 描述 |
|-------|-------|------|-------|------|
| {{ParentDO}} | {{ChildDO}} | 1:N | {{parent_sn}} | {{描述，如 "一个订单包含多个明细行"}} |
| {{EntityA}} | {{EntityB}} | M:N | {{join_table}} | {{描述}} |

---

## 索引（关键业务索引）

<!--
可选：列出影响查询模式或开发者应了解的性能考量的重要数据库索引。
-->

| 表 | 索引名 | 列 | 类型 | 用途 |
|----|----|----|----|------|
| {{table}} | {{idx_name}} | {{col1, col2}} | UNIQUE / BTREE | {{此索引存在的原因}} |

---

## 维护指南

1. **新增列**：同时更新本文档和对应的 MyBatis XML Mapper。
2. **新增枚举值**：更新枚举类、本文档以及所有使用该枚举的 switch/if-else 逻辑。
3. **变更关系**：评估对所有关联查询的影响；更新本文档的 ER 章节。
4. **状态枚举变更**：与 business-rules.md 中的状态机章节协调。
