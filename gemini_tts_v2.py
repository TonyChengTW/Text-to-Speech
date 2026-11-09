#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Google Cloud Text-to-Speech — Gemini 3.1 Flash TTS 產生語音
模型: gemini-3.1-flash-tts-preview / 聲音: Laomedeia / 語系: cmn-tw
只用標準函式庫 (urllib)，不需 pip 安裝任何套件。

認證二選一：
  (A) OAuth（建議，preview 模型較穩）:
        gcloud auth application-default login   # 只需做一次
        export GCP_PROJECT_ID="你的GCP專案ID"
  (B) API key:
        export GOOGLE_TTS_API_KEY="你的API金鑰"

執行:
  python3 gen_tts.py
產出:
  output.wav
"""

import os
import sys
import json
import base64
import wave
import subprocess
import urllib.request
import urllib.error

# ---------- 可調參數 ----------
OUTPUT_FILE = "output.wav"
ENDPOINT = "https://texttospeech.googleapis.com/v1beta1/text:synthesize"

STYLE_PROMPT = "自然順暢，低沉，親切，不強調陰陽頓挫"

TEXT = """新鮮的魚貨
客家的菜包
水果的香甜
這是台北市民的日常

廟埕的炷香
教堂的彩窗
把光放進每個安靜的角落

登上後花園的象山
俯瞰台北101
伴隨著周遭的老房
對「都更」充滿希望

捷運附近的運動驛站
接住一天的疲勞
讓上班族方便盥洗
把時間還給自己

文化徑，把散落各地的建築、歷史、美食與生活串起來。
從一個點，延伸成一條線，再交織成一面網。
人流縫合，讓不同的年代，在同一條路上相遇。
那些曾經被遺忘的腳步，有人替它們記得。
也讓人走進彼此的故事。

孤單不必一個人扛。
陪伴孤獨，接住每一份孤單。
老有所終，壯有所用，幼有所長，
觀寡孤獨廢疾者，皆有所養。

用心，城市就會順；順了，人就會留。
把票投給想要的生活方式，就贏了。

城市，順起來
台北，順起來

3號，台北的靠山
"""

PAYLOAD = {
    "audioConfig": {
        "audioEncoding": "LINEAR16",
        "pitch": 0,
        "speakingRate": 1,
    },
    "input": {
        "prompt": STYLE_PROMPT,
        "text": TEXT,
    },
    "voice": {
        "languageCode": "cmn-tw",
        "modelName": "gemini-3.1-flash-tts-preview",
        "name": "Laomedeia",
    },
}

# 計價（gemini-3.1-flash-tts-preview，2026 推廣期；以官方頁為準）
PRICE_IN_PER_M = 1.00     # USD / 百萬 input text token
PRICE_OUT_PER_M = 20.00   # USD / 百萬 audio output token
AUDIO_TOKENS_PER_SEC = 25 # 經驗值：音訊輸出約 25 token/秒
USD_TWD = 32.0            # 匯率，粗估台幣用


def build_request():
    api_key = os.environ.get("GOOGLE_TTS_API_KEY")
    headers = {"Content-Type": "application/json; charset=utf-8"}
    url = ENDPOINT

    if api_key:
        url = f"{ENDPOINT}?key={api_key}"
        print("認證方式: API key")
    else:
        try:
            token = subprocess.check_output(
                ["gcloud", "auth", "application-default", "print-access-token"],
                text=True,
            ).strip()
        except Exception as e:
            sys.exit(
                "取得 OAuth token 失敗。請先 `gcloud auth application-default login`，"
                f"或改設 GOOGLE_TTS_API_KEY。原始錯誤: {e}"
            )
        project = os.environ.get("GCP_PROJECT_ID")
        if not project:
            sys.exit("使用 OAuth 時需設定環境變數 GCP_PROJECT_ID（你的 GCP 專案 ID）。")
        headers["Authorization"] = f"Bearer {token}"
        headers["x-goog-user-project"] = project
        print(f"認證方式: OAuth（專案 {project}）")

    data = json.dumps(PAYLOAD).encode("utf-8")
    return urllib.request.Request(url, data=data, headers=headers, method="POST")


def main():
    req = build_request()
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"API 錯誤 HTTP {e.code}:")
        print(e.read().decode("utf-8", "replace"))
        sys.exit(1)

    audio_b64 = body.get("audioContent")
    if not audio_b64:
        sys.exit(f"回應沒有 audioContent，原始回應:\n{json.dumps(body, ensure_ascii=False, indent=2)}")

    audio_bytes = base64.b64decode(audio_b64)
    with open(OUTPUT_FILE, "wb") as f:
        f.write(audio_bytes)
    print(f"✅ 已輸出: {OUTPUT_FILE}（{len(audio_bytes):,} bytes）")

    # 從 WAV 讀真實時長，回推費用
    try:
        with wave.open(OUTPUT_FILE, "rb") as w:
            frames, rate = w.getnframes(), w.getframerate()
            dur = frames / rate if rate else 0
    except Exception:
        dur = 0

    chars = len(TEXT)
    in_tokens = len(STYLE_PROMPT) + chars          # 粗估：CJK 約 1 token/字（偏高估）
    out_tokens = dur * AUDIO_TOKENS_PER_SEC
    cost_in = in_tokens / 1_000_000 * PRICE_IN_PER_M
    cost_out = out_tokens / 1_000_000 * PRICE_OUT_PER_M
    total = cost_in + cost_out

    print("\n----- 費用估算 -----")
    print(f"音訊長度       : {dur:.1f} 秒")
    print(f"輸入 token(估) : {in_tokens:,}  → ${cost_in:.5f}")
    print(f"輸出 token(估) : {out_tokens:,.0f}  → ${cost_out:.5f}")
    print(f"本次總計(估)   : ${total:.4f} USD  ≈ NT${total*USD_TWD:.2f}")
    print("（batch 模式約為一半；推廣價 2027/1/1 後可能調漲）")


if __name__ == "__main__":
    main()
