# AI Nursing Assistant · CarePlan

Chatbot RAG cho điều dưỡng: hỏi đáp tiếng Việt dựa trên sách *Quy trình điều dưỡng NANDA – NIC – NOC*, mỗi ý trả lời có nhãn nguồn [S1], [S2]… bấm vào để xem văn bản OCR và ảnh trang gốc. Kèm ô **nhật ký theo dõi diễn biến** người bệnh, được gửi làm bối cảnh khi hỏi. Nhà cung cấp mặc định là **NVIDIA NIM / nvidia/nemotron-3-ultra-550b-a55b**.

## Chạy trên Windows

Cần Python 3.11 trở lên.

**Cách khởi động khuyến nghị:** nhấp đúp `start.cmd`. Launcher chạy Python trực tiếp, tự cài thư viện còn thiếu, hỏi key bằng ô nhập ẩn, rồi tự mở trình duyệt khi server sẵn sàng. Giữ cửa sổ terminal mở trong lúc sử dụng. Nếu chỉ mở link mà chưa chạy launcher, trình duyệt sẽ báo `ERR_CONNECTION_REFUSED`.

Các lệnh PowerShell dưới đây là cách thay thế:

```powershell
cd C:\Users\Legion\Desktop\VinMec\AI_nursing_assistant
.\setup.ps1
.\start.ps1
```

Mở **http://127.0.0.1:8000**. `start.ps1` hỏi API key bằng ô nhập ẩn; key chỉ nằm trong môi trường của phiên chạy và không được ghi vào source. Nhấn Enter để bỏ qua key và dùng thư viện/chỉnh sửa thủ công. Có thể chạy `start.cmd` sau khi cài thư viện. Cổng khác: `.\start.ps1 -Port 8001`.

Nếu đã cấu hình `NVIDIA_API_KEY` trong môi trường hoặc `.env`, có thể chạy `python run.py`. `.env` bị loại khỏi Git; key được lưu riêng trong cấu hình local. Không gửi `.env` chứa key cho người khác.

## Cấu trúc theo ảnh tham chiếu

```text
AI_nursing_assistant/
├── agent/
│   ├── core/                  # agent.py, planner.py, memory.py, executor.py
│   ├── tools/                 # retrieval.py, web_search.py, calculator.py,
│   │                          # database_tool.py, file_handler.py
│   ├── prompts/templates/     # system_prompt.txt, task_prompt.txt
│   └── workflows/             # task_flow.py, multi_step_flow.py
├── llm/
│   ├── providers/             # nvidia.py, openai.py, anthropic.py,
│   │                          # local_model.py, factory.py
│   └── embeddings/            # embed.py, utils.py
├── memory/
│   ├── short_term/            # buffer.py
│   ├── long_term/             # store.py (mặc định tắt)
│   └── vector_store/          # vector_db.py, qdrant_store.py
├── api/
│   ├── routes/                # agent_routes.py
│   ├── controllers/           # agent_controller.py
│   ├── models.py
│   └── server.py
├── config/                    # settings.py, config.yaml
├── frontend/                  # index.html, styles.css, app.js
├── data/
│   ├── processed/             # corpus_full_v2.json; corpus.json là bản cũ
│   ├── index/                 # vector tài liệu nếu được tạo
│   └── runtime/               # không lưu ca bệnh mặc định
├── scripts/                   # build_index.py, smoke_live.py
├── tests/
├── requirements.txt
├── requirements-lock.txt
├── .env                       # cấu hình và key local, không chia sẻ
├── .env.example
├── setup.ps1
├── start.ps1
├── start.cmd
├── run.py
└── README.md
```

## Luồng xử lý

1. Điều dưỡng ghi **nhật ký theo dõi diễn biến** (thời điểm + nội dung) ở cột phải. Nhật ký chỉ lưu trong trình duyệt (localStorage), có nút xuất .txt và xóa hết.
2. Người dùng đặt câu hỏi, có thể lọc theo một quy trình.
3. Truy vấn tìm nguồn = câu hỏi + câu hỏi trước đó + ghi chép nhật ký mới nhất (đã lọc email/số điện thoại).
4. Retriever tìm các trang nguồn (BM25 + Qdrant, RRF). Không có nguồn thì trả lời "không tìm thấy", không gọi model.
5. Model nhận câu hỏi, 10 tin nhắn gần nhất, nhật ký (tối đa ~6.000 ký tự, ưu tiên ghi chép mới) và các nguồn đánh nhãn S1…Sn; trả lời văn bản thường kèm nhãn nguồn. Nhãn trỏ tới nguồn không tồn tại bị loại. Việc có nhãn **không chứng minh nội dung y khoa đúng**.

### Y lệnh nội trú

