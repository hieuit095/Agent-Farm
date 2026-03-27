"""Super Human Mode — stochastic daily routine orchestrator.

Implements an organic operational loop that mimics a dedicated human developer.
Dynamically interleaves Hunt Mode (finding and fixing new issues) and PR Patrol
(monitoring and responding to feedback), with randomized daily PR quotas and
unpredictable human-like delays.

Usage:
    contribai superhuman              # Run the full daily routine
    contribai superhuman --time-warp  # Run 10 fast iterations for testing
"""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import UTC, date, datetime

from contribai.core.exceptions import ContribAIError, GitHubAPIError, LLMRateLimitError

logger = logging.getLogger(__name__)

# Absolute safety cap — never exceed this regardless of random generation
ABSOLUTE_MAX_PRS_PER_DAY = 6

# Delay ranges (seconds) for real operation
HUNT_DELAY_MIN = 1800   # 30 minutes
HUNT_DELAY_MAX = 5400   # 90 minutes
DRY_HUNT_DELAY_MIN = 120   # 2 minutes — retry quickly when no repos scanned
DRY_HUNT_DELAY_MAX = 300   # 5 minutes
PATROL_DELAY_MIN = 600  # 10 minutes
PATROL_DELAY_MAX = 1800 # 30 minutes
PATROL_ONLY_DELAY_MIN = 3600   # 1 hour
PATROL_ONLY_DELAY_MAX = 10800  # 3 hours
STRESS_BREAK_SEC = 900  # 15 minutes

# Time-warp overrides (seconds) for testing
WARP_DELAY_MIN = 1
WARP_DELAY_MAX = 3
WARP_MAX_ITERATIONS = 10

# Action selection weights
HUNT_WEIGHT = 0.60
PATROL_WEIGHT = 0.40

