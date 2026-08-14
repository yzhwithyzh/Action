#!/bin/bash

# 报告规范校验 Worker 状态脚本
# 用途：看进程活没活、队列里还压着几个任务、最近的日志
# 退出码：0 = 运行中，1 = 未运行（可直接给监控脚本用）

set -u

echo "========================================"
echo "Checklist Review Worker"
echo "运行状态"
echo "========================================"

# shellcheck source=_checklist_worker_common.sh
. "$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )/_checklist_worker_common.sh"

checklist_load_env_file > /dev/null
checklist_resolve_python

RUNNING=0

if [ -f "${PID_FILE}" ]; then
    WORKER_PID=$(cat "${PID_FILE}")
    if checklist_is_worker_pid "${WORKER_PID}"; then
        RUNNING=1
        echo "✅ 运行中 (PID: ${WORKER_PID})"
        ps -p "${WORKER_PID}" -o pid=,etime=,%cpu=,%mem= 2>/dev/null | sed 's/^/   /'
    else
        echo "❌ 未运行（PID 文件里的 ${WORKER_PID} 已失效，可直接 ./start_checklist_worker.sh）"
    fi
else
    echo "❌ 未运行（无 PID 文件）"
fi

# 队列长度：CLI 用的是同一份 CONFIG，环境变量对不上时这里读到的就是 0，
# 正好能验证「后端与 worker 是不是同一条队列」
echo ""
if [ -x "${PYTHON_PATH}" ]; then
    export PYTHONPATH="${BACKEND_DIR}${PYTHONPATH:+:${PYTHONPATH}}"
    if QUEUE_INFO=$("${PYTHON_PATH}" -m tools.checklist_worker_tool.cli queue 2>&1); then
        echo "📦 队列: ${QUEUE_INFO}"
    else
        echo "⚠️  队列查询失败（Redis 连不上？依赖没装？）"
        echo "${QUEUE_INFO}" | grep -v '^[[:space:]]*$' | tail -n 3 | sed 's/^/   /'
    fi
fi

echo ""
if [ -f "${RUN_LOG}" ]; then
    echo "📋 最近日志 (${RUN_LOG})："
    tail -n 15 "${RUN_LOG}" | cut -c1-200 | sed 's/^/   /'
else
    echo "📋 暂无进程日志：${RUN_LOG}"
fi

if [ -s "${ERR_LOG}" ]; then
    echo ""
    echo "⚠️  标准错误非空 (${ERR_LOG})，最后 5 行："
    tail -n 5 "${ERR_LOG}" | sed 's/^/   /'
fi

echo "========================================"

[ ${RUNNING} -eq 1 ] || exit 1
