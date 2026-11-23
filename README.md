# DocAgent 本地文档智能体

LangChain 工具调用 + BM25/FAISS + BGE-M3 + BGE Reranker + FastAPI + SQLite。

## 启动

在 PowerShell 中进入本目录，运行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe scripts/download_models.py
# 用编辑器填写 .env 中 LLM_API_KEY，勿将密钥发到聊天或提交到 Git
.\.venv\Scripts\python.exe -m uvicorn docagent.api:app --host 127.0.0.1 --port 8011
```

浏览器打开 http://127.0.0.1:8011；接口文档 /docs。默认 DeepSeek `https://api.deepseek.com`，模型 `deepseek-flash`；以服务商当前可用模型为准。

## 实现与边界

- `search_docs` 查证据、`read_section` 读章节、`calculate` 安全计算。每轮最多6次模型决策，每步最多3个工具调用。不是六次工具调用。
- SQLite 隔离 session_id，原始消息持续保存；预算按字符近似而非精确 token，旧轮次摘要不能授权引用。
- 默认运行配置使用 hybrid + rerank；完整模型下载后运行。将 RETRIEVAL_MODE=bm25、RERANK=false 可快速验证无模型权重的检索路径。BM25 可完全离线运行。dense/hybrid 使用真实 BGE-M3 和 FAISS；rerank 使用真实 CrossEncoder。模型缺失会明确失败，不把词面检索冒充向量结果。
- 本轮工具结果构成唯一引用集合；程序检查引用存在性，不能据此证明每句回答均被证据支持。语义引用正确率需要人工核对。
- SSE 工具事件即时发送，最终回答经引用检查后分段输出，不宣称逐 token 原始生成。
- 本机单用户学习服务，无账号鉴权。session_id 是隔离键而非身份凭证，勿直接暴露公网。

## 数据与评测

corpus 为固定提交的 FastAPI 官方中文文档，MIT 许可与来源见 corpus/LICENSE.fastapi、provenance.json。文档中的未展开模板引用保留原样，不当作事实标签。

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts/evaluate.py --help
```

评测题目是开发时构造的标签，不能声称第三方盲测或人工审核。开发集与测试集分开；答案正确率与证据支持率的人工审核字段需完成后再写简历。离线 stub 测试不等于真实 DeepSeek 调用验证。

## 接口

POST /chat：JSON `{ "message": "FastAPI 默认端口是多少？", "session_id": "study1" }`。
返回 answer、sources、trace、steps、elapsed_ms、guard。服务失败 HTTP503。

POST /chat/stream：同一请求，SSE 事件 status/tool/sources/token/error/done；无论服务成功或捕获异常都会发送 done。请求参数错误返回 HTTP422。

GET /health：索引数量、模型是否配置、检索策略；不返回密钥。

阅读 LEARNING.md 开始代码学习。首次运行本地模型会加载较大权重，延迟不应混入热启动指标。历史虚构成绩不属于本项目结果。

下载模型：运行 .venv/Scripts/python scripts/download_models.py，会自动读取 .env 的 HF_HOME。官方源连接失败时可设置 $env:HF_ENDPOINT='https://hf-mirror.com'。两份权重约4.5GB，版本与实际 SHA256 见 MODEL_MANIFEST.json；加载器固定快照，不依赖 main 缓存别名。下载未完成时可使用 RETRIEVAL_MODE=bm25、RERANK=false。

人工答案复核：逐题查看 live 报告中的问题、答案与本轮工具证据，在独立 JSONL 写入真实人工评分，例如 `{"id":"Q01","correctness":2,"citation_support":1,"notes":"结论正确，引用仅部分支持"}`。两项均为 0–2 分。运行 `.venv/Scripts/python scripts/score_reviews.py reports/live.json reviews.jsonl --output reports/live-reviewed.json`。输出必须另存；全对率和引用支持均值只计算此次实际复核的题目，未复核项不参与分母。程序不会把自动生成的题目标签视为人工审核。

真实本地模型结果与边界见 EVALUATION.md；云端答案、工具决策效果和 Agent 端到端延迟仍需要有效 API Key 与人工复核。

50题真实模型HTTP结果：见 LIVE_EVALUATION.md 和 reports/live-http.json。正常返回50/50，平均决策2.1轮，CPU热启动端到端P95约23.78秒；不可将正常返回率当作答案准确率。

## Windows CMD 启动与文档管理

在项目目录执行 start.cmd，再打开 http://127.0.0.1:8011。PowerShell 可执行 .\start.ps1。
已有环境可运行 .venv\Scripts\python.exe -m pip install -r requirements.txt 更新解析依赖。

首页可导入 Markdown、UTF-8 TXT、DOCX 和文本型 PDF，查看解析预览与当前文件清单。
DOCX 提取普通段落、标题和表格。PDF 提取文字层并保留页码标题。
图片 PNG、JPEG、WebP 使用本机 Tesseract OCR，需要把 tesseract 加入 PATH 并安装 chi_sim 和 eng 语言包。可通过 OCR_LANG 修改语言。纯扫描 PDF 请先转图片。本地解析后的文本保存在 corpus/uploads/，已被 Git 忽略。
删除上传文档会使后续请求重新加载索引。已开始的请求使用各自的索引快照。
Agent 的 list_documents 查看库内文件，search_docs 和 read_section 使用解析后的文字。首页可以恢复既有会话并查看新产生的工具轨迹。此版本仍为本机单用户服务，调用云模型时，检索到的证据会发送给配置的模型服务。
