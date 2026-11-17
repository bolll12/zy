# 知研 · Agent 文献研究系统

在本机上传文档、全文检索、核对原文并整理研究笔记。可直接使用本地证据摘录，也可调用兼容 Chat Completions 的模型 API 归纳检索结果。

## 运行

需要 Python 3.9+ 和 Node.js 22.12+（或 Vite 8 支持的较新版本）。下面以 macOS/Linux 为例：

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
npm ci --prefix frontend
npm run build --prefix frontend
python server.py
```

打开 `http://127.0.0.1:8878`。也可以运行 `python server.py --port 8879 --open` 指定另一端口。服务只监听本机，设计为单用户工作空间。构建后可用 `python launcher.py` 打开它。

## 使用

1. 从 **知识管理** 上传资料。仓库内 `examples/` 有两份原创说明，可用于试跑。
2. 在 **文献库** 搜索关键词和资料编号；在 **研究助手** 输入问题或限定某份资料。证据链接可以定位到原文。
3. 在 **模型设置** 配置远程 HTTPS API 或 Ollama 等本机兼容接口。模式、地址和模型名可被浏览器记住；密钥只保存在当前页面会话。
4. 在 **综述工作台** 整理笔记并导出 Word 或 Markdown。可在 **过程记录** 导出研究历史。

支持拥有文字层的 PDF、DOCX、TXT、Markdown，单文件最多 10 MiB。PDF 按页定位，其余格式按段定位；扫描件需先 OCR。导入使用 SQLite 保存原文件、定位文本和片段，并通过 BM25 做全文检索。上传时仅在本机解析；模型模式会把问题与命中的证据送给所配置的服务，请按资料允许的用途选择模式。

## 数据与开发

- `user_data/` 是个人知识库、笔记、收藏、历史和草稿；请保留本机备份。该目录与生成的网页、依赖、原有课程文档均不纳入版本控制。
- `frontend/` 为网页源码；`server.py` 提供本机 API，`engine.py` 实现检索与证据归纳，`knowledge.py` 处理上传解析和保存。
- 已安装依赖后，运行 `python -m unittest discover -s tests -v`，测试使用临时存储和本机模拟模型服务。
