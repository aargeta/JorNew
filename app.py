import os
from dotenv import load_dotenv
from flask import Flask, Response
import requests
from io import BytesIO

# 1) Load .env
load_dotenv()

# 2) Env vars for Grok
GROK_API_URL = os.getenv("GROK_API_URL")
GROK_API_KEY = os.getenv("XAI_API_KEY")
PERSONALITY_PROMPT = os.getenv("SLEAZY_PERSONALITY", "Default fallback prompt")

# 3) Env vars for ElevenLabs
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID")

app = Flask(__name__)

def call_grok(prompt: str) -> str:
    """
    Calls Grok (x.ai) with model 'grok-2-1212' (or whichever).
    Returns text or "Error:..." if something fails.
    """
    if not GROK_API_URL or not GROK_API_KEY:
        return "Error: Missing GROK_API_URL or XAI_API_KEY"

    headers = {"Authorization": f"Bearer {GROK_API_KEY}"}
    data = {
        "model": "grok-2-1212",
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }
    resp = requests.post(GROK_API_URL, json=data, headers=headers)
    print("[Grok] status:", resp.status_code)

    if resp.status_code == 200:
        try:
            return resp.json()['choices'][0]['message']['content']
        except (KeyError, IndexError):
            return "Error: Unexpected Grok response format."
    else:
        return f"Error: Grok returned {resp.status_code} - {resp.text}"

def call_elevenlabs_tts(text: str) -> BytesIO:
    """
    Sends text to ElevenLabs TTS, returns MP3 data or an error message as bytes.
    """
    if not ELEVENLABS_API_KEY or not ELEVENLABS_VOICE_ID:
        return BytesIO(b"Error: ELEVENLABS_API_KEY or ELEVENLABS_VOICE_ID missing")

    tts_url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json"
    }
    data = {
        "text": text,
        "voice_settings": {
            "stability": 0.6,
            "similarity_boost": 0.9,
            "style_exaggeration": 0.0
        }
    }

    resp = requests.post(tts_url, json=data, headers=headers, stream=True)
    print("[ElevenLabs] status:", resp.status_code)

    if resp.status_code == 200:
        # Return the raw MP3 bytes
        return BytesIO(resp.content)
    else:
        err_msg = f"Error from ElevenLabs: {resp.status_code}, {resp.text}"
        return BytesIO(err_msg.encode("utf-8"))

@app.route("/")
def serve_index():
    """
    An embedded HTML page: user clicks the button -> fetch('/generate-tts') -> plays TTS
    -> Then auto-opens Twitter in a new tab with a pre-filled tweet.
    """
    html_content = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8" />
  <title>Grok + ElevenLabs TTS Demo</title>
</head>
<body>
  <h1>Click Button to Generate TTS & Tweet</h1>

  <button id="ttsButton">Copy</button>

  <script>
    document.getElementById('ttsButton').addEventListener('click', async () => {
      try {
        // 1) Call our Flask route on same origin
        const response = await fetch('/generate-tts');
        if (!response.ok) {
          console.error("Error fetching TTS:", response.status, response.statusText);
          alert("Error fetching TTS. Check console or Flask logs.");
          return;
        }

        // 2) Convert to Blob -> create Audio
        const audioBlob = await response.blob();
        const audioUrl = URL.createObjectURL(audioBlob);
        const audio = new Audio(audioUrl);

        // 3) As soon as audio starts, open Twitter with pre-filled tweet
        audio.onplay = () => {
          // The tweet text with your requested lines
          const tweetText = `$JOR\\n\\njor.png`;
          const twitterUrl = 'https://twitter.com/intent/tweet?text=' + encodeURIComponent(tweetText);
          window.open(twitterUrl, '_blank');
        };

        // 4) Play audio
        audio.play();
      } catch (err) {
        console.error("Error calling generate-tts:", err);
        alert("Error calling generate-tts. See console.");
      }
    });
  </script>
</body>
</html>
"""
    return html_content

@app.route("/generate-tts", methods=["GET"])
def generate_tts():
    # 1) Grok
    grok_text = call_grok(PERSONALITY_PROMPT)
    if grok_text.startswith("Error:"):
        return grok_text, 500

    # 2) ElevenLabs TTS
    mp3_data = call_elevenlabs_tts(grok_text)
    first_20 = mp3_data.getvalue()[:20].decode("utf-8", errors="ignore")
    if first_20.startswith("Error from ElevenLabs"):
        return mp3_data.getvalue().decode("utf-8"), 500

    # 3) Return MP3
    return Response(mp3_data, mimetype="audio/mpeg")

if __name__ == "__main__":
    print("[DEBUG] GROK_API_URL:", GROK_API_URL)
    print("[DEBUG] GROK_API_KEY:", GROK_API_KEY)
    print("[DEBUG] ELEVENLABS_API_KEY:", ELEVENLABS_API_KEY)
    print("[DEBUG] ELEVENLABS_VOICE_ID:", ELEVENLABS_VOICE_ID)
    print("[DEBUG] PERSONALITY_PROMPT:", PERSONALITY_PROMPT[:50], "...")
    app.run(debug=True, host="0.0.0.0", port=5000)
