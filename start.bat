@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
color 0A
title ContribAI Command Center v2.5

:: ── Activate Python venv (makes 'contribai' CLI available) ──
call venv\Scripts\activate

:menu
cls
echo.
echo  ╔══════════════════════════════════════════════════════════════════╗
echo  ║                                                                ║
echo  ║    ██████╗ ██████╗ ███╗   ██╗████████╗██████╗ ██╗██████╗      ║
echo  ║   ██╔════╝██╔═══██╗████╗  ██║╚══██╔══╝██╔══██╗██║██╔══██╗     ║
echo  ║   ██║     ██║   ██║██╔██╗ ██║   ██║   ██████╔╝██║██████╔╝     ║
echo  ║   ██║     ██║   ██║██║╚██╗██║   ██║   ██╔══██╗██║██╔══██╗     ║
echo  ║   ╚██████╗╚██████╔╝██║ ╚████║   ██║   ██║  ██║██║██████╔╝     ║
echo  ║    ╚═════╝ ╚═════╝ ╚═╝  ╚═══╝   ╚═╝   ╚═╝  ╚═╝╚═╝╚════╝      ║
echo  ║                                                                ║
echo  ║          ★  TRUNG TÂM ĐIỀU KHIỂN - COMMAND CENTER  ★          ║
echo  ║              AI Agent đóng góp mã nguồn mở v2.5               ║
echo  ║                                                                ║
echo  ╚══════════════════════════════════════════════════════════════════╝
echo.
echo  ┌──────────────────────────────────────────────────────────────────┐
echo  │  📈  THỐNG KÊ TỔNG QUAN HỆ THỐNG                               │
echo  └──────────────────────────────────────────────────────────────────┘
echo.
contribai stats
echo.
echo  ┌──────────────────────────────────────────────────────────────────┐
echo  │  ⚡  BẢNG ĐIỀU KHIỂN CHÍNH                                      │
echo  └──────────────────────────────────────────────────────────────────┘
echo.
echo     [1]  🧠  CHẾ ĐỘ SUPER HUMAN — Tự động 24/7 giả lập developer ⭐
echo.
echo     [2]  🌐  Khởi chạy Web Dashboard (Mở trình duyệt)
echo     [3]  🦅  Chế độ Hunt Mode (Săn lùng dự án hàng loạt)
echo     [4]  🛡️  Chế độ PR Patrol (Tuần tra ^& Tự chữa lành CI)
echo     [5]  🎯  Nhắm mục tiêu cụ thể (Nhập URL Repo)
echo     [6]  📊  Xem trạng thái hệ thống chi tiết (System Status)
echo     [7]  🧹  Dọn dẹp Fork không còn dùng (Cleanup)
echo     [8]  🏆  Bảng xếp hạng đóng góp (Leaderboard)
echo.
echo     [0]  ❌  Thoát chương trình
echo.
echo  ══════════════════════════════════════════════════════════════════
echo.
set /p choice="  👉  Nhập lựa chọn của bạn [0-8]: "

if "%choice%"=="1" goto :superhuman
if "%choice%"=="2" goto :dashboard
if "%choice%"=="3" goto :hunt
if "%choice%"=="4" goto :patrol
if "%choice%"=="5" goto :target
if "%choice%"=="6" goto :sysinfo
if "%choice%"=="7" goto :cleanup
if "%choice%"=="8" goto :leaderboard
if "%choice%"=="0" goto :exit

echo.
echo  ⚠️  Lựa chọn không hợp lệ! Vui lòng nhập số từ 0 đến 8.
timeout /t 2 >nul
goto :menu

:: ═══════════════════════════════════════════════════════════════
:: [1] Web Dashboard
:: ═══════════════════════════════════════════════════════════════
:dashboard
cls
echo.
echo  ┌──────────────────────────────────────────────────────────────────┐
echo  │  🌐  KHỞI CHẠY WEB DASHBOARD                                    │
echo  └──────────────────────────────────────────────────────────────────┘
echo.
echo  ► Đang khởi động máy chủ Dashboard...
echo  ► Truy cập: http://localhost:8080
echo  ► Nhấn Ctrl+C để dừng máy chủ và quay lại menu.
echo.
contribai serve
pause
goto :menu