# ── Human Developer Persona — Vietnamese Thoughts ──────────────────────────
HUMAN_THOUGHTS = {
    "WAKE_UP": [
        "☀️ Trời sáng rồi! Pha ly cà phê đen rồi xem hôm nay open-source có gì vui không... (Mục tiêu: {limit} PRs)",  # noqa: E501
        "🌅 Hôm nay code nhẹ nhàng {limit} cái PR rồi lượn đi đọc tài liệu vậy.",
        "☕ Mở mắt, bật máy, pha cà phê... Hôm nay chỉ cần {limit} PRs là đạt chỉ tiêu!",
        "🌤️ Ngày mới bắt đầu! Kế hoạch: gửi {limit} PRs, fix bug, rồi tối đi ăn phở. Let's go!",
        "😎 Good morning GitHub! Hôm nay nhắm {limit} PRs — không nhiều, không ít, vừa đủ pro.",
    ],
    "START_HUNT": [
        "🦅 Đã uống xong trà, bắt đầu lượn GitHub săn repo mới...",
        "💪 Vươn vai cái nào! Bắt đầu tìm repo để fix bug thôi.",
        "🔍 Mở GitHub tab mới, scan trending repos... Xem có gì hay ho không nào!",
        "🎯 Bắt đầu hunt session — tìm repo có issue dễ ăn trước đã.",
        "⌨️ Nước trà còn nóng, bắt tay vào code. Kiếm repo nào đó mà đóng góp thôi!",
        "🧑‍💻 OK, đã warm up xong. Giờ vào GitHub tìm project hay ho để contribute nào...",
    ],
    "HUNT_DONE": [
        "✅ Hunt xong! Đã phân tích {repos} repo(s), tạo {prs} PR(s). Cũng tạm ổn!",
        "🎉 Kết quả hunt: {repos} repo(s) scanned, {prs} PR(s) gửi đi. Ngon lành!",
        "📊 Phiên hunt kết thúc — {repos} repo, {prs} PRs. Maintainer ơi, review giùm em!",
    ],
    "REST_HUNT": [
        "😅 Fix bug mỏi mắt quá. Đi lướt web {mins} phút rồi quay lại làm tiếp.",
        "🧘 Nộp PR xong rồi. Nghỉ ngơi {mins} phút cho não hồi phục...",
        "☕ Code xong mệt ghê, nghỉ {mins} phút uống cà phê cái đã.",
        "🎮 Tay rung rồi, kệ, chơi game {mins} phút cho thư giãn rồi quay lại.",
        "📱 Nghỉ tay {mins} phút, đi scroll TikTok một tí rồi code tiếp!",
    ],
    "REST_HUNT_DRY": [
        "🔄 Dry run — 0 repos scanned. Retry in {mins} min with different criteria...",
        "⏩ Nothing to scan this round. Quick {mins} min pause then try again!",
        "🎲 No targets found. Switching criteria in {mins} min...",
    ],
    "START_PATROL": [
        "🛡️ Vào xem mấy cái PR cũ có ai comment gì chưa nào...",
        "🔔 Giờ kiểm tra notifications — xem maintainer phản hồi gì chưa.",
        "📬 Mở inbox GitHub, check xem có review nào cần trả lời không...",
        "👀 Lướt qua mấy PR đang pending, xem có cần fix gì thêm không.",
        "📋 Patrol time! Xem có reviewer nào để lại comment không nào...",
    ],
    "PATROL_EMPTY": [
        "🤷 Chẳng có PR nào đang mở cả. Maintainer review nhanh thật! Thôi nghỉ vậy.",
        "😴 Inbox trống trơn, không có gì cần patrol. Nhàn ghê!",
    ],
    "PATROL_DONE": [
        "✅ Patrol xong! Đã check {checked} PRs, push {fixes} fix(es), trả lời {replies} comment(s).",  # noqa: E501
        "🛡️ Tuần tra hoàn tất: {checked} PRs reviewed, {fixes} sửa, {replies} phản hồi. Ngon!",
    ],
    "REST_PATROL": [
        "😌 Check PR xong rồi. Nghỉ ngơi {mins} phút, đọc blog dev một tí...",
        "🍵 Patrol done, ngồi uống trà {mins} phút cho thoải mái rồi làm tiếp.",
        "📰 Xem xong mấy cái PR, giờ đọc HackerNews {mins} phút đã...",
    ],
    "QUOTA_MET": [
        "🏁 Hôm nay làm đủ KPIs rồi ({today}/{limit} PRs). Giờ chỉ ngồi trực canh comment thôi, không push thêm nữa để tránh bị report spam.",  # noqa: E501
        "✋ Đạt quota rồi ({today}/{limit} PRs). Từ giờ đến hết ngày chỉ patrol thôi — push nhiều quá maintainer ghét!",  # noqa: E501
        "📊 {today}/{limit} PRs — mission accomplished! Giờ chuyển sang chế độ tuần tra, ngồi trả lời review cho đẹp.",  # noqa: E501
        "😎 Xong {today}/{limit} PRs hôm nay! Bây giờ chill mode — chỉ check feedback thôi.",
    ],
    "REST_PATROL_ONLY": [
        "💤 Đang patrol-only mode. Ngủ gật {mins} phút rồi vào check comment tiếp...",
        "🛋️ Ngồi chờ maintainer review, tranh thủ nghỉ {mins} phút...",
        "📺 Quota đã đạt, ngồi xem YouTube {mins} phút chờ notification...",
        "😴 Chờ feedback, tranh thủ ngủ trưa {mins} phút. Alarm set!",
    ],
    "API_ERROR": [
        "😤 GitHub API lại dở chứng rồi! Bực mình, đi dạo {mins} phút cho đỡ stress rồi thử lại.",
        "🔥 API lỗi! Thôi bình tĩnh, uống nước, nghỉ {mins} phút rồi retry.",
        "💀 Lỗi API rồi anh em ơi! Chắc GitHub đang deploy. Chờ {mins} phút vậy...",
        "😰 Lại lỗi mạng! Stress ghê. Đi pha cà phê, {mins} phút nữa quay lại.",
    ],
    "ACTION_ROLL": [
        "🎲 Tung xúc xắc... {roll:.0%} → chọn {action}! (Hunt < 60% / Patrol ≥ 60%)",
        "🎰 Random roll: {roll:.0%} → hành động: {action}. Xem nào...",
        "🎯 Số phận chọn {action} cho iteration này (roll = {roll:.0%}).",
    ],
    "ITERATION": [
        "📊 [Iteration {iter}] PRs hôm nay: {today}/{limit} — còn slot, tiếp tục chiến!",
        "📈 Vòng {iter}: đã tạo {today}/{limit} PRs — {remaining} slot còn lại.",
        "📋 Check-in iteration {iter}: {today}/{limit} PRs. Vẫn trong quota, let's go!",
    ],
    "TIME_WARP_START": [
        "⏩ TIME-WARP ACTIVATED! Delay = 1-3s, auto-exit sau {max_iter} iterations. Bắt đầu test nào!",  # noqa: E501
    ],
    "GOODBYE": [
        "🧠 Super Human Mode kết thúc. Hẹn gặp lại ngày mai, GitHub! 👋",
        "🌙 Hết giờ làm việc. Tắt máy, đi ngủ thôi. See you tomorrow! 😴",
    ],
}


