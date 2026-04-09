@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
color 0A
title Farm-Agent Command Center v3.0

:: ── Activate Python venv (makes 'farm_agent' CLI available) ──
call venv\Scripts\activate

:menu
cls
echo.
echo  ╔════════════════════════════════════════════════════════════════════════════╗
echo  ║                                                                            ║
echo  ║   ███████╗ █████╗ ██████╗ ███╗   ███╗    █████╗  ██████╗ ███████╗███╗   ██╗████████╗   ║
echo  ║   ██╔════╝██╔══██╗██╔══██╗████╗ ████║   ██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝   ║
echo  ║   █████╗  ███████║██████╔╝██╔████╔██║   ███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║      ║
echo  ║   ██╔══╝  ██╔══██║██╔══██╗██║╚██╔╝██║   ██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║      ║
echo  ║   ██║     ██║  ██║██║  ██║██║ ╚═╝ ██║   ██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║      ║
echo  ║   ╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝   ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝      ║
echo  ║                                                                            ║
echo  ║          ★  TRUNG TÂM ĐIỀU KHIỂN - FARM AGENT v3.0  ★                    ║
echo  ║              Trợ lý đóng góp mã nguồn mở v3.0                             ║
echo  ║                                                                            ║
echo  ╚════════════════════════════════════════════════════════════════════════════╝
echo.
echo  ┌──────────────────────────────────────────────────────────────────┐
echo  │  📈  THỐNG KÊ TỔNG QUAN HỆ THỐNG                               │
echo  └──────────────────────────────────────────────────────────────────┘
echo.
farm_agent stats
echo.
echo  ┌──────────────────────────────────────────────────────────────────┐
echo  │  ⚡  BẢNG ĐIỀU KHIỂN CHÍNH                                      │
echo  └──────────────────────────────────────────────────────────────────┘
echo.
echo     [S]  🧠  CHẾ ĐỘ SUPER HUMAN — Tự động 24/7 giả lập developer ⭐
echo.
echo     [1]  🦅  Chế độ Hunt Mode (Săn lùng dự án hàng loạt)
echo     [2]  🔄  Hunt Circular — Vòng lặp Bounty từ target_repo.json
echo     [3]  🛡️  Chế độ PR Patrol (Tuần tra ^& Tự chữa lành CI)
echo     [4]  🎯  Nhắm mục tiêu cụ thể (Nhập URL Repo)
echo     [5]  📊  Xem trạng thái hệ thống chi tiết (System Status)
echo     [6]  🧹  Dọn dẹp Fork không còn dùng (Cleanup)
echo     [7]  🗑️  Garbage Collection — Xóa bài học QA cũ (GC)
echo     [8]  🏆  Bảng xếp hạng đóng góp (Leaderboard)
echo.
echo     [0]  ❌  Thoát chương trình
echo.
echo  ══════════════════════════════════════════════════════════════════
echo.
set /p choice="  👉  Nhập lựa chọn của bạn [0-8, S]: "

if /i "%choice%"=="S" goto :superhuman
if "%choice%"=="1" goto :hunt
if "%choice%"=="2" goto :hunt_circular
if "%choice%"=="3" goto :patrol
if "%choice%"=="4" goto :target
if "%choice%"=="5" goto :sysinfo
if "%choice%"=="6" goto :cleanup
if "%choice%"=="7" goto :gc
if "%choice%"=="8" goto :leaderboard
if "%choice%"=="0" goto :exit

echo.
echo  ⚠️  Lựa chọn không hợp lệ! Vui lòng nhập số từ 0 đến 8 hoặc S.
timeout /t 2 >nul
goto :menu

