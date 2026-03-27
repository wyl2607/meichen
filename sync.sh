#!/usr/bin/env bash
# sync.sh — 一键将本地代码+密钥同步到 VPS，并重启 pipeline
#
# 使用方法（本地运行）：
#   bash sync.sh           # 完整同步：代码 + 密钥 + 重启服务
#   bash sync.sh --code    # 仅同步代码（git pull on VPS）
#   bash sync.sh --secrets # 仅同步密钥（.env + credentials.json）
#
# 前提：Tailscale 已连接，VPS Tailscale IP = 100.125.28.79

set -euo pipefail

VPS_HOST="root@100.125.28.79"
VPS_DIR="/opt/meichen"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

log() { echo "[$(date '+%H:%M:%S')] $*"; }

sync_code() {
    log "▶ 推送代码到 GitHub..."
    cd "$PROJECT_DIR"
    git add -A
    if git diff --cached --quiet; then
        log "  代码无变更，跳过 push"
    else
        git commit -m "chore: sync $(date '+%Y-%m-%d %H:%M')" || true
        git push origin main
        log "  GitHub push 完成"
    fi

    log "▶ VPS 从 GitHub 拉取最新代码..."
    ssh "$VPS_HOST" "cd $VPS_DIR && git pull origin main"
    log "  VPS git pull 完成"
}

sync_secrets() {
    log "▶ 通过 Tailscale 加密隧道传输密钥文件..."
    scp "$PROJECT_DIR/.env" "$PROJECT_DIR/credentials.json" "$VPS_HOST:$VPS_DIR/"
    ssh "$VPS_HOST" "chmod 600 $VPS_DIR/.env $VPS_DIR/credentials.json"
    log "  密钥文件同步完成（权限已加固）"
}

restart_service() {
    log "▶ 重启 VPS pipeline 服务..."
    ssh "$VPS_HOST" "systemctl restart meichen-scout.service && systemctl status meichen-scout.service --no-pager | head -5"
    log "  服务重启完成"
}

show_vps_log() {
    log "▶ VPS 最新日志（后20行）："
    ssh "$VPS_HOST" "tail -20 $VPS_DIR/logs/pipeline.log 2>/dev/null || echo '暂无日志'"
}

# ── 参数解析 ────────────────────────────────────────────
case "${1:-all}" in
    --code)
        sync_code
        restart_service
        ;;
    --secrets)
        sync_secrets
        restart_service
        ;;
    --logs)
        show_vps_log
        ;;
    --status)
        ssh "$VPS_HOST" "systemctl status meichen-scout.service --no-pager"
        ;;
    all|*)
        sync_code
        sync_secrets
        restart_service
        log ""
        show_vps_log
        log ""
        log "✅ 全量同步完成！"
        log "   代码：GitHub wyl2607/meichen + VPS /opt/meichen"
        log "   密钥：VPS /opt/meichen（Tailscale 加密传输，不上 GitHub）"
        ;;
esac
