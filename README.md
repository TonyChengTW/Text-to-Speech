# MiMo TTS CLI 工具

單一 Python 檔案（`tts.py`）的命令列工具，讀取帶有段落語氣控制的 `.txt` 檔案，透過 MiMo-V2.5-TTS API 生成 MP3 音訊。

## 安裝

```bash
# 啟動虛擬環境（必要）
source venv/bin/activate
```

## 使用方式

```bash
# 執行（需要 API 金鑰）
python tts.py input.txt --api-key YOUR_KEY -v

# 或使用 .env 檔案（TTS_API_KEY=xxx）
python tts.py input.txt -v

# 查看版本
python tts.py --version
```

## 文字檔案格式

```
[voice:冰糖]           # 音色 ID（冰糖/茉莉/蘇打/白樺/Mia/Chloe/Milo/Dean）
(開心)你好！[大笑]      # 內聯標籤 → 嵌入 assistant message
```

- 預設風格：`用台灣腔，語速適中，咬字清晰`
- `#` 開頭的行是註解
- `[style:]` 可用於覆蓋全域預設風格
- `[voice:]` 會重設段落音色

## 測試

```bash
pytest tests/ -v
```

## 系統依賴

- Python 3.10+
- ffmpeg：`brew install ffmpeg`