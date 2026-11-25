# Day 14 Lab - Mission Answers

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found in `01-localhost-vs-production/develop/app.py`
1. **Hardcoded secrets (dòng 17–18):** `OPENAI_API_KEY = "sk-hardcoded-fake-key-never-do-this"` và `DATABASE_URL = "postgresql://admin:password123@localhost:5432/mydb"` ghi trực tiếp trong source code — nếu push lên GitHub sẽ lộ ngay. Đã sửa ở `production/config.py` & `production/.env.example` bằng cách đọc từ biến môi trường.
2. **Không có config management (dòng 21–22):** `DEBUG = True` và `MAX_TOKENS = 500` được gán cứng trong code thay vì đọc qua `Settings` từ environment variables.
3. **Dùng `print()` và log lộ secret (dòng 33–34, 38):** Dùng `print(f"[DEBUG] Using key: {OPENAI_API_KEY}")` vừa khó parse khi lên production vừa làm lộ API key ra log. Đã sửa ở `production/app.py` (dòng 28–32, 111–122) bằng structured JSON logging và không log secret.
4. **Không có health check / readiness endpoint (dòng 42–43):** Không có `/health` hay `/ready` nên platform (Docker/Railway/Render/K8s) không biết container còn sống hay sẵn sàng nhận traffic chưa. Đã thêm `/health` (dòng 135–149) và `/ready` (dòng 152–161) trong `production/app.py`.
5. **Host/Port cố định và bật `reload=True` (dòng 49–54):** `host="localhost"` chỉ nhận kết nối nội bộ máy (không chạy được trong Docker/container), `port=8000` không đọc từ `PORT` env var, và `reload=True` bật debug reload trong production. Đã sửa ở `production/app.py` (dòng 194–199) thành `host=settings.host` (`0.0.0.0`), `port=settings.port`, `reload=settings.debug`.
6. **Không xử lý graceful shutdown:** Khi tắt tiến trình bằng `SIGTERM`, request đang chạy có thể bị ngắt đột ngột. Đã sửa ở `production/app.py` bằng `lifespan` (dòng 40–67) và `signal.signal(signal.SIGTERM, handle_sigterm)` (dòng 180–189).

### Exercise 1.2: Kết quả gọi bản `develop`
Lệnh chạy:
```bash
curl -X POST "http://localhost:8000/ask?question=Hello"
```
Output:
```json
{"answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
```

### Exercise 1.3: So sánh `develop` vs `production`
| Feature | Develop (`develop/app.py`) | Production (`production/app.py`) | Tại sao quan trọng? |
| --- | --- | --- | --- |
| Config | Hardcode trực tiếp (`OPENAI_API_KEY`, `DEBUG = True`, `port=8000`) | Đọc từ environment variables qua `config.settings` và `.env` | Tách biệt cấu hình khỏi code (12-Factor App), tránh lộ secret trên Git và dễ đổi giữa dev/staging/prod. |
| Health check | Không có | Có `GET /health` (liveness) và `GET /ready` (readiness, trả 503 khi chưa sẵn sàng) | Giúp orchestrator/load balancer tự động restart container lỗi và chỉ route traffic khi app sẵn sàng. |
| Logging | `print()` plain text, log cả `OPENAI_API_KEY` | Structured JSON logging (`logging` với format JSON), không log secret | Dễ thu thập/tìm kiếm trên Datadog/Loki/ELK và đảm bảo an toàn thông tin. |
| Shutdown | Dừng đột ngột, không có cleanup | `lifespan` + `SIGTERM` handler (`handle_sigterm`) | Cho phép hoàn thành các request đang xử lý (in-flight) trước khi thoát, tránh lỗi cho người dùng khi deploy/scale down. |
| Host / Port | `host="localhost"`, `port=8000`, `reload=True` | `host="0.0.0.0"`, `port=PORT` từ env, `reload=settings.debug` | `0.0.0.0` cần thiết để container nhận traffic từ bên ngoài; `PORT` từ env để tương thích Railway/Render/Cloud Run. |

