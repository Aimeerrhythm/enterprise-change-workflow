## TDD 编码模式

> 测试先行，实现在后。适用于所有新增功能和 Bug 修复。

### 测试基础设施

| 组件 | 说明 |
|------|------|
| `{{base_test_class}}` | 测试基类（示例：可自带 `@Transactional` + `@Rollback`，视项目配置而定） |
| H2 内存库 | `schema_all.sql` 自动建表 |
| Embedded Redis | 测试 profile 自动启动，无需外部 Redis |
| Mock RabbitMQ | 消息收发在内存中完成 |
| `JunitFileUtils` | 从 `src/test/resources/mockdata/` 加载 JSON 测试数据 |

### 示例：Bug 修复（库存不足时应拒绝扣减）

**1. RED — 先写失败测试**

```java
// {{test_module}}/src/test/java/.../StockDeductBizServiceTest.java
public class StockDeductBizServiceTest extends {{base_test_class}} {

    @Resource
    private StockDeductBizService stockDeductBizService;

    @Test
    public void testRejectWhenStockInsufficient() {
        // 构造请求：扣减数量 > 库存
        DeductStockRequest request = new DeductStockRequest();
        request.setSkuId(99999L);
        request.setQuantity(100);

        ServiceResult<Void> result = stockDeductBizService.deduct(request);

        assertThat(result.isSuccess()).isFalse();
        assertThat(result.getErrorCode()).isEqualTo("STOCK_INSUFFICIENT");
    }
}
```

运行验证失败：
```bash
mvn test -pl {{test_module}} -Dtest=StockDeductBizServiceTest#testRejectWhenStockInsufficient
# 期望：测试失败，因为功能未实现
```

**2. GREEN — 最少实现让测试通过**

```java
// BizServiceImpl 中添加库存校验
StockDO stock = stockManager.getBySkuId(request.getSkuId());
if (stock == null || stock.getQuantity() < request.getQuantity()) {
    return ServiceResult.fail("STOCK_INSUFFICIENT", "库存不足");
}
```

再次运行：
```bash
mvn test -pl {{test_module}} -Dtest=StockDeductBizServiceTest
# 期望：测试通过
mvn test
# 期望：全量通过，无回归
```

**3. REFACTOR — 绿灯下清理**

提取校验逻辑、改善命名等，保持测试始终通过。

### 示例：新增功能（查询任务详情）

**1. RED**

```java
public class TaskReadBizServiceTest extends {{base_test_class}} {

    @Resource
    private TaskReadBizService taskReadBizService;
    @Resource
    private TaskManager taskManager;

    @Test
    public void testGetTaskDetailReturnsCorrectStatus() {
        // 先通过 Manager 插入测试数据（H2 + 自动回滚）
        TaskDO taskDO = new TaskDO();
        taskDO.setTaskSn("TSK-TEST-001");
        taskDO.setStatus(TaskStatusEnum.PENDING.getCode());
        taskManager.insert(taskDO);

        ServiceResult<TaskDetailResponse> result =
            taskReadBizService.getDetail("TSK-TEST-001");

        assertThat(result.isSuccess()).isTrue();
        assertThat(result.getData().getStatus())
            .isEqualTo(TaskStatusEnum.PENDING.getCode());
    }

    @Test
    public void testGetTaskDetailReturnsFailWhenNotFound() {
        ServiceResult<TaskDetailResponse> result =
            taskReadBizService.getDetail("NON-EXISTENT");

        assertThat(result.isSuccess()).isFalse();
    }
}
```

**2. GREEN → 3. REFACTOR**（同上模式）

### 外部依赖打桩

需要 Mock 外部 Facade 时：

```java
public class QualityCheckBizServiceTest extends {{base_test_class}} {

    @Resource
    private QualityCheckBizService qualityCheckBizService;

    @MockBean
    private GoodsQueryFacade goodsQueryFacade;

    @Test
    public void testQcPassWhenGoodsValid() {
        // 打桩外部依赖
        when(goodsQueryFacade.getBySkuId(anyLong()))
            .thenReturn(ServiceResult.success(mockGoodsResponse()));

        ServiceResult<QcResultResponse> result =
            qualityCheckBizService.executeQc(buildQcRequest());

        assertThat(result.isSuccess()).isTrue();
        assertThat(result.getData().getQcResult()).isEqualTo("PASS");
    }
}
```

### 断言反模式

```java
// BAD — println 不是断言，测试永远"通过"
System.out.println(JSON.toJSONString(result));

// BAD — 只验证非空，不验证内容
Assert.notNull(result, "result is null");

// GOOD — 精确断言业务结果
assertThat(result.isSuccess()).isTrue();
assertThat(result.getData().getOrderSn()).isEqualTo("expected-sn");
assertThat(result.getData().getStatus()).isEqualTo(OrderStatus.CREATED.getCode());
```
