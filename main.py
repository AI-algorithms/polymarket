"""
Polymarket 高胜率交易者跟单系统 - 主程序入口
"""
import argparse
import sys
from loguru import logger

# 配置日志
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level="INFO",
)
logger.add("logs/polymarket_{time}.log", rotation="1 day", retention="7 days", level="DEBUG")


def run_dashboard():
    """启动仪表板"""
    logger.info("启动 Streamlit 仪表板...")
    import subprocess
    subprocess.run(["streamlit", "run", "src/dashboard/app.py"])


def run_scanner(addresses_file: str):
    """运行交易者扫描器"""
    logger.info(f"开始扫描交易者: {addresses_file}")

    from src.api.polymarket_client import PolymarketClient
    from src.analytics.trader_analyzer import TraderAnalyzer

    client = PolymarketClient()
    analyzer = TraderAnalyzer(min_trades=20, min_win_rate=0.90)

    # 读取地址列表
    with open(addresses_file, 'r') as f:
        addresses = [line.strip() for line in f if line.strip()]

    logger.info(f"共 {len(addresses)} 个地址待分析")

    qualified_traders = []
    for i, address in enumerate(addresses, 1):
        logger.info(f"[{i}/{len(addresses)}] 分析 {address}")
        try:
            trades = client.get_user_trades(address, limit=500)
            positions = client.get_user_positions(address)
            analysis = analyzer.analyze_trader(trades, positions)

            if analyzer.is_qualified_trader(analysis):
                logger.success(f"✓ 高胜率交易者: {address} (胜率: {analysis['win_rate']:.1%})")
                qualified_traders.append({
                    "address": address,
                    **analysis
                })
            else:
                logger.info(f"✗ 不符合条件: {address} (胜率: {analysis['win_rate']:.1%})")
        except Exception as e:
            logger.error(f"分析失败 {address}: {e}")

    logger.info(f"\n扫描完成！找到 {len(qualified_traders)} 个高胜率交易者")

    # 保存结果
    if qualified_traders:
        import json
        output_file = "data/qualified_traders.json"
        with open(output_file, 'w') as f:
            json.dump(qualified_traders, f, indent=2)
        logger.success(f"结果已保存到: {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Polymarket 高胜率交易者跟单系统")
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # 仪表板命令
    subparsers.add_parser("dashboard", help="启动可视化仪表板")

    # 扫描命令
    scanner_parser = subparsers.add_parser("scan", help="扫描高胜率交易者")
    scanner_parser.add_argument("--file", required=True, help="交易者地址列表文件")

    args = parser.parse_args()

    if args.command == "dashboard":
        run_dashboard()
    elif args.command == "scan":
        run_scanner(args.file)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
