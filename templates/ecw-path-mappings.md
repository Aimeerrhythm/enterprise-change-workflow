# 代码路径→域映射 (Code Path Mappings)

> 本文件定义项目源码目录到业务域的映射关系。biz-impact-analysis agent 使用此文件将 diff 中的文件路径定位到业务域。
> 由 /ecw-init 生成初始版本，随项目演进手动维护。

---

## 映射规则

按路径模式匹配，优先匹配更具体的规则。当多条规则匹配同一文件时，**最长路径前缀优先**。

| 路径模式 | 映射规则 |
|---------|---------|
| `{biz_root}/{domain}/` | 按子目录名映射到域（查"业务目录完整映射"表） |
| `{shared_root}/` | 标记为"共享层"，需检查调用方来判断影响域 |
| `{infra_root}/` | 标记为"基础设施层"（外部集成/数据访问） |
| `{common_root}/` | 标记为"横切"，潜在影响所有域 |
| `{interface_root}/` | 按子目录推断域（API 层） |
| `{sql_root}/` | SQL 层变更，按文件名映射对应数据对象所属域 |

<!-- 
  说明：
  - 将上表中的 {biz_root} 替换为你项目的业务代码根目录，如 src/main/java/com/example/biz/
  - {shared_root} 替换为共享服务目录，如 src/main/java/com/example/shared/
  - {infra_root} 替换为基础设施层目录，如 src/main/java/com/example/infra/
  - {common_root} 替换为通用工具层目录，如 src/main/java/com/example/common/
  - {interface_root} 替换为接口层目录，如 src/main/java/com/example/interfaces/
  - {sql_root} 替换为 SQL/Mapper 文件目录，如 src/main/resources/mybatis/mapper/
-->

---

## 业务目录完整映射

> 列出业务代码根目录下所有子目录及其所属域。biz-impact-analysis 使用此表将 diff 文件路径定位到具体域。

| 子目录 | 所属域 |
|--------|--------|
| example-order | order（订单） |
| example-payment | payment（支付） |
| example-user | user（用户） |
<!-- 
  填写说明：
  1. 逐一列出 {biz_root} 下的所有子目录
  2. 映射到 domain-registry.md 中定义的域
  3. 括号内注明子域/功能说明，便于理解
  4. 子目录可以多对一映射到同一个域
  
  示例（电商项目）：
  | order        | order（订单核心）     |
  | cart         | order（购物车）       |
  | checkout     | order（结算）         |
  | payment      | payment（支付）       |
  | refund       | payment（退款）       |
  | inventory    | inventory（库存）     |
  | product      | product（商品）       |
  | pricing      | product（定价）       |
  | user         | user（用户）          |
  | auth         | user（认证）          |
-->

---

## 回调/策略层映射

> 如果项目使用策略模式或回调机制，子目录可能按策略/回调类型组织，需要独立映射。

| 子目录 | 所属域 |
|--------|--------|
<!-- 
  示例：
  | strategy/order   | order    |
  | strategy/payment | payment  |
  | callback/notify  | payment  |
-->

---

## 事件监听器映射

> 如果项目使用事件驱动架构，监听器目录需要独立映射。

| 子目录 | 所属域 |
|--------|--------|
<!-- 
  示例：
  | listener/order       | order       |
  | listener/inventory   | inventory   |
  | listener/common      | 横切         |
-->

---

## 共享层映射规则

> 共享层代码（如 Manager、CoreService）无法仅通过路径确定影响域。以下规则补充按类名前缀推断：

| 类名模式 | 映射域 |
|---------|--------|
<!-- 
  示例：
  | Order*          | order              |
  | Payment*        | payment            |
  | Product*        | product（共享）     |
  | Account*        | account（共享）     |
  | 无法匹配的      | 标记为"共享层"      |
-->

---

## 维护指南

1. **新增业务子目录时**：在"业务目录完整映射"中添加对应行
2. **新增域时**：先在 `domain-registry.md` 注册域，再在此文件添加路径映射
3. **重构目录结构时**：同步更新所有受影响的映射表
4. **验证完整性**：定期检查实际目录结构与映射表的一致性，确保无遗漏
