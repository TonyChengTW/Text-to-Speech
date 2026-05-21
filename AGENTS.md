# MiMo TTS CLI 工具

單一 Python 檔案（`tts.py`）的命令列工具，讀取帶有段落語氣控制的 `.txt` 檔案，透過 MiMo-V2.5-TTS API 生成 MP3 音訊。

## 快速開始

```bash
# 啟動虛擬環境（必要）
source venv/bin/activate

# 執行
python tts.py input.txt --api-key YOUR_KEY -v
# 或使用 .env 檔案（TTS_API_KEY=xxx）
python tts.py input.txt -v

# 查看版本
python tts.py --version
```

## 指令

```bash
# 執行所有測試
pytest tests/ -v

# 執行單一測試檔案
pytest tests/test_parser.py -v

# 執行單一測試
pytest tests/test_parser.py::test_parse_simple_segment -v
```

## 版本管理

版本號遵循 [語意化版本](https://semver.org/lang/zh-TW/)：`MAJOR.MINOR.PATCH`

- **MAJOR** — 不相容的 API 變更
- **MINOR** — 向後相容的新功能
- **PATCH** — 向後相容的問題修正

```bash
# 查看當前版本
cat VERSION

# 更新版本號（修改兩處）
# 1. VERSION 檔案
# 2. tts.py 中的 __version__ 變數

# 建立版本標籤
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
```

## 架構

- `tts.py` — 所有邏輯集中在單一檔案（解析器、API 客戶端、音訊處理、CLI）
- `VERSION` — 當前版本號
- `sample.txt` — 完整的語氣標籤範例
- `.env` — API 金鑰儲存（不會提交）
- `tests/` — 33 個測試，涵蓋解析器、API、音訊、分段、協調流程

## API 配置

**基礎 URL：** `https://token-plan-cn.xiaomimimo.com/v1`  
**認證：** `Authorization: Bearer <key>` 標頭  
**端點：** `POST /v1/chat/completions`

API 金鑰優先順序：`--api-key` 參數 > `TTS_API_KEY` 環境變數 > `.env` 檔案

## 文字檔案格式

```
[voice:冰糖]           # 音色 ID（冰糖/茉莉/蘇打/白樺/Mia/Chloe/Milo/Dean）
(開心)你好！[大笑]      # 內聯標籤 → 嵌入 assistant message
```

- 預設風格：工具已配置全域偏好為 `用台灣腔，語速適中，咬字清晰`
- `#` 開頭的行是註解
- `[style:]` 可用於覆蓋全域預設風格或設定該段落專屬風格
- `[voice:]` 會重設段落風格，但不會移除全域預設（除非明確指定 style）
- 沒有標頭的文字會使用全域預設值

## 關鍵檔案

- `tts.py:75-140` — MiMoClient 重試邏輯
- `tts.py:28-72` — parse_text_file 解析器
- `tts.py:173-205` — chunk_text 句子邊界偵測
- `tests/conftest.py` — 將專案根目錄加入 Python 路徑

## 系統依賴

- Python 3.10+
- ffmpeg（pydub 轉換 MP3 所需）：`brew install ffmpeg`