:: ═══════════════════════════════════════════════════════════════
:: [S] Super Human Mode
:: ═══════════════════════════════════════════════════════════════
:superhuman
cls
echo.
echo  ┌──────────────────────────────────────────────────────────────────┐
echo  │  🧠  CHẾ ĐỘ SUPER HUMAN - TỰ ĐỘNG 24/7                        │
echo  └──────────────────────────────────────────────────────────────────┘
echo.
echo  ► Hệ thống sẽ hoạt động như một lập trình viên thực thụ:
echo    - Tự đặt hạn mức PR ngẫu nhiên mỗi ngày (2-5 PRs)
echo    - Xen kẽ Hunt Mode và PR Patrol một cách tự nhiên
echo    - Nghỉ ngơi với thời gian ngẫu nhiên giữa các hành động
echo    - Tự động chuyển sang Patrol khi đạt hạn mức
echo    - Tự động dọn dẹp Knowledge Base cũ mỗi ngày
echo  ► Nhấn Ctrl+C để dừng.
echo.
echo  ────────────────────────────────────────────────────────────────
echo.
farm_agent superhuman
pause
goto :menu

:: ═══════════════════════════════════════════════════════════════
:: [1] Hunt Mode
:: ═══════════════════════════════════════════════════════════════
:hunt
cls
echo.
echo  ┌──────────────────────────────────────────────────────────────────┐
echo  │  🦅  CHẾ ĐỘ HUNT MODE - SĂN LÙNG DỰ ÁN HÀNG LOẠT             │
echo  └──────────────────────────────────────────────────────────────────┘
echo.
echo  ► Hệ thống sẽ tự động tìm kiếm các repo tiềm năng trên GitHub,
echo    phân tích mã nguồn, và tạo Pull Request đóng góp.
echo  ► Chế độ: Phân tích mã + Giải quyết Issues (both)
echo.
echo  ────────────────────────────────────────────────────────────────
echo.
farm_agent hunt --mode both
echo.
echo  ════════════════════════════════════════════════════════════════
echo  ✅  Hunt Mode đã hoàn thành!
echo  ════════════════════════════════════════════════════════════════
pause
goto :menu

:: ═══════════════════════════════════════════════════════════════
:: [2] Hunt Circular — Bounty Target Loop
:: ═══════════════════════════════════════════════════════════════
:hunt_circular
cls
echo.
echo  ┌──────────────────────────────────────────────────────────────────┐
echo  │  🔄  HUNT CIRCULAR — VÒNG LẶP BOUNTY TỪ TARGET_REPO.JSON     │
echo  └──────────────────────────────────────────────────────────────────┘
echo.
echo  ► Chế độ Bounty: Đọc danh sách mục tiêu từ target_repo.json,
echo    xử lý theo vòng tròn (round-robin) dựa trên thời gian quét cũ nhất.
echo  ► Bloodhound: Quét ast-grep trước, chỉ gửi true positives cho LLM.
echo  ► QA Hardcore: Chỉ chấp nhận patch đạt điểm >= 9.0/10.0.
echo.
echo  ────────────────────────────────────────────────────────────────
echo.
farm_agent hunt-circular
echo.
echo  ════════════════════════════════════════════════════════════════
echo  ✅  Hunt Circular đã hoàn thành!
echo  ════════════════════════════════════════════════════════════════
pause
goto :menu

:: ═══════════════════════════════════════════════════════════════
:: [3] PR Patrol
:: ═══════════════════════════════════════════════════════════════
:patrol
cls
echo.
echo  ┌──────────────────────────────────────────────────────────────────┐
echo  │  🛡️  CHẾ ĐỘ PR PATROL - TUẦN TRA ^& TỰ CHỮA LÀNH              │
echo  └──────────────────────────────────────────────────────────────────┘
echo.
echo  ► Hệ thống sẽ quét tất cả PR đang mở, đọc phản hồi từ maintainer,
echo    tự động sửa code và đẩy cập nhật lên PR.
echo.
echo  ────────────────────────────────────────────────────────────────
echo.
farm_agent patrol
echo.
echo  ════════════════════════════════════════════════════════════════
echo  ✅  PR Patrol đã hoàn thành!
echo  ════════════════════════════════════════════════════════════════
pause
goto :menu

:: ═══════════════════════════════════════════════════════════════
:: [4] Target cụ thể
:: ═══════════════════════════════════════════════════════════════
:target
cls
echo.
echo  ┌──────────────────────────────────────────────────────────────────┐
echo  │  🎯  NHẮM MỤC TIÊU CỤ THỂ - TARGET MODE                       │
echo  └──────────────────────────────────────────────────────────────────┘
echo.
set /p repo_url="  📎  Nhập URL của Repository (VD: https://github.com/owner/repo): "
echo.

