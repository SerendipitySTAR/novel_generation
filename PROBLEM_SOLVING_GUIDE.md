# 问题解决指南

本指南帮助您解决小说生成系统中的两个主要问题：

## 🔧 问题1: 人物记忆混杂

### 问题描述
不同故事之间的人物记忆出现混杂，导致角色信息错乱。

### 解决方案

#### 1. 诊断问题
```bash
python -m src.utils.problem_solver diagnose
```

#### 2. 查看所有小说
```bash
python -m src.utils.problem_solver list
```

#### 3. 修复特定小说的记忆问题
```bash
# 交互式修复
python -m src.utils.problem_solver fix --novel-id 1

# 非交互式修复（自动清理）
python -m src.utils.problem_solver fix --novel-id 1 --non-interactive
```

#### 4. 修复所有记忆问题
```bash
python -m src.utils.problem_solver fix
```

### 手动管理选项

#### 删除特定角色
```python
from src.utils.memory_manager import MemoryManager

memory_manager = MemoryManager()
# 删除角色ID为5的角色
memory_manager.delete_specific_character(5)
```

#### 更新角色信息
```python
# 更新角色信息
memory_manager.update_character_info(
    character_id=5,
    name="新名字",
    description="新描述"
)
```

#### 清除整个小说的记忆
```python
# 清除角色和知识库，保留章节
result = memory_manager.clear_novel_memory(
    novel_id=1,
    clear_characters=True,
    clear_chapters=False,
    clear_knowledge_base=True
)
```

## 🔄 问题2: 循环导致系统卡死

### 问题描述
工作流程陷入无限循环，占用大量CPU资源，导致系统卡死。

### 已实施的解决方案

#### 1. 循环保护机制
- **最大迭代次数限制**: 每个小说的章节生成循环最多执行 `章节数 × 3` 次迭代
- **异常状态检测**: 检测章节号是否异常增长
- **安全退出条件**: 当检测到异常时强制退出循环

#### 2. 递归限制优化
- **动态计算**: 根据章节数动态计算递归限制
- **缓冲区**: 添加额外的缓冲区以处理重试情况

#### 3. 监控和诊断
```bash
# 检查系统健康状态
python -m src.utils.problem_solver health
```

#### 4. 紧急停止
```bash
# 如果系统陷入循环，执行紧急停止
python -m src.utils.problem_solver emergency-stop
```

### 预防措施

#### 1. 设置合理的参数
```python
# 在运行工作流程时设置较小的章节数进行测试
user_input = {
    "theme": "测试主题",
    "chapters": 2,  # 先用较小的数字测试
    "words_per_chapter": 500
}
```

#### 2. 监控执行过程
- 观察控制台输出中的循环计数器
- 注意 "SAFETY" 相关的警告信息
- 如果看到重复的循环信息，立即停止程序

#### 3. 使用超时机制
```python
import signal
import time

def timeout_handler(signum, frame):
    raise TimeoutError("工作流程执行超时")

# 设置30分钟超时
signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm(1800)  # 30分钟

try:
    result = workflow_manager.run_workflow(user_input)
finally:
    signal.alarm(0)  # 取消超时
```

## 🛠️ 高级故障排除

### 1. 数据库问题
```python
# 检查数据库连接
from src.persistence.database_manager import DatabaseManager
db = DatabaseManager()
novels = db.get_all_novels()  # 如果失败，说明数据库有问题
```

### 2. 知识库问题
```python
# 检查知识库状态
from src.knowledge_base.knowledge_base_manager import KnowledgeBaseManager
kb = KnowledgeBaseManager()
collections = kb.list_collections()
print(f"现有集合: {collections}")
```

### 3. 内存泄漏检查
```bash
# 使用系统监控工具
top -p $(pgrep -f python)
# 或
htop
```

### 4. 日志分析
- 查看控制台输出中的错误信息
- 注意内存使用情况
- 监控CPU使用率

## 📋 最佳实践

### 1. 定期清理
- 每次开始新项目前运行诊断
- 定期清理不需要的小说数据
- 备份重要的记忆数据

### 2. 测试策略
- 先用小规模参数测试（1-2章节）
- 逐步增加复杂度
- 在生产环境前充分测试

### 3. 监控策略
- 设置执行超时
- 监控系统资源使用
- 保持日志记录

### 4. 备份策略
```bash
# 导出重要小说的记忆备份
python -m src.utils.problem_solver fix --novel-id 1
# 选择选项4进行备份
```

## 🆘 紧急情况处理

### 如果系统完全卡死：
1. **强制终止进程**:
   ```bash
   pkill -f "python.*novel"
   ```

2. **检查系统资源**:
   ```bash
   free -h  # 检查内存
   df -h    # 检查磁盘空间
   ```

3. **清理临时文件**:
   ```bash
   rm -rf ./chroma_db/*  # 清理知识库（谨慎操作）
   ```

4. **重启系统**（最后手段）

### 数据恢复：
如果数据丢失，可以从备份文件恢复：
```python
import json
from src.utils.memory_manager import MemoryManager

# 加载备份数据
with open('novel_1_memory_backup.json', 'r') as f:
    backup_data = json.load(f)

# 手动恢复数据（需要自定义实现）
```

## 📞 获取帮助

如果问题仍然存在：
1. 运行完整诊断: `python -m src.utils.problem_solver diagnose`
2. 收集错误日志和系统信息
3. 检查是否有足够的磁盘空间和内存
4. 考虑降低并发度或减少章节数量

记住：**预防胜于治疗**。定期维护和监控可以避免大多数问题。