---

## Part 2: Docker

### Exercise 2.1: Dockerfile questions (`02-docker/develop/Dockerfile`)
1. **Base image:** `python:3.11` (full Python distribution, ~1 GB).
2. **Working directory:** `/app` (`WORKDIR /app`).
3. **Tại sao `COPY requirements.txt` trước `COPY . .` (hoặc copy code)?** Để tận dụng **Docker layer cache**. `requirements.txt` ít thay đổi hơn source code; nếu đặt `COPY requirements.txt` + `RUN pip install` trước, khi sửa code (`app.py`) Docker chỉ cần build lại từ bước `COPY` code mà không phải cài lại toàn bộ thư viện.
4. **CMD vs ENTRYPOINT khác nhau thế nào?**
   - `CMD` cung cấp lệnh/tham số mặc định khi container chạy, và **dễ bị ghi đè** khi truyền tham số lúc `docker run <image> <command>`.
   - `ENTRYPOINT` cố định file thực thi chính của container; các tham số truyền thêm ở `docker run` sẽ được nối vào sau `ENTRYPOINT` (thường kết hợp `ENTRYPOINT` + `CMD` cho default flags).

### Exercise 2.2: Build và run `my-agent:develop`
Lệnh test container:
```bash
curl -X POST "http://localhost:8000/ask?question=What+is+Docker?"
```
Output:
```json
{"answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}
```

### Exercise 2.3: Multi-stage build & so sánh dung lượng
- **Stage 1 (`builder`, `python:3.11-slim`):** Cài build tools (`gcc`, `libpq-dev`) và cài Python packages vào `/root/.local` (`pip install --user`).
- **Stage 2 (`runtime`, `python:3.11-slim`):** Chỉ copy `/root/.local` và source code sang, tạo non-root user `appuser`, không mang theo `gcc` hay build tools/cache.
- **Kích thước đo được bằng `docker images | grep my-agent`:**
  - Develop (`my-agent:develop`): **1.67 GB** (1670 MB; content size 426 MB)
  - Production (`my-agent:advanced`): **240 MB** (content size 57.4 MB)
  - Chênh lệch: giảm **~85.6%** (nhỏ hơn ~7 lần).

### Exercise 2.4: Docker Compose stack (`02-docker/production/docker-compose.yml`)
**Architecture diagram:**
```text
Client (port 80 / 443)
   │
   ▼
[ nginx ] (reverse proxy & load balancer, network: internal)
   │
   ▼
[ agent ] (FastAPI, port 8000, depends_on redis & qdrant healthy)
   ├──▶ [ redis ]  (redis:7-alpine, volume: redis_data)
   └──▶ [ qdrant ] (qdrant/qdrant:v1.9.0, volume: qdrant_data)
```
**Kết quả test qua Nginx (`http://localhost/health`):**
```json
{"status":"ok","uptime_seconds":7.4,"version":"2.0.0","timestamp":"2026-11-25T09:17:10.960952"}
```

---

## Part 3: Cloud Deployment

### Exercise 3.1 / 3.2: Deploy agent Part 6 lên Render
- **Platform:** Render
- **Public URL:** _(Điền sau khi deploy xong)_
- **Screenshots:** `screenshots/dashboard.png`, `screenshots/running.png`, `screenshots/test.png`

### So sánh `railway.toml` vs `render.yaml`
- **`railway.toml` (TOML):** Cấu hình theo từng service riêng lẻ (ở đây chỉ khai báo `[build] builder = "DOCKERFILE"` và `[deploy] healthcheckPath = "/health"`). Biến môi trường và các service phụ như Redis được thêm trực tiếp trên Railway Dashboard/CLI.
- **`render.yaml` (YAML — Blueprint / IaC):** Khai báo toàn bộ kiến trúc nhiều service/database trong một file (`services:` gồm `type: web`, `runtime: docker`, `healthCheckPath: /health`, `envVars:` với `sync: false` hoặc `generateValue: true` cho secret), giúp đồng bộ hạ tầng như Infrastructure as Code khi deploy từ GitHub.

