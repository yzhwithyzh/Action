#!/bin/bash

# 报告助手 AI Worker（一键优化 · 整篇成文） 停止脚本
# 用途：优雅停止 tools/report_ai_worker_tool 常驻 worker
#
# SIGTERM 后 worker 不会立刻退：它先停止取新任务，再等在跑的任务自然结束
# （上限 = REPORT_AI_WORKER_SHUTDOWN_TIMEOUT，默认 300s）。所以这里默认等 330s ——
# 一次整篇成文是逐章的多次模型调用，等不到就 kill -9 等于把用户正在跑的任务从中间打断，
# 打断一键优化只会丢掉还没写回任务状态的那几条，打断整篇成文则整篇白跑。
#
# 可用环境变量：
#   REPORT_AI_WORKER_STOP_WAIT  最长等待秒数（默认 330）

set -u

echo "========================================"
echo "Report AI Worker"
echo "停止中..."
echo "========================================"

# shellcheck source=_report_ai_worker_common.sh
. "$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )/_report_ai_worker_common.sh"

MAX_WAIT="${REPORT_AI_WORKER_STOP_WAIT:-330}"

if [ ! -f "${PID_FILE}" ]; then
    echo "❌ 未找到 PID 文件，Worker 可能未在运行"
    echo "   ${PID_FILE}"
    exit 1
fi

WORKER_PID=$(cat "${PID_FILE}")

if ! ps -p "${WORKER_PID}" > /dev/null 2>&1; then
    echo "❌ Worker 进程不存在 (PID: ${WORKER_PID})"
    echo "   清理残留 PID 文件..."
    rm -f "${PID_FILE}"
    exit 1
fi

if ! report_ai_is_worker_pid "${WORKER_PID}"; then
    echo "❌ PID ${WORKER_PID} 不是 Report AI Worker（进程已退出、PID 被复用），拒绝 kill"
    echo "   清理残留 PID 文件..."
    rm -f "${PID_FILE}"
    exit 1
fi

echo "▶️  发送 SIGTERM 信号到 Worker (PID: ${WORKER_PID})..."
echo "   worker 会先停止取新任务，再等在跑的任务收尾（最长 ${MAX_WAIT}s）"
kill -TERM ${WORKER_PID}

WAIT_TIME=0
while ps -p ${WORKER_PID} > /dev/null 2>&1; do
    if [ ${WAIT_TIME} -ge ${MAX_WAIT} ]; then
        echo "⚠️  Worker 未在 ${MAX_WAIT} 秒内退出，强制终止..."
        kill -9 ${WORKER_PID}
        sleep 1
        break
    fi

    echo "   等待 Worker 优雅关闭... (${WAIT_TIME}s/${MAX_WAIT}s)"
    sleep 5
    WAIT_TIME=$((WAIT_TIME + 5))
done

if ps -p ${WORKER_PID} > /dev/null 2>&1; then
    echo "❌ Worker 停止失败，进程仍在运行"
    exit 1
else
    echo "✅ Worker 已成功停止"
    rm -f "${PID_FILE}"
fi

echo "========================================"
