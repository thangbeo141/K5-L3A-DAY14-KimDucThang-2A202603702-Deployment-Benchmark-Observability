# Benchmark & Observability Report — Day 14

> Copy file này thành `BENCHMARK_REPORT.md` trong repo của bạn và điền đầy đủ.
> Mọi con số phải lấy từ report JSON / CSV / screenshot thật, không ước lượng.

**Họ tên:** Kim Đức Thắng (2A202603702)
**Ngày chạy:** 25/11/2026
**Môi trường:** Windows + WSL2 Ubuntu 26.04, Docker Desktop

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | < 500 ms | Đảm bảo trải nghiệm phản hồi nhanh cho 95% người dùng (theo ngưỡng `load_test.py`). |
| Error rate `/ask` | < 2.0 % | Cho phép sai số nhỏ từ lỗi upstream tạm thời (`MOCK_ERROR_RATE=0.01`) mà vẫn giữ độ tin cậy ≥ 98%. |
| Accuracy trên golden dataset | ≥ 80 % (mục tiêu 100%) | Đảm bảo chất lượng câu trả lời không bị regression trước khi deploy. |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 5.05 | 189.5 | 216.0 | 223.9 | 1.00% | PASS |
| 10 | 36.73 | 187.2 | 218.2 | 1693.9 | 0.33% | PASS |
| 50 | 104.03 | 197.9 | 276.7 | 1728.7 | 3.00% | FAIL (error rate) |
| 100 | 75.07 | 275.5 | 2035.6 | 2256.9 | 0.33% | FAIL (p95) |

**Nhận xét:** RPS có tăng tuyến tính theo concurrency không? Vì sao?

Không tăng tuyến tính mãi: từ c=1 (5.05 RPS) lên c=10 (36.73 RPS) và c=50 (104.03 RPS) thì tăng mạnh nhờ xử lý bất đồng bộ, nhưng lên c=100 lại giảm xuống 75.07 RPS và p95 vọt từ 276.7 ms lên 2035.6 ms do nghẽn tài nguyên CPU/event loop khi có quá nhiều request đồng thời (saturation point).

### 2.2 Tail latency

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 203.9 | 413.3 | 466.9 |
| 0.03 (mặc định) | 240.1 | 221.3 | 1695.5 |
| 0.1 | 365.6 | 1696.7 | 1720.0 |

**Nhận xét:** Chỉ số nào nhạy nhất với request chậm? Vì sao SLO không nên đặt theo average?

`p99` (và `p95` khi slow rate ≥ 10%) nhạy nhất với request chậm: chỉ 3% request chậm đã làm p99 tăng từ 466.9 ms lên 1695.5 ms, trong khi `avg` chỉ nhích nhẹ từ 203.9 ms lên 240.1 ms. Nếu đặt SLO theo average thì sẽ che giấu hoàn toàn trải nghiệm tệ của nhóm người dùng gặp tail latency.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.3% (1/23) | 91.3% (21/23) | 100.0% (23/23) |
| Avg tokens / câu | 57.1 | 109.0 | 113.6 |
| Tổng cost (USD) | $0.000404 | $0.000760 | $0.000790 |
| Cost / câu đúng (USD) | $0.00040395 | $0.00003619 | $0.00003436 |
| Quality gate | FAIL | PASS (min 80%) | PASS (min 100%) |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| `security-02` | `token`, `hết hạn`, `chữ ký` | Thêm entry cho từ khoá `"jwt"` vào `KNOWLEDGE_BASE` trong `develop/utils/mock_llm.py` giải thích JWT là token tự chứa claims, có thời gian hết hạn và xác minh bằng chữ ký số. |
| `scaling-03` | `cpu`, `memory`, `custom metrics` | Thêm entry cho từ khoá `"hpa"`, `"kubernetes"` vào `KNOWLEDGE_BASE` mô tả HPA scale dựa trên CPU, memory và custom metrics. |

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:**

Agent v2 thêm bước retrieval từ `KNOWLEDGE_BASE` nên tốn thêm ~20 ms latency và tăng gần gấp đôi tổng token/cost ($0.000790 vs $0.000404). Tuy nhiên, accuracy tăng vọt từ 4.3% lên 100.0%, làm **cost / câu đúng** giảm hơn 11 lần ($0.00003436 so với $0.00040395 của v1).

**CI Quality Gate (Exercise 7.3):** Trong CI/CD (GitHub Actions), chạy `python eval/run_eval.py --url http://localhost:8002 --min-accuracy 0.8 --baseline reports/eval_v2.json`. Script trả về **exit code khác 0 (`1`)** nếu accuracy dưới ngưỡng hoặc có bất kỳ câu nào bị regression, giúp pipeline tự động chặn merge PR/deploy.

---

## 4. Observability stack (production)

### 4.1 Screenshot

- [x] Dashboard Grafana khi đang có tải (thấy rõ Golden Signals: `9.3 req/s`, `19.41%` error, `1.93 s` p95, `$1.6035` cost) — [grafana-dashboard.png](screenshots/grafana-dashboard.png)
- [x] Một trace chậm trong Jaeger (thấy span nào chiếm thời gian: `chat mock-llm-large` chiếm ~99%) — [jaeger-slow-trace.png](screenshots/jaeger-slow-trace.png)
- [x] Một trace lỗi trong Jaeger (POST `/ask` 503 có badge đỏ trên `chat mock-llm-large`) — [jaeger-error-trace.png](screenshots/jaeger-error-trace.png)
- [x] Trang Alerts của Prometheus với 3 alerts đang **firing** (`AgentHighErrorRate`, `AgentHighLatencyP95`, `LLMCostBurnRateHigh`) — [prometheus-alert-firing.png](screenshots/prometheus-alert-firing.png)

