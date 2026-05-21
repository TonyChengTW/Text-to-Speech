# TTS CLI 工具

支援 **MiMo TTS** 與 **Gemini TTS** 兩種 API 的命令列工具，讀取帶有段落語氣控制的 `.txt` 檔案生成 MP3 音訊。

## 安裝

```bash
# 啟動虛擬環境（必要）
source venv/bin/activate
```

## API 金鑰設定

支援三種 API 金鑰設定方式，優先順序如下：

| 優先順序 | 參數 | 環境變數 | 說明 |
|---------|------|---------|------|
| 1 | `--api-key` | - | 直接指定 |
| 2 | `--gemini-api-key` | `GEMINI_API_KEY` | Gemini API |
| 3 | 參數 | `TTS_API_KEY` | MiMo API（金鑰可共用） |
| 4 | `.env` 檔案 | `TTS_API_KEY` / `GEMINI_API_KEY` | 環境變數檔案 |

`.env` 檔案格式：
```bash
TTS_API_KEY=your_mimo_key
GEMINI_API_KEY=your_gemini_key
```

## 使用方式

### 基本用法（使用 MiMo API，預設）

```bash
python tts.py input.txt -v
```

### Gemini API

```bash
# 使用 gemini-2.5-flash-preview-tts（預設）
python tts.py input.txt --gemini-api-key YOUR_KEY -v

# 指定其他 Gemini 模型
python tts.py input.txt --model gemini-3.1-flash-tts-preview -v

# 兩者皆指定時優先使用 --gemini-api-key
python tts.py input.txt --gemini-api-key YOUR_KEY -v
```

### 其他選項

```bash
# 指定輸出檔案
python tts.py input.txt -o output.mp3

# 查看版本
python tts.py --version

# 查看所有選項
python tts.py --help

## 聲音克隆（Voice Clone）

使用自己的音訊檔案克隆音色，僅支援 **MiMo API**。

### 管理克隆音色

```bash
# 新增克隆音色（需要音訊檔案）
python tts.py --clone-profile add my_voice --audio path/to/your_audio.mp3

# 列出所有克隆音色
python tts.py --clone-profile list

# 刪除克隆音色
python tts.py --clone-profile delete my_voice
```

**支援格式**：`.mp3`、`.wav`、`.m4a`

### 使用克隆音色

在文字檔案中使用 `[clone:音色名稱]` 標記：

```
[clone:my_voice]
這段文字會用你克隆的聲音來朗讀。
```

### 注意事項

- 克隆音色僅支援 **MiMo API**，不支援 Gemini
- Gemini 使用 `[clone:X]` 會回傳錯誤
- 克隆音色適合少量文字，長文字建議用內建音色

## 支援模型

### MiMo 模型

| 模型 | 說明 |
|------|------|
| `mimo-v2.5-tts` | MiMo 預設模型 |
| `mimo-v2.5-tts-voiceclone` | 克隆音色模型（內部使用） |

### Gemini 模型

| 模型 | 說明 |
|------|------|
| `gemini-2.5-flash-preview-tts` | Gemini 2.5 TTS（預設） |
| `gemini-3.1-flash-tts-preview` | Gemini 3.1 TTS |

## 文字檔案格式

### 音色指定

```
[voice:音色名稱]
```

#### MiMo API 音色

| 音色 ID | 說明 |
|--------|------|
| `冰糖` | 女聲，年輕活潑 |
| `茉莉` | 女聲，成熟知性 |
| `蘇打` | 女聲，自然清新 |
| `白樺` | 男聲，溫柔沉穩 |
| `Mia` | 女聲，甜美可愛 |
| `Chloe` | 女聲，温柔大方 |
| `Milo` | 男聲，陽光活力 |
| `Dean` | 男聲，深沉磁性 |

#### Gemini API 音色

| 音色 ID | 說明 |
|--------|------|
| `Aoede` | 對應 `aoede` |
| `Kore` | 對應 `kore` |
| `Puck` | 對應 `puck` |
| `Charon` | 對應 `charon` |
| `Leda` | 對應 `leda` |
| `Sulafat` | 對應 `sulafat` |
| `Fenrir` | 對應 `fenrir` |
| `Enceladus` | 對應 `enceladus` |

**注意**：工具會自動將 Gemini 音色 ID 轉換為 API 接受的格式（`aoede`、`kore` 等小寫名稱）。

### 語氣標記

```
(開心)你好！[大笑]
```

可用語氣：`開心`、`平靜`、`失落`、`大笑`、`緊張`、`興奮`、`感傷`

### 其他標記

- `#` 開頭的行是註解
- `[style:自訂風格]` 覆蓋該段落風格
- `[clone:音色名稱]` 使用克隆音色（僅 MiMo）
- 段落間的空白行會自動合併

### 範例

```
[voice:冰糖]
(開心)歡迎來到主場！

[voice:Kore]
(平靜)這是一段Gemini API的測試文字。

# 使用克隆音色（僅 MiMo）
[clone:my_voice]
這段使用我克隆的聲音。

[voice:Aoede]
(興奮)完成！
```

## 預設風格

- **MiMo**：`語調自然，台灣腔，不要用中國大陸捲舌腔調`
- **Gemini**：`語調自然，不要用中國大陸捲舌腔調`

## 測試

```bash
# 執行所有測試
pytest tests/ -v

# 執行單一測試檔案
pytest tests/test_parser.py -v

# 執行單一測試
pytest tests/test_parser.py::test_parse_simple_segment -v
```

## 版本管理

版本號遵循語意化版本：`MAJOR.MINOR.PATCH`

```bash
# 查看當前版本
cat VERSION

# 建立版本標籤
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
```

## 系統依賴

- Python 3.10+
- ffmpeg（pydub 轉換 MP3 所需）：`brew install ffmpeg`