Cột phải có tab **Y lệnh nội trú**: ô gõ/dán y lệnh hiện hành của bác sĩ kèm ngày giờ, tự lưu trong trình duyệt (localStorage), có nút xóa. Khi bật "Gửi y lệnh kèm câu hỏi", y lệnh (đã lọc email/số điện thoại, tối đa 6.000 ký tự) được gửi cho model trong trường `orders`. Prompt yêu cầu model chỉ nhắc lại đúng y lệnh, không tự sửa liều; nếu y lệnh thiếu hoặc không khớp diễn biến thì ghi "cần trao đổi với bác sĩ". Y lệnh không được đưa vào truy vấn tìm nguồn. API: `orders`, `ordersTime` trong `POST /api/chat`.

### Chế độ bảng kế hoạch

Khi câu hỏi có ý lập kế hoạch ("lập/tạo/soạn … kế hoạch", "bảng kế hoạch …", "kế hoạch chăm sóc cho người bệnh …") hoặc bấm nút **Lập bảng kế hoạch**, chatbot dùng `agent/prompts/templates/plan_prompt.txt` và trả về bảng tối đa 6 đầu mục, xếp theo ưu tiên. Mỗi đầu mục gồm: chẩn đoán/vấn đề, mục tiêu, can thiệp, lượng giá, **lý do chọn** (dữ kiện trong nhật ký/câu hỏi dẫn tới đầu mục) và **nguồn** (S1, S2… nếu sách có nội dung tương ứng; không có thì ghi "Chưa có nguồn", hàng vẫn được giữ để điều dưỡng xác nhận). Kèm danh sách dữ kiện cần bổ sung, nút sao chép bảng (dán vào Word/Excel) và xuất CSV. API: `mode` = `auto` | `plan` | `answer`; phản hồi có `kind`, `plan`, `missingInfo`.

Bản giao diện/luồng "lập kế hoạch chăm sóc dạng bảng" cũ được sao lưu trong `_backup_truoc_RAG/`.

## Dữ liệu và giới hạn

- Nguồn là bản OCR sách *Quy trình điều dưỡng NANDA – NIC – NOC*, NXB Y học 2024.
- Corpus đầy đủ chứa **657 cửa sổ tìm kiếm**, bao phủ **373 trang**, **21 quy trình**, toàn bộ **354 bảng** và **565 chú thích** trong JSONL. Mỗi kết quả lấy đầy đủ bằng chứng của trang; loại trùng trang trước khi đưa vào AI. Bản 275 đoạn trước đây được giữ để đối chiếu/rollback.
- Không còn loại các bảng tiếp nối khỏi corpus. Giữ ô trống và HTML gốc; ngữ cảnh bảng trước được trích riêng, có nguồn và cờ kiểm tra, không tự khẳng định ô trống kế thừa chẩn đoán/mục tiêu. Nội dung chỉ có trong hình ảnh chưa được phiên âm thêm.
- Văn bản và mã OCR chưa được hiệu đính toàn bộ. Một số tiêu đề có lỗi chính tả giữ nguyên từ nguồn để không tự đoán sửa.
- Đã cấu hình **NVIDIA nemotron-3.5-embed-8b + Qdrant**, vector 4096 chiều/Cosine; kết hợp tìm kiếm vector với BM25 bằng RRF. Khi dịch vụ lỗi sẽ dùng keyword_fallback và ghi log.
- Không có công cụ đặt y lệnh, kê đơn hoặc tự thực hiện hành động lâm sàng.
- `web_search.py` là adapter tùy chọn, mặc định tắt và không được dùng làm nguồn lập kế hoạch. Các provider khác có adapter, nhưng luồng live được kiểm tra với NVIDIA.
- Thông tin ca đã ẩn danh và các đoạn nguồn được gửi tới API bạn cấu hình khi chat. Công cụ lọc email/điện thoại cơ bản **không thay thế ẩn danh thủ công**.
- Mặc định chỉ lắng nghe 127.0.0.1, không có đăng nhập nhiều người dùng. Không mở trực tiếp ra Internet; cần bổ sung xác thực, phân quyền và vận hành phù hợp trước khi dùng trong cơ sở y tế.
- Server không lưu câu hỏi hay nhật ký; lịch sử chat mất khi tải lại, nhật ký nằm trong localStorage của trình duyệt. Bộ nhớ dài hạn mặc định tắt, không có route tự lưu ca.

## API

- `GET /api/status`: trạng thái cấu hình, không trả key.
- `GET /api/knowledge?q=...&chapter=chapter_01`: tìm nguồn.
- `POST /api/chat`: nhận `message`, `messages` (tối đa 10 tin), `journal` (tối đa 50 ghi chép `{time, text}`), `chapter` (tùy chọn); trả `answer`, `sources`, `citedSourceIds`, `status`.
- `GET /api/page-image/{trang}`: ảnh trang gốc từ `../NANDA_NIC_NOC_pages`.
- Tài liệu tương tác: `/docs`.