### Exercise 3.3: GCP Cloud Run (`03-cloud-deployment/production-cloud-run/`)
Pipeline CI/CD trong `cloudbuild.yaml` đi qua 4 bước tuần tự (`waitFor`):
1. **`test`:** Dùng `python:3.11-slim` cài dependencies và chạy `pytest tests/ -v`.
2. **`build`:** Build Docker image gắn tag `$COMMIT_SHA` và `latest` (tận dụng `--cache-from`).
3. **`push`:** Đẩy image lên Google Container Registry (`gcr.io/$PROJECT_ID/ai-agent`).
4. **`deploy`:** Chạy `gcloud run deploy ai-agent` lên region `asia-southeast1` với `--min-instances=1` (tránh cold start), `--max-instances=10`, và nạp secret từ Secret Manager (`--set-secrets`). File `service.yaml` định nghĩa cấu hình Knative Service tương ứng (CPU/RAM limits, `containerConcurrency: 80`, `livenessProbe` `/health`, `startupProbe` `/ready`).

---

## Part 4: API Security

### Exercise 4.1: API Key Authentication (`04-api-gateway/develop/app.py`)
- API key được kiểm tra trong dependency `verify_api_key` dùng `APIKeyHeader(name="X-API-Key", auto_error=False)`.
- Thiếu header `X-API-Key` → **401 Unauthorized**; sai key → **403 Forbidden**; đúng key → **200 OK**.
- Rotate key: cập nhật biến môi trường `AGENT_API_KEY` (hoặc hỗ trợ danh sách key cũ/mới trong lúc chuyển đổi) rồi restart/reload service, không hardcode trong code.

**Kết quả `curl -i` bản develop (401 và 200):**
```http
HTTP/1.1 401 Unauthorized
content-type: application/json

{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}
```
```http
HTTP/1.1 200 OK
content-type: application/json

{"question":"Hello","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
```

### Exercise 4.2 & 4.3: JWT Authentication & Rate Limiting (`04-api-gateway/production/`)
- Dùng `POST /auth/token` với tài khoản `student` / `demo123` để lấy JWT Bearer token (đã che token khi gọi API).
- `rate_limiter.py` dùng thuật toán **Sliding Window Counter** (`collections.deque` lưu timestamp trong cửa sổ 60 giây): `student` giới hạn **10 requests/phút**, `admin` là **100 requests/phút**. (Trong production cần lưu vào Redis thay vì RAM để share giữa nhiều instance).