if "%repo_url%"=="" (
    echo  ⚠️  Bạn chưa nhập URL! Quay lại menu...
    timeout /t 2 >nul
    goto :menu
)

echo  ► Đang nhắm mục tiêu: %repo_url%
echo  ► Hệ thống sẽ phân tích và tạo đóng góp cho repo này...
echo.
echo  ────────────────────────────────────────────────────────────────
echo.
farm_agent target %repo_url%
echo.
echo  ════════════════════════════════════════════════════════════════
echo  ✅  Target đã hoàn thành!
echo  ════════════════════════════════════════════════════════════════
pause
goto :menu

:: ═══════════════════════════════════════════════════════════════
:: [5] System Info
:: ═══════════════════════════════════════════════════════════════
:sysinfo
cls
echo.
echo  ┌──────────────────────────────────────────────────────────────────┐
echo  │  📊  TRẠNG THÁI HỆ THỐNG CHI TIẾT                              │
echo  └──────────────────────────────────────────────────────────────────┘
echo.
farm_agent sysinfo
echo.
echo  ════════════════════════════════════════════════════════════════
pause
goto :menu

:: ═══════════════════════════════════════════════════════════════
:: [6] Cleanup
:: ═══════════════════════════════════════════════════════════════
:cleanup
cls
echo.
echo  ┌──────────────────────────────────────────────────────────────────┐
echo  │  🧹  DỌN DẸP FORK KHÔNG CÒN DÙNG                               │
echo  └──────────────────────────────────────────────────────────────────┘
echo.
echo  ► Quét các fork đã tạo, kiểm tra trạng thái PR,
echo    và xóa fork nào đã hoàn thành nhiệm vụ.
echo.
echo  ────────────────────────────────────────────────────────────────
echo.
farm_agent cleanup
echo.
echo  ════════════════════════════════════════════════════════════════
echo  ✅  Dọn dẹp hoàn thành!
echo  ════════════════════════════════════════════════════════════════
pause
goto :menu

:: ═══════════════════════════════════════════════════════════════
:: [7] Garbage Collection — KB Purge
:: ═══════════════════════════════════════════════════════════════
:gc
cls
echo.
echo  ┌──────────────────────────────────────────────────────────────────┐
echo  │  🗑️  GARBAGE COLLECTION — XÓA BÀI HỌC QA CŨ                   │
echo  └──────────────────────────────────────────────────────────────────┘
echo.
echo  ► Xóa các bài học QA (knowledge base) cũ hơn 90 ngày.
echo    Giúp tiết kiệm token LLM và giữ context window sạch.
echo.
echo  ────────────────────────────────────────────────────────────────
echo.
farm_agent gc
echo.
echo  ════════════════════════════════════════════════════════════════
echo  ✅  Garbage Collection hoàn thành!
echo  ════════════════════════════════════════════════════════════════
pause
goto :menu

:: ═══════════════════════════════════════════════════════════════
:: [8] Leaderboard
:: ═══════════════════════════════════════════════════════════════
:leaderboard
cls
echo.
echo  ┌──────────────────────────────────────────────────────────────────┐
echo  │  🏆  BẢNG XẾP HẠNG ĐÓNG GÓP                                    │
echo  └──────────────────────────────────────────────────────────────────┘
echo.
farm_agent leaderboard
echo.
echo  ════════════════════════════════════════════════════════════════
pause
goto :menu

:: ═══════════════════════════════════════════════════════════════
:: [0] Thoát
:: ═══════════════════════════════════════════════════════════════
:exit
cls
echo.
echo  ╔══════════════════════════════════════════════════════════════════╗
echo  ║                                                                ║
echo  ║   🙏  CẢM ƠN BẠN ĐÃ SỬ DỤNG FARM-AGENT!                       ║
echo  ║                                                                ║
echo  ║   ► Tiếp tục đóng góp cho cộng đồng mã nguồn mở!             ║
echo  ║   ► GitHub: https://github.com/your-org/farm_agent             ║
echo  ║                                                                ║
echo  ╚══════════════════════════════════════════════════════════════════╝
echo.
timeout /t 3 >nul
endlocal
exit /b 0