"""Email-based problem feedback for the experiment software.

Sends feedback to ``koji3527@qq.com`` over QQ SMTP, with built-in rate
limiting so the recipient mailbox can never be spammed by a runaway loop.

Credentials live in ``config/email.json`` (gitignored) — the operator must
manually create it with their sender address and QQ SMTP ``auth_code``.
The limiter state is persisted in ``config/email_feedback_state.json`` so
the cooldown survives restarts and the daily cap is enforced across runs.
"""

from __future__ import annotations

import json
import smtplib
import ssl
import time
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path
from typing import Optional, Tuple

QQ_SMTP_HOST = "smtp.qq.com"
QQ_SMTP_PORT = 465
RECIPIENT = "koji3527@qq.com"
CONFIG_FILE_NAME = "email.json"
RATE_LIMIT_FILE_NAME = "email_feedback_state.json"
RATE_LIMIT_MIN_INTERVAL_SECONDS = 60.0
RATE_LIMIT_MAX_PER_DAY = 8
SMTP_TIMEOUT_SECONDS = 15.0


@dataclass(frozen=True)
class EmailConfig:
    sender: str
    auth_code: str
    smtp_host: str = QQ_SMTP_HOST
    smtp_port: int = QQ_SMTP_PORT


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    seconds_to_wait: float
    sent_today: int
    daily_limit: int
    reason: str = ""


def default_config_path(runtime_dir: Path) -> Path:
    return runtime_dir / CONFIG_FILE_NAME


def default_rate_limit_path(runtime_dir: Path) -> Path:
    return runtime_dir / RATE_LIMIT_FILE_NAME


def load_email_config(config_path: Path) -> EmailConfig:
    if not config_path.exists():
        raise FileNotFoundError(
            "未找到邮箱配置 {0}。请在 config 目录下新建 {1}，"
            "填入发件邮箱和 QQ 邮箱授权码（不是登录密码）。".format(
                config_path, CONFIG_FILE_NAME
            )
        )
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("邮箱配置 JSON 解析失败: {0}".format(exc)) from exc
    sender = str(payload.get("sender", "")).strip()
    auth_code = str(payload.get("auth_code", "")).strip()
    if not sender:
        raise ValueError("邮箱配置缺少 sender 字段")
    if not auth_code:
        raise ValueError("邮箱配置缺少 auth_code 字段（QQ 邮箱 IMAP/SMTP 授权码）")
    return EmailConfig(
        sender=sender,
        auth_code=auth_code,
        smtp_host=str(payload.get("smtp_host", QQ_SMTP_HOST)),
        smtp_port=int(payload.get("smtp_port", QQ_SMTP_PORT)),
    )


def write_email_config(config_path: Path, sender: str, auth_code: str) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "sender": sender,
        "auth_code": auth_code,
        "smtp_host": QQ_SMTP_HOST,
        "smtp_port": QQ_SMTP_PORT,
    }
    config_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _load_rate_state(state_path: Path) -> dict:
    if not state_path.exists():
        return {"last_sent_at": 0.0, "sent_today": 0, "today": ""}
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"last_sent_at": 0.0, "sent_today": 0, "today": ""}
    return {
        "last_sent_at": float(payload.get("last_sent_at", 0.0)),
        "sent_today": int(payload.get("sent_today", 0)),
        "today": str(payload.get("today", "")),
    }


def _save_rate_state(state_path: Path, state: dict) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _reset_if_new_day(state: dict, today: str) -> dict:
    if state.get("today") != today:
        return {"last_sent_at": 0.0, "sent_today": 0, "today": today}
    return state


def _today_label(now: float) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(now))