### 4.2 Thí nghiệm "phá hệ thống"

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` | ~1–2 phút (`for: 1m`, quan sát trên Prometheus lúc 22:18) | Error rate (`19.41%`) & Requests/s theo status code (`503`) |
| B | `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` | ~2–3 phút (`for: 2m`, quan sát trên Prometheus lúc 22:18) | Latency p95 (`1.93 s`) & biểu đồ `p50 / p95 / p99` |
| C | `LLM_MODEL=mock-llm-large` | `LLMCostBurnRateHigh` | ~2–3 phút (`for: 2m`, quan sát trên Prometheus lúc 22:18) | LLM cost (`$1.6035`) |
| D | `docker pause` 1 instance | `AgentInstanceDown` *(theo `alert_rules.yml`)* | Chưa chạy trực tiếp (theo rule `for: 30s` + scrape interval 5s → ~35s) | Instances (`up{job="agent"}`) |
| E | `AGENT_VERSION=v1` | Không có alert nào | N/A | Chỉ thấy qua Accuracy / Eval |

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

Alert hạ tầng (error rate, latency, CPU) không phát hiện được suy giảm chất lượng câu trả lời (silent regression). Cần chạy **Eval chất lượng tự động (CI Quality Gate)** trên golden dataset trước khi deploy, kết hợp theo dõi user feedback (thumbs up/down), LLM-as-a-judge sampling online, hoặc theo dõi tỉ lệ fallback/độ dài câu trả lời theo từng `agent_version`.

### 4.3 Debug bằng trace

Chọn 1 trace chậm tìm được (khớp ảnh `screenshots/jaeger-slow-trace.png`):

- `trace_id`: `17fd797c276c8d04c8455b1769d0fc97`
- Tổng thời gian: `1863.0` ms (~`1.9s` trên Jaeger UI, `POST /ask`, status `200`)
- Span chiếm nhiều thời gian nhất: `chat mock-llm-large` (`1844.1` ms, chiếm **99.0%** tổng thời gian; so với `agent.retrieve_context` chỉ mất `17.4` ms)
- Dòng log tương ứng (grep theo `trace_id`):

```json
{"ts": "2026-11-25T15:20:10.921073+00:00", "level": "INFO", "service": "observable-agent", "instance": "568a2082aa96", "event": "http_request", "trace_id": "17fd797c276c8d04c8455b1769d0fc97", "span_id": "d65ca7ee345e6ac6", "request_id": "d79587d7c7a7", "method": "POST", "route": "/ask", "status": 200, "ms": 1863.0}
```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | 37.18 | 210 | 6000 | 8500 | 318 (7.15%) |
| 3 | 62.93 | 190 | 950 | 2700 | 66 (0.88%) |

**Giải thích kết quả:** Scale có cải thiện p95 không? Nút thắt nằm ở đâu?

Scale từ 1 lên 3 instance cải thiện rõ rệt cả throughput lẫn tail latency: tổng RPS tăng từ **37.18** lên **62.93 req/s**, **p95 giảm từ 6000 ms xuống 950 ms**, và tỉ lệ lỗi giảm từ **7.15%** (có 277 lỗi `502 Bad Gateway` do 1 instance quá tải không nhận nổi kết nối từ Nginx) xuống còn **0.88%** (chỉ còn 66 lỗi `503` từ `MOCK_ERROR_RATE=0.01`, không còn `502`). Nút thắt ở `scale=1` là giới hạn CPU (`0.5` CPU) và 1 worker process của container agent duy nhất; khi scale lên 3 instance, Nginx chia tải ra 3 container nên hết nghẽn.

---

## 6. Kết luận

- 3 điều bạn học được về benchmark & observability:
  1. **Tail latency quan trọng hơn average:** Chỉ 3–10% request chậm đã đẩy `p99` tăng vọt (~1.7 s) trong khi `avg` thay đổi rất ít, nên SLO phải đặt theo `p95`/`p99`.
  2. **Đo cả hiệu năng lẫn chất lượng và chi phí:** Scale giúp giảm mạnh p95 (từ 6000 ms xuống 950 ms) và loại bỏ lỗi 502, nhưng một thay đổi phiên bản (`v2` vs `v1`) có thể làm tụt accuracy nghiêm trọng mà alert hạ tầng không phát hiện ra — cần eval tự động (CI quality gate) và theo dõi `cost / câu đúng`.
  3. **Liên kết 3 trụ cột Metrics – Traces – Logs:** Prometheus/Grafana báo *khi nào* hệ thống lỗi hoặc chậm, còn `trace_id` gắn trong JSON logs và Jaeger giúp khoanh vùng ngay *span* nào gây nghẽn (`chat mock-llm-large` chiếm 99.0% thời gian).
- Nếu đưa agent này lên production thật, bạn sẽ thêm metric / alert nào nữa?
  - Thêm metric & alert cho **Redis latency / connection errors** (tránh nghẽn rate limit và cost guard), **tỉ lệ rate-limit 429 & budget-exceeded 402**, **token input/output per request** (phát hiện prompt injection/context phình to), và **online eval / user feedback score** để bắt suy giảm chất lượng sớm.
