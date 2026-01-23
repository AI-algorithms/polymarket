#!/bin/bash

# Polymarket Quant - 一键启动脚本
# 产品级启动体验

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# 清屏
clear

# Logo
echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║                                                               ║"
echo "║   📊  ${BOLD}POLYMARKET QUANT${NC}${BLUE}                                       ║"
echo "║       Professional Copy Trading System                       ║"
echo "║                                                               ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# 进度条函数
progress_bar() {
    local duration=$1
    local steps=20
    local sleep_time=$(echo "scale=3; $duration / $steps" | bc)
    
    printf "["
    for ((i=0; i<$steps; i++)); do
        printf "▓"
        sleep $sleep_time 2>/dev/null || sleep 0.1
    done
    printf "] Done!\n"
}

# 检查步骤函数
check_step() {
    local step_name=$1
    local step_num=$2
    echo -e "${CYAN}[$step_num/5]${NC} $step_name"
}

# Step 1: 虚拟环境
check_step "Checking virtual environment..." "1"
if [ ! -d "venv" ]; then
    echo -e "    ${YELLOW}→ Creating virtual environment...${NC}"
    python3 -m venv venv
    echo -e "    ${GREEN}✓ Virtual environment created${NC}"
else
    echo -e "    ${GREEN}✓ Virtual environment exists${NC}"
fi

# 激活虚拟环境
source venv/bin/activate

# Step 2: 依赖检查
check_step "Checking dependencies..." "2"
if ! python -c "import streamlit; import plotly; import pandas" 2>/dev/null; then
    echo -e "    ${YELLOW}→ Installing dependencies...${NC}"
    pip install -q --upgrade pip
    pip install -q -r requirements.txt
    echo -e "    ${GREEN}✓ Dependencies installed${NC}"
else
    echo -e "    ${GREEN}✓ All dependencies available${NC}"
fi

# Step 3: 系统检查
check_step "Running system check..." "3"
if python test_system.py > /dev/null 2>&1; then
    echo -e "    ${GREEN}✓ All systems operational${NC}"
else
    echo -e "    ${YELLOW}→ Running diagnostics...${NC}"
    python test_system.py 2>&1 | tail -5
fi

# Step 4: 配置检查
check_step "Checking configuration..." "4"
if [ -f ".env" ]; then
    echo -e "    ${GREEN}✓ Configuration file found${NC}"
else
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo -e "    ${YELLOW}→ Created .env from example${NC}"
    else
        echo -e "    ${GREEN}✓ Using default configuration${NC}"
    fi
fi

# Step 5: 启动服务
check_step "Starting dashboard..." "5"
echo ""

# 启动信息
echo -e "${PURPLE}════════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${BOLD}🚀 Dashboard is starting...${NC}"
echo ""
echo -e "  ${CYAN}Local URL:${NC}    http://localhost:8501"
echo -e "  ${CYAN}Network URL:${NC}  http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost"):8501"
echo ""
echo -e "  ${YELLOW}Press Ctrl+C to stop the server${NC}"
echo ""
echo -e "${PURPLE}════════════════════════════════════════════════════════════════${NC}"
echo ""

# 启动 Streamlit（静默模式，减少输出）
streamlit run src/dashboard/app.py \
    --server.headless true \
    --browser.gatherUsageStats false \
    --theme.base dark \
    --theme.primaryColor "#3b82f6" \
    --theme.backgroundColor "#0f172a" \
    --theme.secondaryBackgroundColor "#1e293b" \
    --theme.textColor "#f1f5f9" \
    2>/dev/null
