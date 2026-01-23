# Polymarket 量化交易平台

Polymarket 量化交易系统。

## 核心功能

### 1. 高胜率用户识别
- 实时监控 Polymarket 用户交易数据
- 筛选 90%+ 胜率用户
- 多维度验证（交易次数、盈利稳定性、仓位合理性）

### 2. 智能跟单策略
- 实时跟踪目标用户的新交易
- 基于 Kelly 公式动态调整仓位
- 多用户组合分散风险

### 3. 风险管理系统
- 单笔最大仓位限制
- 单日亏损熔断
- 相关性风险控制
- 流动性风险评估

### 4. 可视化仪表盘
- 实时监控面板
- 用户画像分析
- 收益归因分析
- 风险暴露视图

## 项目结构

```
polymarket/
  ├── src/
  │   ├── api/polymarket_client.py      # API 客户端
  │   ├── analytics/
  │   │   ├── trader_analyzer.py        # 交易者分析
  │   │   └── trader_scanner.py         # 交易者扫描
  │   ├── strategies/copy_trading.py    # 跟单引擎
  │   ├── utils/risk_manager.py         # 风险管理
  │   └── dashboard/app.py              # 可视化仪表盘
  ├── tests/                            # 单元测试
  ├── scripts/run_system.py             # 启动脚本
  ├── docs/QUICKSTART.md                # 快速开始指南
  ├── requirements.txt                  # 依赖
  ├── Makefile                          # 便捷命令
  └── README.md                         # 项目说明
```

## 快速开始

### 🚀 一键启动（推荐）

```bash
# macOS/Linux
./start.sh

# Windows
start.bat
```

脚本会自动完成：
- ✅ 创建虚拟环境（如果不存在）
- ✅ 安装所有依赖
- ✅ 运行系统测试
- ✅ 启动仪表板

---

### 手动启动（可选）

### 1. 创建虚拟环境并安装依赖
```bash
# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate  # macOS/Linux
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 2. 运行系统测试
```bash
# 激活虚拟环境后
python test_system.py
```

### 3. 启动可视化仪表板
```bash
# 方式 1：使用主程序
python main.py dashboard

# 方式 2：直接运行 Streamlit
streamlit run src/dashboard/app.py
```

仪表板将在浏览器中自动打开（默认 http://localhost:8501）

### 4. 使用仪表板分析交易者

#### 单个交易者分析
1. 在"交易者分析"标签页
2. 输入交易者的钱包地址（如 `0x1234...`）
3. 点击"分析"按钮
4. 查看该交易者的胜率、盈利等指标

#### 批量分析
1. 在"排行榜"标签页
2. 输入多个交易者地址（每行一个）
3. 点击"批量分析"
4. 系统会自动筛选出高胜率交易者

#### 5. 命令行扫描（可选）
```bash
# 创建地址列表文件
echo "0x1234567890abcdef1234567890abcdef12345678" > addresses.txt

# 运行扫描
python main.py scan --file addresses.txt

# 结果保存在 data/qualified_traders.json
```

#### 风险警告

⚠️ **重要提示**：
- 本系统仅供学习研究使用
- 预测市场具有高风险，过往表现不代表未来收益
- 请勿投入超过你承受范围的资金
- 务必进行充分的回测验证
- 建议从小仓位开始测试

## 核心策略逻辑

### 高胜率用户筛选标准

| 指标 | 要求 | 说明 |
|------|------|------|
| 胜率 | ≥ 90% | 历史交易获胜比例 |
| 交易次数 | ≥ 20 | 最少交易样本量 |
| 总盈利 | > 0 | 必须为正收益 |
| 最大回撤 | < 30% | 风险控制能力 |
| 平均仓位 | 合理 | 避免极端 all-in |

### Kelly 公式应用

```
f* = (p × b - q) / b × kelly_fraction
```

- `p`: 胜率（如 0.90）
- `q`: 败率（1 - p）
- `b`: 赔率（odds）
- `kelly_fraction`: 保守系数（0.5 = Half-Kelly）

#### 风险控制规则

1. **单笔限制**：单笔投注 ≤ 总资金 × Kelly 结果
2. **日亏损熔断**：单日累计亏损达 MAX_DAILY_LOSS 时停止交易
3. **用户分散**：同时跟随 5-10 个高胜率用户，避免单点依赖
4. **流动性检查**：只投注流动性充足的市场（volume > 10k）

#### 技术栈

- **数据获取**：aiohttp + requests
- **数据分析**：pandas + numpy + scipy
- **Web3 交互**：web3.py + eth-account
- **可视化**：plotly + dash
- **数据库**：PostgreSQL + SQLAlchemy
- **测试**：pytest

#### 开发计划

- [x] 项目初始化
- [x] Polymarket API 封装
- [x] 用户数据采集
- [x] 高胜率用户识别算法
- [x] 跟单策略引擎（基础版）
- [x] 风险管理系统（基础版）
- [x] 可视化仪表盘
- [ ] 实时监控和自动跟单
- [ ] 回测框架
- [ ] 单元测试覆盖

### 许可证

MIT License
