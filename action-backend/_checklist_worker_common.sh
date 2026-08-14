#!/bin/bash

# 报告规范校验 Worker 运维脚本的公共部分 —— 由 start/stop/status 三个脚本 source，
# 不要直接执行。路径、解释器、PID 判定只有一份，改一处三个脚本一起生效。
#
# 与 _srd_worker_common.sh 是同一种形态的两份文件，刻意不合并：两个 worker 的队列名、
# 环境变量前缀、日志目录、优雅关闭时长各不相同，合成一份就得靠参数传来传去，
# 而运维脚本被 source 时最不该出现的就是「传错了参数守错了队列」。

# 工作目录固定为 action-backend（worker 的模块路径 tools.checklist_worker_tool 依赖于此）
BACKEND_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "${BACKEND_DIR}" || exit 1

# 日志与 PID：与 worker 自身的日志（checklist_worker_tool.log）放在同一个目录，排障不用两处找
LOG_DIR="${BACKEND_DIR}/tools/checklist_worker_tool/logs"
RUN_LOG="${LOG_DIR}/checklist_worker_tool.log"
OUT_LOG="${LOG_DIR}/checklist_worker.out.log"
ERR_LOG="${LOG_DIR}/checklist_worker.err.log"
PID_FILE="${LOG_DIR}/checklist_worker.pid"

# worker 自己的配置（CHECKLIST_WORKER_*）走进程环境变量，**不读 .env.${APP_ENV}**：
# 那份文件是 `KEY = 'value'` 的 dotenv 语法（bash source 不了），而且 WorkerConfig 在
# config.env 被 import 之前就已经定型。要改 Redis/队列/并发，写在下面这个文件里
# （纯 KEY=VALUE 的 shell 语法，等价于 README 里 systemd 的 EnvironmentFile；
# 见 .env.checklist-worker.example）。
# ⚠️ 后端进程要拿到同一份 CHECKLIST_WORKER_REDIS_*/QUEUE_NAME，否则一个投一条队列、
#    一个守另一条，官网提交的校验会永远排队没人取。
checklist_load_env_file() {
    local env_file="${CHECKLIST_WORKER_ENV_FILE:-${BACKEND_DIR}/.env.checklist-worker}"
    if [ -f "${env_file}" ]; then
        echo "▶️  载入环境文件: ${env_file}"
        set -a
        # shellcheck disable=SC1090
        . "${env_file}"
        set +a
    fi
}

# 解释器：优先 CHECKLIST_WORKER_PYTHON，其次 action-backend 里的 venv
checklist_resolve_python() {
    if [ -n "${CHECKLIST_WORKER_PYTHON:-}" ]; then
        PYTHON_PATH="${CHECKLIST_WORKER_PYTHON}"
    elif [ -x "${BACKEND_DIR}/.venv/bin/python" ]; then
        PYTHON_PATH="${BACKEND_DIR}/.venv/bin/python"
    elif [ -x "${BACKEND_DIR}/.venv/Scripts/python.exe" ]; then
        # Git Bash 下本地试跑用；正式部署都是上面那条 POSIX 路径
        PYTHON_PATH="${BACKEND_DIR}/.venv/Scripts/python.exe"
    else
        PYTHON_PATH="$(command -v python3 || command -v python)"
    fi
}

# PID 是不是真的 checklist worker。
# 只判「进程还活着」不够：worker 崩过之后 PID 会被系统复用给别的进程，
# stop 脚本就会去 kill 一个无关进程。所以再核一次命令行。
# 匹配 `checklist_worker` 而不是完整脚本名：两种起法都要认 ——
# `start_checklist_worker.py`（本套脚本）与 `python -m tools.checklist_worker_tool`（systemd 示例）。
# Git Bash 自带的 msys ps 不支持 `-o`，拿不到命令行时退回「活着就算」——
# 那是本地试跑的场景，不值得为它把脚本判成「未运行」。
checklist_is_worker_pid() {
    local pid="$1" args
    [ -n "${pid}" ] || return 1
    ps -p "${pid}" > /dev/null 2>&1 || return 1
    args="$(ps -p "${pid}" -o args= 2>/dev/null)"
    [ -n "${args}" ] || return 0
    case "${args}" in
        *checklist_worker*) return 0 ;;
        *) return 1 ;;
    esac
}
