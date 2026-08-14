#!/bin/bash

# 报告规范校验 Worker 重启脚本
# 用途：停止 + 启动，环境变量（APP_ENV / CHECKLIST_WORKER_*）会原样传给两个子脚本

set -u

echo "========================================"
echo "Checklist Review Worker"
echo "重启中..."
echo "========================================"

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "▶️  步骤 1/2: 停止 Worker..."
"${SCRIPT_DIR}/stop_checklist_worker.sh"

# 停止失败大多是「本来就没跑」（没有 PID 文件 / 进程已退），继续启动即可；
# 真正卡住的情况会在下一步被 start 脚本的「已在运行中」拦下来
if [ $? -ne 0 ]; then
    echo "⚠️  停止 Worker 时出现问题，继续尝试启动..."
fi

echo ""
echo "⏳ 等待 2 秒..."
sleep 2

echo ""
echo "▶️  步骤 2/2: 启动 Worker..."
"${SCRIPT_DIR}/start_checklist_worker.sh"

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Worker 重启成功"
else
    echo ""
    echo "❌ Worker 重启失败"
    exit 1
fi

echo "========================================"