:: ═══════════════════════════════════════════════════════════════
:: [2] Hunt Mode
:: ═══════════════════════════════════════════════════════════════
:hunt
cls
echo.
echo  ┌──────────────────────────────────────────────────────────────────┐
echo  │  🦅  CHẾ ĐỘ HUNT MODE - SĂN LÙNG DỰ ÁN HÀNG LOẠT             │
echo  └──────────────────────────────────────────────────────────────────┘
echo.
echo  ► Agent sẽ tự động tìm kiếm các repo tiềm năng trên GitHub,
echo    phân tích mã nguồn, và tạo Pull Request đóng góp.
echo  ► Chế độ: Phân tích mã + Giải quyết Issues (both)
echo.
echo  ────────────────────────────────────────────────────────────────
echo.
contribai hunt --mode both
echo.
echo  ════════════════════════════════════════════════════════════════
echo  ✅  Hunt Mode đã hoàn thành!
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
echo  ► Agent sẽ quét tất cả PR đang mở, đọc phản hồi từ maintainer,
echo    tự động sửa code và đẩy cập nhật lên PR.
echo.
echo  ────────────────────────────────────────────────────────────────
echo.
contribai patrol
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
echo  ► Agent sẽ phân tích và tạo đóng góp cho repo này...
echo.
echo  ────────────────────────────────────────────────────────────────
echo.
contribai target %repo_url%
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
contribai sysinfo
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
contribai cleanup
echo.
echo  ════════════════════════════════════════════════════════════════
echo  ✅  Dọn dẹp hoàn thành!
echo  ════════════════════════════════════════════════════════════════
pause
goto :menu

:: ═══════════════════════════════════════════════════════════════
:: [7] Leaderboard
:: ═══════════════════════════════════════════════════════════════
:leaderboard
cls
echo.
echo  ┌──────────────────────────────────────────────────────────────────┐
echo  │  🏆  BẢNG XẾP HẠNG ĐÓNG GÓP                                    │
echo  └──────────────────────────────────────────────────────────────────┘
echo.
contribai leaderboard
echo.
echo  ════════════════════════════════════════════════════════════════
pause
goto :menu

:: ═══════════════════════════════════════════════════════════════
:: [8] Super Human Mode
:: ═══════════════════════════════════════════════════════════════
:superhuman
cls
echo.
echo  ┌──────────────────────────────────────────────────────────────────┐
echo  │  🧠  CHẾ ĐỘ SUPER HUMAN - TỰ ĐỘNG 24/7                        │
echo  └──────────────────────────────────────────────────────────────────┘
echo.
echo  ► Agent sẽ hoạt động như một lập trình viên thực thụ:
echo    - Tự đặt hạn mức PR ngẫu nhiên mỗi ngày (2-5 PRs)
echo    - Xen kẽ Hunt Mode và PR Patrol một cách tự nhiên
echo    - Nghỉ ngơi với thời gian ngẫu nhiên giữa các hành động
echo    - Tự động chuyển sang Patrol khi đạt hạn mức
echo  ► Nhấn Ctrl+C để dừng.
echo.
echo  ────────────────────────────────────────────────────────────────
echo.
contribai superhuman
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
echo  ║   🙏  CẢM ƠN BẠN ĐÃ SỬ DỤNG CONTRIBAI!                       ║
echo  ║                                                                ║
echo  ║   ► Tiếp tục đóng góp cho cộng đồng mã nguồn mở!             ║
echo  ║   ► GitHub: https://github.com/your-org/contribai              ║
echo  ║                                                                ║
echo  ╚══════════════════════════════════════════════════════════════════╝
echo.
timeout /t 3 >nul
endlocal
exit /b 0
