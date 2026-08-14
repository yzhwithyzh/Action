#!/bin/bash

# 报告规范校验 Worker 启动脚本
# 用途：后台拉起 tools/checklist_worker_tool 常驻 worker（Redis 队列驱动），
#       它是官网「报告助手第三步」的算力后端 —— 不跑它，前台提交后会一直停在「校验中」
#
# 拉的是同目录的 start_checklist_worker.py（等价于 `python -m tools.checklist_worker_tool`，
# 多一层 sys.path 与信号兜底），与 start_srd_worker.sh 同一种形态。
#
# 可用环境变量：
#   APP_ENV                     运行环境，决定读哪个 .env（默认 dev → .env.dev）
#   CHECKLIST_WORKER_PYTHON     Python 解释器（默认用 action-backend/.venv）
#   CHECKLIST_WORKER_ENV_FILE   worker 自己的环境文件（默认 action-backend/.env.checklist-worker）

set -u

echo "========================================"
echo "Checklist Review Worker"
echo "启动中..."
echo "========================================"

# shellcheck source=_checklist_worker_common.sh
. "$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )/_checklist_worker_common.sh"

checklist_load_env_file
checklist_resolve_python

# 运行环境：config/env.py 靠 --env 参数选 .env 文件，光设 APP_ENV 会被它覆盖成 dev，必须显式传参。
# worker 要连库取 checklist 条目与 ai_models 模型池，这里指的库必须和后端服务是同一套。
APP_ENV="${APP_ENV:-dev}"

if [ ! -x "${PYTHON_PATH}" ]; then
    echo "❌ 找不到可用的 Python 解释器：${PYTHON_PATH:-<空>}"
    echo "   请用 CHECKLIST_WORKER_PYTHON=/path/to/python 指定"
    exit 1
fi

# Worker 启动脚本
WORKER_SCRIPT="${BACKEND_DIR}/start_checklist_worker.py"

if [ ! -f "${WORKER_SCRIPT}" ]; then
    echo "❌ 找不到启动脚本：${WORKER_SCRIPT}"
    exit 1
fi

mkdir -p "${LOG_DIR}"

# 检查是否已经在运行
if [ -f "${PID_FILE}" ]; then
    OLD_PID=$(cat "${PID_FILE}")
    if checklist_is_worker_pid "${OLD_PID}"; then
        echo "❌ Worker 已在运行中 (PID: ${OLD_PID})"
        echo "   如需重启，请执行 ./restart_checklist_worker.sh"
        exit 1
    else
        echo "⚠️  发现残留 PID 文件，已清理"
        rm -f "${PID_FILE}"
    fi
fi

echo "▶️  解释器: ${PYTHON_PATH}"
echo "▶️  运行环境: ${APP_ENV}（.env.${APP_ENV}）"
echo "▶️  启动 Worker Service..."

# PYTHONPATH 指向 action-backend：worker 取条目与模型池时要 `import config.database`
export PYTHONPATH="${BACKEND_DIR}${PYTHONPATH:+:${PYTHONPATH}}"

nohup "${PYTHON_PATH}" "${WORKER_SCRIPT}" --env "${APP_ENV}" \
    > "${OUT_LOG}" 2> "${ERR_LOG}" &

WORKER_PID=$!
echo ${WORKER_PID} > "${PID_FILE}"

# 等 3 秒：worker 启动时要连 Redis，连不上会立刻退出，这里能当场发现
sleep 3

if ps -p ${WORKER_PID} > /dev/null 2>&1; then
    echo "✅ Worker 启动成功 (PID: ${WORKER_PID})"
    echo ""
    echo "📋 日志文件："
    echo "   进程日志: ${RUN_LOG}"
    echo "   标准输出: ${OUT_LOG}"
    echo "   标准错误: ${ERR_LOG}"
    echo ""
    echo "📌 管理命令："
    echo "   查看日志: tail -f ${RUN_LOG}"
    echo "   查看状态: ./status_checklist_worker.sh"
    echo "   停止服务: ./stop_checklist_worker.sh"
    echo "   重启服务: ./restart_checklist_worker.sh"
else
    echo "❌ Worker 启动失败，请查看日志："
    echo "   ${ERR_LOG}"
    tail -n 20 "${ERR_LOG}" 2>/dev/null | sed 's/^/   /'
    rm -f "${PID_FILE}"
    exit 1
fi

echo "========================================"
