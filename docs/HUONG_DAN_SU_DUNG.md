# 🇻🇳 Hướng Dẫn Cài Đặt & Sử Dụng Farm-Agent

> **Farm-Agent** là AI Agent tự động đóng góp vào các dự án mã nguồn mở trên GitHub — tìm repo, phân tích lỗi, tạo bản sửa, và gửi Pull Request hoàn toàn tự động.

---

## 📋 Mục Lục

1. [Yêu cầu hệ thống](#-1-yêu-cầu-hệ-thống)
2. [Cài đặt](#-2-cài-đặt)
3. [Lấy API Keys](#-3-lấy-api-keys)
4. [Cấu hình](#-4-cấu-hình)
5. [Sử dụng cơ bản](#-5-sử-dụng-cơ-bản)
6. [Các chế độ nâng cao](#-6-các-chế-độ-nâng-cao) *(bao gồm Super Human Mode)*
7. [Quản lý & theo dõi](#-7-quản-lý--theo-dõi)
8. [Chạy với Docker](#-8-chạy-với-docker)
9. [Câu hỏi thường gặp](#-9-câu-hỏi-thường-gặp)

---

## 🔧 1. Yêu Cầu Hệ Thống

| Yêu cầu | Phiên bản |
|---|---|
| Python | 3.11 trở lên |
| Git | Bất kỳ |
| pip | Đi kèm Python |

Kiểm tra phiên bản Python:

```bash
python --version
# Kết quả mong đợi: Python 3.11.x hoặc cao hơn
```

---

## 📦 2. Cài Đặt

### Bước 1: Tải mã nguồn

```bash
git clone https://github.com/tang-vu/Farm-Agent.git
cd Farm-Agent
```

### Bước 2: Cài đặt Farm-Agent

```bash
pip install -e ".[dev]"
```

> **Giải thích:** Lệnh này cài đặt Farm-Agent ở chế độ phát triển (`-e`) cùng với các công cụ kiểm thử (`[dev]`).

### Bước 3: Kiểm tra cài đặt thành công

```bash
farm_agent info
```

Nếu thấy thông tin hệ thống hiển thị → cài đặt thành công ✅

---

## 🔑 3. Lấy API Keys

Farm-Agent cần **2 API key**: một cho GitHub và một cho LLM (mô hình AI).

### 3.1 GitHub Token

1. Truy cập: https://github.com/settings/tokens
2. Nhấn **"Generate new token (classic)"**
3. Đặt tên: `Farm-Agent`
4. Chọn các quyền (scopes):
   - ✅ `repo` (toàn bộ)
   - ✅ `delete_repo` (để dọn fork)
   - ✅ `read:org`
5. Nhấn **Generate token** → Sao chép token (bắt đầu bằng `ghp_...`)

### 3.2 LLM API Key (chọn 1 trong các nhà cung cấp)

| Nhà cung cấp | Cách lấy key | Ghi chú |
|---|---|---|
| **Gemini** (mặc định, khuyên dùng) | https://aistudio.google.com/apikey | Miễn phí |
| OpenAI | https://platform.openai.com/api-keys | Trả phí |
| Anthropic | https://console.anthropic.com | Trả phí |
| Minimax | https://platform.minimaxi.com | Trả phí |
| Ollama | Không cần key — chạy local | Miễn phí |

---

## ⚙️ 4. Cấu Hình

### Bước 1: Tạo file cấu hình

```bash
cp config.example.yaml config.yaml
```

### Bước 2: Mở và chỉnh sửa `config.yaml`

```yaml
# === BẮT BUỘC ===
github:
  token: "ghp_xxxxxxxxxxxxxxxx"    # ← Dán GitHub token vào đây

llm:
  provider: "gemini"                # ← Nhà cung cấp AI (gemini/openai/anthropic/minimax/ollama)
  model: "gemini-2.5-flash"         # ← Tên model
  api_key: "AIzaxxxxxxxxxxxxxxxx"   # ← Dán LLM API key vào đây

# --- Ví dụ cầu hình Minimax ---
# llm:
#   provider: "minimax"
#   model: "MiniMax-M2.7"
#   api_key: "ey-..."
#   minimax_group_id: "12345..."    # ← Bắt buộc đối với Minimax, nếu lỗi API, Farm-Agent sẽ retry với backoff

logging:
  level: "INFO"                     # Mức log (DEBUG, INFO, WARNING, ERROR)
  log_dir: "logs"                   # Thư mục lưu nhật ký (sẽ tự tạo nếu không có, cần cấp quyền write)
  keep_days: 30                     # Số ngày tự động giữ file log rolling theo ngày

# === TÙY CHỌN ===
discovery:
  languages:                        # ← Ngôn ngữ lập trình muốn tìm
    - python
    - javascript
  stars_range: [50, 10000]          # ← Phạm vi sao (50 đến 10,000)
```

### Cách khác: Dùng biến môi trường (không cần sửa file)

```bash
# Windows (PowerShell)
$env:GITHUB_TOKEN = "ghp_xxxxxxxxxxxxxxxx"
$env:GEMINI_API_KEY = "AIzaxxxxxxxxxxxxxxxx"

# Linux / macOS
export GITHUB_TOKEN="ghp_xxxxxxxxxxxxxxxx"
export GEMINI_API_KEY="AIzaxxxxxxxxxxxxxxxx"
```

---

## 🚀 5. Sử Dụng Cơ Bản

### 5.1 Chạy thử (Dry Run) — Xem trước, KHÔNG tạo PR

```bash
farm_agent run --dry-run
```

> ⚠️ **Luôn chạy thử trước** để xem Farm-Agent sẽ làm gì trước khi tạo PR thật.

### 5.2 Chạy tự động (Full Run)

```bash
farm_agent run
```

Farm-Agent sẽ tự động:
1. 🔍 Tìm repo phù hợp trên GitHub
2. 📊 Phân tích mã nguồn (bảo mật, chất lượng, tài liệu, UI/UX)
3. 🔧 Tạo bản sửa lỗi
4. 📬 Gửi Pull Request

### 5.3 Nhắm vào 1 repo cụ thể

```bash
# Xem trước
farm_agent target https://github.com/owner/repo --dry-run

# Chạy thật
farm_agent target https://github.com/owner/repo
```

---

## 🎯 6. Các Chế Độ Nâng Cao

### 6.1 Hunt Mode — Săn tìm & đóng góp hàng loạt

```bash
# Chạy 1 lần
farm_agent hunt

# Chạy 5 vòng, nghỉ 15 phút giữa mỗi vòng
farm_agent hunt --rounds 5 --delay 15

# Chỉ phân tích code (không giải issue)
farm_agent hunt --mode analysis

# Chỉ giải quyết issue
farm_agent hunt --mode issues

# Cả hai (mặc định)
farm_agent hunt --mode both
```

### 6.2 PR Patrol — Theo dõi & phản hồi review

```bash
farm_agent patrol
```

Tự động:
- Đọc comment của maintainer trên PR đã gửi
- Phân loại phản hồi (sửa code / câu hỏi / chấp nhận / từ chối)
- Tạo và push bản sửa nếu cần
- Đóng PR & đưa repo vào danh sách đen nếu bị từ chối thô bạo

### 6.3 Giải quyết Issue

```bash
farm_agent solve https://github.com/owner/repo
```

### 6.4 Lọc theo ngôn ngữ

```bash
farm_agent run --language python
farm_agent run --language javascript
```

### 6.5 CI Auto-Healing (Tự Động Sửa Lỗi CI)

Trong chế độ `patrol`, Farm-Agent tự động giám sát các GitHub Action / CI checks của PR:
- Nếu một CI/Check Run bị lỗi (Failed), Farm-Agent tự động tải nguyên văn file log gốc từ GitHub (trích xuất chính xác Traceback mã lỗi, xử lý an toàn redirect hoặc 404/410).
- Sau khi có lỗi, AI chạy vòng lặp Agentic Loop (ReAct) tự chẩn đoán nguyên nhân và push thêm commit nhằm fix lỗi đè lên branch đó.
- **Cơ chế dự phòng (Zero-Tolerance Safe Fallback):** Farm-Agent cho phép fix lặp lại tối đa 2 lần (`MAX_CI_FIX_ATTEMPTS=2`). Đến lần thất bại thứ 3, hệ thống sẽ thay mặt bạn tự động đóng (Close) PR để tránh spam repo của maintainer.

### 6.6 Style Mimicry & Architectural Awareness (Nhận Thức Cấu Trúc Toàn Diện)

Bạn có thể tin tưởng Farm-Agent không bao giờ sinh ra những file mã nguồn bị thiếu hụt Context (Hallucinations) là nhờ:
1. **RepoMapper (Project Map):** Bất cứ khi làm việc, Tool `mapper.py` trước tiên sẽ quét toàn bộ kho dự án, đọc cú pháp (AST/Regex) và cấp cho LLM một bảng sơ đồ toàn diện cực nhỏ gọn các danh sách đường dẫn, Class và function signatures.
2. **Khớp Chữ Ký Hàm (Signature Match) & Bắt Chước:** Dựa trên Map này, System Prompt ép AI phải cross-reference (kiểm tra chéo) gọi đúng các hàm có thật từ hệ thống thay vì tự tưởng tượng thêm hàm mới. Phong cách code được bắt chước 100%.
3. **LLM Tool Calling Loop (Đọc File Động):** Trong quá trình sinh mã, nếu LLM nhận ra một function class chưa nhìn thấy Body (nội dung), LLM sẽ báo lệnh công cụ `read_file` đến server. Hệ thống tự quét GitHub lấy code nguyên vẹn đẩy vào Context (giới hạn tối đa 3 lần loop: `MAX_TOOL_CALLS = 3`) trước khi AI hoàn thiện file PR cuối cùng.

### 6.7 🧠 Chế Độ Super Human — Mô Phỏng Lập Trình Viên 24/7

**Tại sao cần Super Human Mode?**

GitHub có hệ thống phát hiện spam dựa trên hành vi bất thường: nếu một tài khoản tạo PR liên tục với tần suất đều đặn như máy, tài khoản sẽ bị flag. Super Human Mode giải quyết vấn đề này bằng cách mô phỏng nhịp sinh học của một lập trình viên thực — làm việc, nghỉ ngơi, uống cà phê, lướt web — với thời gian hoàn toàn ngẫu nhiên.

**Cơ chế hoạt động:**

| Thông số | Giá trị | Mục đích |
|----------|---------|----------|
| Hạn mức PR/ngày | Ngẫu nhiên 2–5 PRs | `random.randint(2, 5)` — mỗi ngày khác nhau |
| An toàn tuyệt đối | Tối đa 6 PRs/ngày | `ABSOLUTE_MAX_PRS_PER_DAY = 6` — không bao giờ vượt |
| Tỷ lệ hành động | Hunt 60% / Patrol 40% | Xúc xắc ngẫu nhiên quyết định mỗi iteration |
| Nghỉ sau Hunt | 30–90 phút | Giả lập phiên coding sâu |
| Nghỉ sau Patrol | 10–30 phút | Giả lập check inbox nhanh |
| Chế độ Patrol-Only | 1–3 giờ giữa mỗi lần | Khi đạt quota, chỉ trả lời review |
| Stress break | 15 phút | Tự nghỉ khi gặp lỗi API GitHub |

**Cách chạy:**

```bash
# Chạy 24/7 (production) — nhấn Ctrl+C để dừng
farm_agent superhuman

# Chạy thử nhanh (10 iterations, delays 1-3 giây)
farm_agent superhuman --time-warp

# Chạy thử KHÔNG tạo PR thật
farm_agent superhuman --time-warp --dry-run
```

**Hoặc qua Command Center** (`start.bat`):
- Chọn **[8] 🧠 Chế độ Super Human** từ menu chính.

**Persona "Lập trình viên Việt Nam":**

Terminal sẽ hiển thị log bằng tiếng Việt tự nhiên, ngẫu nhiên từ 40+ câu trong 11 trạng thái khác nhau (`HUMAN_THOUGHTS`). Ví dụ:

```
☀️ Trời sáng rồi! Pha ly cà phê đen rồi xem hôm nay open-source có gì vui không... (Mục tiêu: 4 PRs)
📋 Check-in iteration 1: 0/4 PRs. Vẫn trong quota, let's go!
🎲 Tung xúc xắc... 35% → chọn HUNT 🦅! (Hunt < 60% / Patrol ≥ 60%)
💪 Vươn vai cái nào! Bắt đầu tìm repo để fix bug thôi.
✅ Hunt xong! Đã phân tích 1 repo(s), tạo 1 PR(s). Cũng tạm ổn!
😅 Fix bug mỏi mắt quá. Đi lướt web 45 phút rồi quay lại làm tiếp.
🏁 Hôm nay làm đủ KPIs rồi (4/4 PRs). Giờ chỉ ngồi trực canh comment thôi...
```

> ⚠️ **Lưu ý:** Luôn chạy `--time-warp --dry-run` trước khi chạy production để xác nhận cấu hình LLM và GitHub token hoạt động đúng.

---

## 📊 7. Quản Lý & Theo Dõi

```bash
farm_agent status     # Xem trạng thái PR đã gửi
farm_agent stats      # Thống kê tổng quan
farm_agent info       # Thông tin hệ thống
farm_agent cleanup    # Xóa fork cũ không còn PR mở
```

### Web Dashboard (Bảng điều khiển web)

```bash
farm_agent serve                  # Mở dashboard tại http://localhost:8787
farm_agent serve --port 9000      # Đổi cổng
```

### Lên lịch chạy tự động

```bash
farm_agent schedule --cron "0 */6 * * *"    # Chạy mỗi 6 giờ
```

---

## 🐳 8. Chạy Với Docker

```bash
# Khởi động dashboard
docker compose up -d dashboard

# Chạy 1 lần
docker compose run --rm runner run

# Dashboard + lịch tự động
docker compose up -d dashboard scheduler
```

---

## ❓ 9. Câu Hỏi Thường Gặp

### Q: Dùng nhà cung cấp AI nào tốt nhất?

**Gemini** (mặc định) — miễn phí, nhanh, hỗ trợ context dài 1M token. Khuyên dùng cho người mới.

### Q: Làm sao để tránh spam PR?

- Luôn chạy `--dry-run` trước
- Giới hạn PR/ngày trong `config.yaml`: `max_prs_per_day: 10`
- Farm-Agent đã có hệ thống chống trùng lặp và kiểm tra chất lượng tự động
- **Khuyến nghị:** Dùng `farm_agent superhuman` — tự động giới hạn 2–5 PRs/ngày với delays ngẫu nhiên, mô phỏng hành vi con người để tránh bị GitHub flag

### Q: Làm sao để dùng model local (Ollama)?

```yaml
llm:
  provider: "ollama"
  model: "codellama:13b"
  base_url: "http://localhost:11434"
```

Cài Ollama trước: https://ollama.com

### Q: Lệnh nào an toàn nhất để chạy lần đầu?

```bash
farm_agent run --dry-run
```

Lệnh này chỉ **xem trước** kết quả, không tạo bất kỳ PR nào.

### Q: Làm sao chạy test?

```bash
pytest tests/ -v                    # Chạy toàn bộ test
pytest tests/ -v --cov=farm_agent    # Chạy test + đo coverage
```

---

> 💡 **Mẹo:** Bắt đầu với `farm_agent target <repo-url> --dry-run` để hiểu cách Farm-Agent hoạt động trước khi chạy hunt mode.
