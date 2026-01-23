"""
数据库集成示例
演示如何使用数据库存储和查询交易者数据
"""
import sys
sys.path.append('src')

from api.polymarket_client import PolymarketClient
from analytics.trader_analyzer import TraderAnalyzer
from data.dao import TraderDAO

print("=" * 60)
print("数据库集成示例")
print("=" * 60)

# 示例：分析交易者并保存到数据库
example_address = "0x1234567890abcdef1234567890abcdef12345678"

print(f"\n1. 分析交易者: {example_address}")
client = PolymarketClient()
analyzer = TraderAnalyzer(min_trades=20, min_win_rate=0.90)

# 模拟数据（实际使用时从 API 获取）
mock_trades = [
    {"market": "market1", "side": "BUY", "size": 100, "price": 0.5},
    {"market": "market1", "side": "SELL", "size": 100, "price": 0.8},
    {"market": "market2", "side": "BUY", "size": 50, "price": 0.3},
    {"market": "market2", "side": "SELL", "size": 50, "price": 0.7},
]
mock_positions = []

analysis = analyzer.analyze_trader(mock_trades, mock_positions)
analysis['is_qualified'] = analyzer.is_qualified_trader(analysis)

print(f"   胜率: {analysis['win_rate']:.1%}")
print(f"   总盈利: ${analysis['overall_pnl']:.2f}")
print(f"   是否合格: {'是' if analysis['is_qualified'] else '否'}")

# 保存到数据库
print("\n2. 保存到数据库...")
try:
    trader = TraderDAO.save_trader(example_address, analysis)
    print(f"   ✓ 已保存交易者: {trader.address}")
except Exception as e:
    print(f"   ✗ 保存失败: {e}")
    print(f"   提示: 请先运行 'python scripts/init_db.py' 初始化数据库")
    sys.exit(1)

# 查询高胜率交易者
print("\n3. 查询高胜率交易者...")
try:
    qualified_traders = TraderDAO.get_qualified_traders(min_win_rate=0.90)
    print(f"   找到 {len(qualified_traders)} 个高胜率交易者")

    for trader in qualified_traders[:5]:  # 显示前5个
        print(f"   - {trader.address[:10]}... 胜率: {trader.win_rate:.1%}, 盈利: ${trader.overall_pnl:.2f}")
except Exception as e:
    print(f"   ✗ 查询失败: {e}")

print("\n" + "=" * 60)
print("✓ 示例完成！")
print("=" * 60)
print("\n更多用法请参考: DATABASE.md")