def evaluate_rate_limit(
    state_path: Path,
    *,
    now: Optional[float] = None,
    min_interval: float = RATE_LIMIT_MIN_INTERVAL_SECONDS,
    daily_limit: int = RATE_LIMIT_MAX_PER_DAY,
    today: Optional[str] = None,
) -> RateLimitDecision:
    """Return whether a send is allowed right now without mutating state."""
    if now is None:
        now = time.time()
    if today is None:
        today = _today_label(now)
    state = _reset_if_new_day(_load_rate_state(state_path), today)
    sent_today = int(state.get("sent_today", 0))
    if sent_today >= daily_limit:
        return RateLimitDecision(
            allowed=False,
            seconds_to_wait=0.0,
            sent_today=sent_today,
            daily_limit=daily_limit,
            reason="今日发送次数已达上限（{0} 封）".format(daily_limit),
        )
    last_sent = float(state.get("last_sent_at", 0.0))
    elapsed = now - last_sent
    if last_sent > 0.0 and elapsed < min_interval:
        return RateLimitDecision(
            allowed=False,
            seconds_to_wait=max(0.0, min_interval - elapsed),
            sent_today=sent_today,
            daily_limit=daily_limit,
            reason="请稍候",
        )
    return RateLimitDecision(
        allowed=True,
        seconds_to_wait=0.0,
        sent_today=sent_today,
        daily_limit=daily_limit,
        reason="ok",
    )


def send_feedback(
    config: EmailConfig,
    subject: str,
    body: str,
    sender_label: str,
    state_path: Path,
    *,
    smtp_login=None,
    smtp_send=None,
    now: Optional[float] = None,
    min_interval: float = RATE_LIMIT_MIN_INTERVAL_SECONDS,
    daily_limit: int = RATE_LIMIT_MAX_PER_DAY,
    today: Optional[str] = None,
) -> RateLimitDecision:
    """Send feedback email to ``RECIPIENT`` if rate limit allows it.

    ``smtp_login`` and ``smtp_send`` are dependency-injection seams for
    tests; production code should leave them ``None`` and let the function
    open a real ``smtplib.SMTP_SSL`` connection.
    """
    if now is None:
        now = time.time()
    if today is None:
        today = _today_label(now)
    state = _reset_if_new_day(_load_rate_state(state_path), today)

    decision = evaluate_rate_limit(
        state_path,
        now=now,
        min_interval=min_interval,
        daily_limit=daily_limit,
        today=today,
    )
    if not decision.allowed:
        return decision

    subject_clean = (subject or "").strip() or "未填写主题"
    body_clean = (body or "").strip() or "(无正文)"
    label_clean = (sender_label or "").strip() or "匿名"

    msg = EmailMessage()
    msg["From"] = config.sender
    msg["To"] = RECIPIENT
    msg["Subject"] = "[实验软件反馈] {0}".format(subject_clean)
    msg.set_content(
        "发件人: {0}\n时间: {1}\n\n{2}\n".format(
            label_clean, time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)), body_clean
        )
    )

    def _default_login(smtp):
        smtp.login(config.sender, config.auth_code)

    def _default_send(smtp):
        smtp.send_message(msg)

    try:
        if smtp_login is None and smtp_send is None:
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(
                config.smtp_host,
                config.smtp_port,
                context=ctx,
                timeout=SMTP_TIMEOUT_SECONDS,
            ) as smtp:
                _default_login(smtp)
                _default_send(smtp)
        else:
            # Test path: callers may supply one or both callables
            if smtp_login is not None:
                smtp_login(None)
            if smtp_send is not None:
                smtp_send(None)
    except Exception as exc:
        raise RuntimeError("邮件发送失败: {0}".format(exc)) from exc

    state["last_sent_at"] = now
    state["sent_today"] = int(state.get("sent_today", 0)) + 1
    state["today"] = today
    _save_rate_state(state_path, state)
    return RateLimitDecision(
        allowed=True,
        seconds_to_wait=0.0,
        sent_today=int(state["sent_today"]),
        daily_limit=daily_limit,
        reason="ok",
    )


def remaining_cooldown_seconds(
    state_path: Path,
    *,
    now: Optional[float] = None,
    min_interval: float = RATE_LIMIT_MIN_INTERVAL_SECONDS,
    today: Optional[str] = None,
) -> Tuple[float, int, int]:
    if now is None:
        now = time.time()
    if today is None:
        today = _today_label(now)
    state = _reset_if_new_day(_load_rate_state(state_path), today)
    sent_today = int(state.get("sent_today", 0))
    last_sent = float(state.get("last_sent_at", 0.0))
    elapsed = now - last_sent if last_sent > 0.0 else min_interval
    cooldown = max(0.0, min_interval - elapsed) if last_sent > 0.0 else 0.0
    return cooldown, sent_today, RATE_LIMIT_MAX_PER_DAY