def _thought(category: str, **kwargs) -> str:
    """Pick a random Vietnamese thought and format it with kwargs."""
    templates = HUMAN_THOUGHTS.get(category, [f"[{category}]"])
    return random.choice(templates).format(**kwargs)


class SuperHumanLoop:
    """Orchestrates a stochastically driven daily routine.

    Mimics a real human developer by:
    - Setting a random daily PR target (1-5, capped at 6)
    - Hunting INFINITELY until the target number of successful PRs is met
    - Shifting to patrol-only mode once the daily PR target is reached
    - Handling errors gracefully with "stress breaks"
    """

    def __init__(
        self,
        pipeline,
        memory,
        *,
        dry_run: bool = False,
        target_repo_url: str | None = None,
        target_repo_max_prs: int = 1,
    ):
        """Initialize the Super Human Loop.

        Args:
            pipeline: ContribPipeline instance for Hunt operations.
            memory: Memory instance for PR count tracking.
            dry_run: If True, Hunt/Patrol won't create real PRs.
            target_repo_url: If set, Hunt will target this repo directly.
            target_repo_max_prs: Maximum PRs to create per targeted hunt.
        """
        from contribai.core.daily_log import DailyMarkdownLogger
        from contribai.core.notifier import TelegramNotifier

        self._pipeline = pipeline
        self._memory = memory
        self._dry_run = dry_run
        self._target_repo_url = target_repo_url
        self._target_repo_max_prs = max(1, target_repo_max_prs)
        self._daily_pr_target: int = 0
        self._prs_created_today: int = 0
        self._current_day: date | None = None
        self._iteration = 0
        self._quota_logged_today = False
        self._daily_log = DailyMarkdownLogger()
        self._notifier = TelegramNotifier(
            token=self._pipeline.config.notifications.telegram_token,
            chat_id=self._pipeline.config.notifications.telegram_chat_id,
        )

    def _new_day_check(self) -> bool:
        """Check if a new calendar day has started. Returns True if day changed."""
        today = datetime.now(UTC).date()
        if self._current_day != today:
            self._current_day = today
            self._daily_pr_target = min(
                random.randint(1, 5),
                ABSOLUTE_MAX_PRS_PER_DAY,
            )
            self._prs_created_today = 0
            logger.info(_thought("WAKE_UP", limit=self._daily_pr_target))
            self._daily_log.log_new_day(self._daily_pr_target)
            self._quota_logged_today = False  # reset for new day
            return True
        return False

    def _pick_delay(
        self,
        action: str,
        time_warp: bool,
    ) -> int:
        """Pick a stochastic delay based on the action type."""
        if time_warp:
            return random.randint(WARP_DELAY_MIN, WARP_DELAY_MAX)

        if action == "hunt":
            return random.randint(HUNT_DELAY_MIN, HUNT_DELAY_MAX)
        elif action == "hunt_dry":
            return random.randint(DRY_HUNT_DELAY_MIN, DRY_HUNT_DELAY_MAX)
        elif action == "patrol_only":
            return random.randint(PATROL_ONLY_DELAY_MIN, PATROL_ONLY_DELAY_MAX)
        else:  # patrol
            return random.randint(PATROL_DELAY_MIN, PATROL_DELAY_MAX)

    def _pick_stress_delay(self, time_warp: bool) -> int:
        """Delay after an error — simulates a developer taking a stress break."""
        if time_warp:
            return random.randint(WARP_DELAY_MIN, WARP_DELAY_MAX)
        return STRESS_BREAK_SEC

    def _format_duration(self, seconds: int) -> str:
        """Format seconds into a human-readable string."""
        if seconds < 60:
            return f"{seconds}s"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes}m {seconds % 60}s"
        hours = minutes // 60
        return f"{hours}h {minutes % 60}m"

    async def _do_hunt(self) -> tuple[int, int]:
        """Execute a single Hunt action.

        If target_repo_url is set, hunts that specific repo.
        Otherwise, uses DiscoveryEngine for wild GitHub discovery.

        Returns:
            Tuple of (prs_created, repos_analyzed).
        """
        logger.info(_thought("START_HUNT"))
        try:
            if self._target_repo_url:
                # Targeted mode — user explicitly passed --target-repo
                logger.info(
                    "🎯 Targeted hunt: %s (max %d PR)",
                    self._target_repo_url,
                    self._target_repo_max_prs,
                )
                result = await self._pipeline.run_single(
                    self._target_repo_url,
                    dry_run=self._dry_run,
                    max_prs=self._target_repo_max_prs,
                )
            else:
                # Wild discovery — search GitHub based on config.yaml criteria
                logger.info("🌍 Wild discovery mode — searching GitHub network...")
                result = await self._pipeline.hunt(
                    rounds=1,
                    delay_sec=5,
                    dry_run=self._dry_run,
                    mode="both",
                )
            logger.info(_thought(
                "HUNT_DONE",
                repos=result.repos_analyzed,
                prs=result.prs_created,
            ))
            
            if result.prs_created > 0:
                rest_time = random.randint(900, 2700)
                logger.info(f"Mới nộp PR xong, căng não quá. Đi hút điếu thuốc / dạo bộ 30 phút rồi mới làm tiếp. (Sleeping {rest_time}s)")
                await asyncio.sleep(rest_time)

            # ── Daily log: record hunt outcome ──
            if result.prs_created > 0 and result.pr_urls:
                for url in result.pr_urls:
                    # Extract repo and PR# from URL
                    parts = url.rstrip("/").split("/")
                    repo = f"{parts[-4]}/{parts[-3]}" if len(parts) >= 4 else "unknown"
                    pr_num = int(parts[-1]) if parts[-1].isdigit() else 0
                    self._daily_log.log_hunt_success(repo, pr_num, url)
            elif result.prs_created > 0:
                self._daily_log.log_hunt_success(
                    "repo", result.prs_created, "(no URL available)",
                )
            else:
                self._daily_log.log_hunt_no_result(result.repos_analyzed)
            return result.prs_created, result.repos_analyzed
        except GitHubAPIError as exc:
            logger.error("🦅 HUNT failed (GitHubAPIError): %s", exc)
            raise
        except Exception as exc:
            logger.error("🦅 HUNT failed (unexpected error): %s", exc)
            raise

    async def _do_patrol(self) -> None:
        """Execute a single PR Patrol action."""
        from contribai.github.client import GitHubClient
        from contribai.llm.provider import create_llm_provider
        from contribai.pr.patrol import PRPatrol

        logger.info(_thought("START_PATROL"))
        try:
            pr_records = await self._memory.get_prs(status="open", limit=100)
            if not pr_records:
                logger.info(_thought("PATROL_EMPTY"))
                return

            logger.info("📬 Tìm thấy %d PR(s) đang mở, bắt đầu review...", len(pr_records))

            github = GitHubClient(token=self._pipeline.config.github.token)
            llm = create_llm_provider(self._pipeline.config.llm)

            try:
                patrol_engine = PRPatrol(github=github, llm=llm, memory=self._memory, notifier=self._notifier)
                result = await patrol_engine.patrol(
                    pr_records,
                    dry_run=self._dry_run,
                )
                logger.info(_thought(
                    "PATROL_DONE",
                    checked=result.prs_checked,
                    fixes=result.fixes_pushed,
                    replies=result.replies_sent,
                ))
                # ── Daily log: record patrol outcome ──
                if result.prs_checked > 0:
                    self._daily_log.log_patrol_result(
                        prs_checked=result.prs_checked,
                        fixes_pushed=result.fixes_pushed,
                        replies_sent=result.replies_sent,
                        ci_fixes=getattr(result, "ci_fixes_pushed", 0),
                    )
                else:
                    self._daily_log.log_patrol_empty()
            finally:
                await github.close()
                await llm.close()

        except GitHubAPIError as exc:
            logger.error("🛡️ Patrol lỗi (GitHubAPIError): %s", exc)
            raise
        except Exception as exc:
            logger.error("🛡️ Patrol lỗi (không xác định): %s", exc)
            raise

    async def run_daily_routine(self, *, time_warp: bool = False) -> None:
        """Run the continuous Super Human daily routine.

        The bot hunts INFINITELY until its daily PR target is met.
        Only successful PR creations count towards the target.
        Scanning repos without creating PRs does NOT consume quota.

        Args:
            time_warp: If True, overrides delays to 1-3 seconds and exits
                       after 10 iterations (for testing / verification).
        """
        if time_warp:
            logger.info(_thought("TIME_WARP_START", max_iter=WARP_MAX_ITERATIONS))

        logger.info("🧠 Super Human Mode initialized — starting daily loop...")
        self._iteration = 0

        # Start telegram listener in the background
        if getattr(self, "_notifier", None):
            asyncio.create_task(self._notifier.start_polling(self._memory))

        while True:
            self._iteration += 1

            # ── Time-warp exit gate ─────────────────────────────────────
            if time_warp and self._iteration > WARP_MAX_ITERATIONS:
                logger.info(
                    "⏩ TIME-WARP: Completed %d iterations — exiting.",
                    WARP_MAX_ITERATIONS,
                )
                break

            # ── New day check & target reset ────────────────────────────
            self._new_day_check()

            remaining = max(0, self._daily_pr_target - self._prs_created_today)

            # ── Mandatory Lunch Break ───────────────────────────────────
            now = datetime.now()
            if not time_warp and now.hour == 12:
                target_lunch_end = now.replace(hour=13, minute=0, second=0, microsecond=0)
                seconds_until_1pm = (target_lunch_end - now).total_seconds()
                if seconds_until_1pm > 0:
                    logger.info("Đến giờ nghỉ trưa rồi! Gấp máy đi ăn cơm, chiều 1h cày tiếp. 🍱")
                    await asyncio.sleep(seconds_until_1pm)

            # ── Decide action based on LOCAL PR counter ─────────────────
            if self._prs_created_today >= self._daily_pr_target:
                # ── TARGET MET — Patrol-only mode ──────────────────────
                if not self._quota_logged_today:
                    self._daily_log.log_quota_met(
                        self._prs_created_today, self._daily_pr_target,
                    )
                    self._quota_logged_today = True
                logger.info(_thought(
                    "QUOTA_MET",
                    today=self._prs_created_today,
                    limit=self._daily_pr_target,
                ))
                try:
                    await self._do_patrol()
                except (GitHubAPIError, ContribAIError, Exception) as exc:
                    logger.error("Patrol error in quota-met mode: %s", exc)
                    self._daily_log.log_error("Patrol (quota-met)", str(exc))
                    stress_delay = self._pick_stress_delay(time_warp)
                    mins = max(1, stress_delay // 60)
                    logger.warning(_thought("API_ERROR", mins=mins))
                    await asyncio.sleep(stress_delay)
                    continue

                delay = self._pick_delay("patrol_only", time_warp)
                mins = max(1, delay // 60)
                logger.info(_thought("REST_PATROL_ONLY", mins=mins))
                await asyncio.sleep(delay)

            else:
                # ── UNDER TARGET — Hunt infinitely until target met ────
                logger.info(_thought(
                    "ITERATION",
                    iter=self._iteration,
                    today=self._prs_created_today,
                    limit=self._daily_pr_target,
                    remaining=remaining,
                ))

                logger.info(_thought(
                    "ACTION_ROLL",
                    roll=0.0,
                    action="HUNT 🦅",
                ))

                try:
                    prs_opened, repos_scanned = await self._do_hunt()
                    # CRITICAL: Only count ACTUAL successful PR creations
                    if prs_opened > 0:
                        self._prs_created_today += prs_opened
                        logger.info(
                            "🎯 PR COUNTER: +%d → %d/%d today",
                            prs_opened,
                            self._prs_created_today,
                            self._daily_pr_target,
                        )
                    else:
                        logger.info(
                            "🔄 No PR created this hunt. Counter stays %d/%d.",
                            self._prs_created_today,
                            self._daily_pr_target,
                        )
                except LLMRateLimitError as exc:
                    # Quota exhausted — take a LONG cooldown (1 hour)
                    # so the sliding window has time to clear up
                    quota_cooldown = 3 if time_warp else 3600
                    logger.warning(
                        "Ngân sách Minimax đã chạm đỉnh (Quota exhausted). "
                        "Tắt máy đi ngủ 1 tiếng để hồi mana... "
                        "(sleeping %ds, error: %s)",
                        quota_cooldown, exc,
                    )
                    self._daily_log.log_error(
                        "HUNT (LLM Quota)", str(exc),
                    )
                    await asyncio.sleep(quota_cooldown)
                    continue
                except (GitHubAPIError, ContribAIError, Exception) as exc:
                    # Errors do NOT increment the counter
                    logger.error("Hunt error: %s", exc)
                    self._daily_log.log_error("HUNT", str(exc))
                    stress_delay = self._pick_stress_delay(time_warp)
                    mins = max(1, stress_delay // 60)
                    logger.warning(_thought("API_ERROR", mins=mins))
                    await asyncio.sleep(stress_delay)
                    continue

                # ── Dynamic Sleep ──────────────────────────────────────
                # Dry run (0 repos scanned, 0 PRs) → short retry (2-5 min)
                # Productive hunt (repos scanned or PRs created) → normal rest (30-90 min)
                if prs_opened == 0 and repos_scanned == 0:
                    delay = self._pick_delay("hunt_dry", time_warp)
                    mins = max(1, delay // 60)
                    logger.info(_thought("REST_HUNT_DRY", mins=mins))
                else:
                    delay = self._pick_delay("hunt", time_warp)
                    mins = max(1, delay // 60)
                    logger.info(_thought("REST_HUNT", mins=mins))
                await asyncio.sleep(delay)

        self._daily_log.log_shutdown(self._iteration - 1)
        logger.info(_thought("GOODBYE"))

        # Clean up persistent HTTP connections
        if self._notifier:
            await self._notifier.close()
