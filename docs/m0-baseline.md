# M0 — baseline trước khi sửa các cổng bảo mật

Ngày ghi nhận: 2026-09-25. Checkout `main` tại `41fa72c13cd15e3913f957aa5ef981d2c1861b16`, cộng các thay đổi M0 chưa commit. M0 chỉ đo và chuẩn bị dữ liệu kiểm chứng; không thay đổi quyết định bảo mật của pipeline.

## Đường đi thực tế

| Lệnh/nguồn | Đường xử lý | Đầu ra có tác động |
| --- | --- | --- |
| `run`, `target`, `hunt` (nhánh analysis) | `farm_agent/cli/main.py` → `FarmAgentPipeline.run/run_single/hunt` → `_process_repo` → `_process_repo_impl` | `PRManager.create_pr`, `handle_responsible_disclosure` |
| `hunt-circular`, `superhuman` | `main.py` hoặc `orchestrator/human.py` → `run_circular` → `BloodhoundAnalyzer.run_bloodhound` → sinh bản vá/QA | `PRManager.create_pr`, `handle_responsible_disclosure` |
| `hunt` (nhánh issues), `solve` | `_process_repo_issues` / `IssueSolver` | issue hoặc PR; chưa thuộc telemetry M0 cho nhánh bảo mật |
| `patrol`, vòng `superhuman` | `PRPatrol.patrol` | phản hồi review và sửa CI; chưa thuộc telemetry M0 |

Hai pipeline săn lỗi hiện có chính sách xác minh khác nhau. `run_circular` có thể đánh dấu `COMPLETED_NO_VULN` khi không có kết quả prefilter. `_process_repo_impl` có nhánh tạo fix dù PoC thiếu hoặc lỗi, và giới hạn hai finding sau validation. M0 **không sửa** các hành vi này; M1 phải xử lý.

## Kết quả trước thay đổi M0

Môi trường: Python 3.14.2, pytest 8.4.2, Ruff 0.15.6 trên Windows. `pyproject.toml` yêu cầu Python >=3.11.

| Kiểm tra | Kết quả baseline | Diễn giải |
| --- | --- | --- |
| `python -m pytest -q` | 59 qua, 22 lỗi | Pytest không tạo được thư mục tại `%TEMP%/pytest-of-USER` do quyền truy cập. Đây là lỗi môi trường, không phải kết quả kiểm thử sản phẩm. |
| `python -m pytest -q --basetemp .pytest-m0-tmp --tb=short` | 81 qua, 1 warning | Warning `AsyncMock` chưa await trong `test_async_io_pipeline.py` đã tồn tại. Không chạy Docker, pentest hoặc API trả phí. |
| `python -m ruff check . --output-format concise` | 707 lỗi | Nợ lint hiện hữu toàn repo; không dùng tổng số này để quy lỗi cho M0. |

Sau thay đổi M0, lệnh pytest dùng `--basetemp` chạy **84 qua, 1 warning** (81 cũ + 3 bài kiểm tra M0). Chỉ các tệp mới được yêu cầu Ruff sạch; nợ lint ở `pipeline.py` và `memory.py` vẫn tồn tại và cần so sánh theo dòng thay đổi ở các mốc tiếp theo.

## Corpus và cách đo

`tests/corpus/manifest.json` khai báo bốn cặp vulnerable/fixed: IDOR hai tenant, SQLi, SSRF nội bộ, path traversal. `tests/corpus/targets.py` triển khai hoàn toàn offline; `tests/unit/test_m0_corpus.py` xác nhận mỗi cặp có kết quả khác biệt và kiểm soát benign vẫn hoạt động. Các control case về repo sạch, hai lỗi trong cùng file, thiếu phụ thuộc, scanner timeout và lỗi tạo PoC hiện là **nhãn ground truth để bổ sung fixture pipeline ở M1–M3**, chưa phải phép đo recall của Agent-Farm.

Chạy lại corpus: `python -m pytest -q tests/unit/test_m0_corpus.py --basetemp .pytest-m0-tmp`.

Không suy ra precision/recall từ số bài unit test qua. Benchmark sau này phải chạy Agent-Farm trên corpus, đối chiếu từng candidate với ground truth và báo mẫu số theo loại lỗi, commit, phiên bản model/prompt/sensor.

## Sự kiện đo đạc

SQLite `scan_events` có `scan_id`, `candidate_id` (hash tạm của repo/path/title), `pipeline`, `stage`, `outcome`, `reason_code`, `count`, `duration_ms`, `model`, token và USD. Hai nhánh chính ghi thời điểm bắt đầu/kết thúc; nhánh chuẩn ghi số sau analysis, lọc đường dẫn, lọc impact, candidate cap, dedupe, validation, appraisal, PoC và generation; nhánh circular ghi prefilter, context filter, generation và QA. Mã nguồn, prompt, phản hồi LLM và PoC không được lưu vào bảng này. Đọc bản tóm tắt: `python scripts/m0_report.py data/memory.db` hoặc thêm `--scan-id <id>`.

`input_tokens`, `output_tokens`, `cost_usd` và `model` hiện để `NULL`: provider đang trả về văn bản nhưng chưa cung cấp usage metadata cho pipeline. `NULL` nghĩa là **chưa đo**, không phải 0. M4 phải nối usage thực từ CommandCode Provider API. Hash `candidate_id` ở M0 chỉ để liên kết sự kiện trong một baseline; M1 sẽ có ID candidate theo scan/commit và bảng evidence riêng. Sự kiện M0 được ghi best effort; lỗi ghi DB được log nhưng không thay đổi kết quả quét.

## Tiêu chí qua M0 và bước tiếp theo

- Có sơ đồ CLI → hai đường quét → PR/patrol và mốc baseline test/lint tách riêng.
- Corpus offline có oracle kiểm tra được cho bốn cặp vulnerable/fixed; các scenario lỗi đã có nhãn để M1 thêm fixture thực thi.
- Có `scan_id`, số lượng ở các cổng chính, thời gian quét và reason code không chứa dữ liệu nhạy cảm; trường chi phí thiếu được biểu diễn rõ là chưa đo.
- M1 phải thêm state `CONFIRMED`, `RULED_OUT`, `OPEN_PROOF_GAP`, kiểm tra lỗi scanner/PoC thực thi, và chặn fix/PR/disclosure khi proof thiếu ở **cả hai** pipeline. M0 không được dùng làm bằng chứng rằng hệ thống đã an toàn để tự động công bố.