## Kiểm thử

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Bộ kiểm thử dùng provider giả lập, kiểm tra retrieval, nguồn trích dẫn, dữ liệu thiếu, schema lỗi, phạm vi file, phép tính, chặn ghi nhớ và API. Live test riêng: `python -m scripts.smoke_live`; cần key trong môi trường, chỉ gửi ca giả lập và không in key.

## Bật vector sau khi có model embedding phù hợp

Đặt `EMBEDDING_MODEL`, `EMBEDDING_BASE_URL` trong môi trường / `.env`, rồi:

```powershell
.\.venv\Scripts\python.exe -m scripts.build_index
```

Đây là một thao tác gọi API có thể tốn hạn mức. Không chạy tự động lúc khởi động. Khi có index tương thích, retriever kết hợp từ khóa và cosine bằng RRF. Nếu API embedding lỗi, phản hồi ghi rõ `keyword_fallback`. Cần dựng lại index khi đổi model embedding hoặc corpus.

## Đổi nhà cung cấp

`LLM_PROVIDER` nhận `nvidia`, `openai`, `anthropic`, `compatible` hoặc `local`. Khi đổi, cấu hình **đồng thời** model, base URL và biến key tương ứng. `local` dùng endpoint tương thích OpenAI. Dữ liệu hiện dành cho thử nghiệm, chưa được xác nhận cho quyết định lâm sàng thực tế.


## Log và chẩn đoán phản hồi chậm

- Log JSON hiển thị ở terminal và lưu trong `logs/app.log`, xoay vòng khi đạt 5 MB, giữ 3 bản cũ. Mốc thời gian trong log là UTC.
- Mỗi lần gọi API có `request_id`; lỗi giao diện hiện mã này để tra cùng sự kiện trong log.
- Các sự kiện chính: `http.request_started`, `retrieval.completed`, `llm.request_started`, `llm.response_received`, `llm.timeout`, `chat.provider_error`.
- Log gồm model/provider, thời gian, số nguồn, trạng thái HTTP, loại lỗi và usage token nếu API trả về. Không ghi key, header xác thực, prompt, phản hồi AI hoặc nội dung ca bệnh.
- Timeout mặc định 90 giây cho toàn bộ lần gọi model. Khi hết thời gian, API trả HTTP 504 / `TIMEOUT`; trình duyệt đợi thêm 15 giây để nhận thông báo từ server. Có thể chỉnh `LLM_TIMEOUT_SECONDS` trong `.env` rồi khởi động lại.
- Log cho các yêu cầu trước khi thêm chức năng này không tồn tại; cần tái hiện lỗi để biết nguyên nhân.


### Qdrant + NVIDIA embeddings

Set EMBEDDING_MODEL=nvidia/nemotron-3.5-embed-8b, EMBEDDING_API_KEY, QDRANT_URL, QDRANT_API_KEY and QDRANT_COLLECTION in .env. Chat uses its existing separate NVIDIA_API_KEY. Run `.venv\Scripts\python.exe scripts\build_index.py` to index reference documents (4096 dimensions, Cosine). No collection is deleted or recreated. Re-running upserts deterministic IDs and reuses a content/model-hashed embedding cache. Use a new collection when changing model or corpus version to avoid stale records. Endpoint currently requires one text per request; the builder runs four individual requests concurrently over a reused HTTP client. Source records retain page and chapter metadata. Query embeddings are not stored. Retrieval fuses BM25 and Qdrant rankings with RRF, respects chapter selection and logs keyword fallback on errors. Restart start.cmd after configuration changes.


### Full OCR corpus v2

`corpus_full_v2.json` is built reproducibly by `scripts/build_full_corpus.py` from the sibling NANDA_NIC_NOC_RAG directory (373 pages, 1995 blocks). It keeps all 1237 non-header/footer blocks, all 354 tables and 565 footnotes; 758 page headers/footers are excluded from embeddings but remain in original page metadata. There are 657 bounded plain-text search windows (up to 1400 characters) covering all 373 pages; each retrieved window returns full page evidence and table HTML with columns and spans. Retrieval deduplicates pages. Suspected continuation pages quote prior table context separately, without guessing empty cells or asserting clinical joins. Original OCR text/HTML, image filenames and block IDs are retained. Images without OCR are flagged and are not transcribed by text embeddings. This is broader coverage, not a claim of clinically corrected OCR.

Build staging collection: `.venv\Scripts\python.exe scripts\build_index.py --corpus data/processed/corpus_full_v2.json --collection nursing_nemotron35_8b_full_v3`. Verify with the same arguments to `scripts/verify_qdrant.py`. Switch config/config.yaml corpus_path and .env QDRANT_COLLECTION only after verification; the previous corpus/collection remain available for rollback.