**Kết quả `curl -i` bản production (401, 200, 429):**
- Thiếu token (**401**):
```http
HTTP/1.1 401 Unauthorized
www-authenticate: Bearer
content-type: application/json
x-content-type-options: nosniff
x-frame-options: DENY
```
- Có token hợp lệ (`Authorization: Bearer <REDACTED>`) (**200**):
```http
HTTP/1.1 200 OK
content-type: application/json

{"question":"Explain JWT","answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic.","usage":{"requests_remaining":9,"budget_remaining_usd":2.1e-05}}
```
- Vòng lặp vượt quá 10 requests/phút (request #11 → **429**):
```http
HTTP/1.1 429 Too Many Requests
x-ratelimit-limit: 10
x-ratelimit-remaining: 0
x-ratelimit-reset: 1795598897
retry-after: 58
content-type: application/json

{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":58}}
```

### Exercise 4.4: Cost Guard (`04-api-gateway/production/cost_guard.py`)
- **Cơ chế:** Trước khi gọi LLM chạy `check_budget(user_id)` kiểm tra chi tiêu ngày/tháng (vượt `daily_budget_usd` → trả **402 Payment Required**; vượt `global_daily_budget_usd` → **503**; đạt 80% → ghi log warning). Sau khi gọi LLM xong chạy `record_usage()` cộng dồn input/output tokens và quy đổi ra USD. Trong production phải lưu counter trong Redis (`INCRBYFLOAT` + `EXPIRE`) để không mất khi restart hoặc scale nhiều instance.
- **Tại sao cần cả Rate Limit và Cost Guard?**
  - **Rate limit** bảo vệ **tốc độ / tải hệ thống** (chống spam/DDoS theo số request/phút).
  - **Cost guard** bảo vệ **tiền / ngân sách LLM** (vì 1 request prompt dài có thể tốn rất nhiều token dù tổng số request/phút vẫn dưới rate limit). Cần cả hai để vừa chống quá tải vừa tránh cháy ví.

---

## Part 5: Scaling & Reliability

### Exercise 5.1 & 5.2: Health Check, Readiness Check & Graceful Shutdown (`05-scaling-reliability/develop/app.py`)
- **Liveness (`GET /health`) vs Readiness (`GET /ready`):**
  - `/health` kiểm tra process có còn sống không (trả 200 nếu tiến trình đang chạy). Nếu `/health` lỗi, orchestrator sẽ restart container.
  - `/ready` kiểm tra app đã sẵn sàng nhận traffic chưa (đã load xong hoặc kết nối được Redis/DB chưa; trả **503** nếu chưa sẵn sàng). Load balancer dựa vào `/ready` để ngừng route traffic mới vào instance chưa sẵn sàng hoặc đang tắt.
- **Graceful shutdown:** Khi nhận `SIGTERM`, đặt `_is_ready = False` để load balancer ngừng gửi request mới, sau đó chờ các `_in_flight_requests` hoàn thành (trong `lifespan`) trước khi thoát hoàn toàn, tránh cắt ngang request của user.

### Exercise 5.3, 5.4 & 5.5: Stateless Design, Load Balancing & Test (`05-scaling-reliability/production/`)
- **Tại sao state trong RAM bị hỏng khi scale nhiều instance?** Khi chạy 3 instance (`--scale agent=3`), mỗi container có bộ nhớ RAM riêng. Nginx phân tán các request của cùng 1 session sang nhiều instance khác nhau; nếu lưu `conversation_history` trong dict ở RAM, instance 2 sẽ không thấy lịch sử chat của instance 1. Đưa state ra **Redis** dùng chung giúp mọi instance đều đọc/ghi cùng 1 lịch sử hội thoại.
- **Kết quả chạy `docker compose -p k5-day14-scaling up -d --build --scale agent=3` và `python3 test_stateless.py`:**
  - Session ID: `f5bed695-cac8-4e00-b134-3022eee41c72`
  - 5 request liên tiếp được Nginx phân tán qua các instance khác nhau (`instance-fc70fe`, `instance-279bcf`).
  - Kiểm tra `/chat/{session_id}/history` trả về đủ **10 messages** (5 user + 5 assistant) → `✅ Session history preserved across all instances via Redis!`.

---

## Part 6: Final Project (`06-lab-complete/`)

Chạy `python3 check_production_ready.py` (chế độ đầy đủ có Docker trong WSL2):
```text
================================================================
  📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ✅ Graceful shutdown
     ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
  Result: 12/12 tiêu chí đạt · 43/43 checks passed
  🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
================================================================
```
- Kích thước Docker image: **238 MB** (`python:3.11-slim` multi-stage, user non-root `appuser`).
- Graceful shutdown (`docker stop`): **exit code 0, 0.8s**.

---

## AI Log
- Sử dụng AI assistant (Antigravity) để kiểm tra môi trường WSL2/Docker (CP0), chạy kiểm tra các bài thực hành Part 1–5 (CP1–CP4), hoàn thiện các `TODO` trong `06-lab-complete/` (CP5), và kiểm tra kết quả `check_production_ready.py` đạt `PASS 12/12` (43/43 checks).
