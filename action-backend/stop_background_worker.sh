#!/bin/bash

# 研究背景生成 Worker 停止脚本
# 用途：优雅停止 tools/background_worker_tool 常驻 worker
#
# SIGTERM 后 worker 不会立刻退：它先停止取新任务，再等在跑的生成任务自然结束
# （上限 = BACKGROUND_WORKER_SHUTDOWN_TIMEOUT，默认 300s）。所以这里默认等 330s ——
# 一次生成是九次模型调用外加若干次向量检索，等不到就 kill -9 等于把用户正在跑的任务从中间打断，
# 而稿件只在队列与进程里流转、不落库，打断了就真没了。
#
# 可用环境变量：
#   BACKGROUND_WORKER_STOP_WAIT  最长等待秒数（默认 330）

set -u

echo "========================================"
echo "Background Generation Worker"
echo "停止中..."
echo "========================================"

# shellcheck source=_background_worker_common.sh
. "$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )/_background_worker_common.sh"

MAX_WAIT="${BACKGROUND_WORKER_STOP_WAIT:-330}"

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

if ! background_is_worker_pid "${WORKER_PID}"; then
    echo "❌ PID ${WORKER_PID} 不是 Background Worker（进程已退出、PID 被复用），拒绝 kill"
    echo "   清理残留 PID 文件..."
    rm -f "${PID_FILE}"
    exit 1
fi

echo "▶️  发送 SIGTERM 信号到 Worker (PID: ${WORKER_PID})..."
echo "   worker 会先停止取新任务，再等在跑的生成任务收尾（最长 ${MAX_WAIT}s）"
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
