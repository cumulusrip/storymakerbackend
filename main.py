from fastapi import FastAPI, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import requests, os, random, uuid, subprocess
from gtts import gTTS

# Initialize
app = FastAPI()

# Allow CORS (frontend Next.js will call this API)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Setup static folders ---
os.makedirs("static/audio", exist_ok=True)
os.makedirs("static/images", exist_ok=True)
os.makedirs("static/videos", exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")

# Predefined assets (match your actual files)
ASSETS = {
    "images": [
        "/static/images/1.jpeg",
        "/static/images/2.jpeg",
        "/static/images/3.jpeg"
    ],
    "videos": [
        "/static/videos/1.mp4",
        "/static/videos/2mp4.mp4",
        "/static/videos/3.mp4"
    ]
}


GEMINI_KEY = "" 

def generate_script(prompt: str) -> str:
    if not GEMINI_KEY:
        return f"Mock script for: {prompt}"

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    headers = {
        "Content-Type": "application/json",
        "X-goog-api-key": GEMINI_KEY
    }
    data = {
        "contents": [{"parts": [{"text": prompt}]}]
    }

    resp = requests.post(url, headers=headers, json=data)
    if resp.status_code == 200:
        try:
    
            candidate = resp.json()["candidates"][0]
            return candidate["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError):
            return f"Error parsing Gemini response: {resp.text}"
    return f"Error: {resp.text}"




def generate_audio(text: str) -> str:
    filename = f"audio_{uuid.uuid4().hex}.mp3"
    path = f"static/audio/{filename}"
    tts = gTTS(text)
    tts.save(path)
    return f"/static/audio/{filename}"


@app.post("/generate")
async def generate(prompt: str = Form(...)):
    script = generate_script(prompt)
    audio_url = generate_audio(script)
    images = random.sample(ASSETS["images"], 3)
    videos = random.sample(ASSETS["videos"], 3)
    return JSONResponse({
        "script": script,
        "audio_url": audio_url,
        "assets": {"images": images, "videos": videos}
    })


def get_duration(path: str) -> float:
    """Return duration in seconds using ffprobe"""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    return float(result.stdout)

@app.post("/final-video")
async def create_final_video(payload: dict):
    audio_url = payload.get("audio")
    image_url = payload.get("image")
    video_url = payload.get("video")
    script_text = payload.get("script", "")  

    audio_path = audio_url.replace("/static/", "static/")
    image_path = image_url.replace("/static/", "static/")
    video_path = video_url.replace("/static/", "static/") if video_url else None

    final_filename = f"final_{uuid.uuid4().hex}.mp4"
    final_path = f"static/{final_filename}"


    import textwrap
    wrapped_text = "\\n".join(textwrap.wrap(script_text, width=40))
    font_path = "static/fonts/Roboto-Bold.ttf"

    if video_path:
        cmd = [
            "ffmpeg",
            "-y",
            "-i", video_path,
            "-i", audio_path,
            "-vf", f"drawtext=fontfile={font_path}:text=\"{wrapped_text}\":fontcolor=white:fontsize=48:box=1:boxcolor=black@0.5:x=(w-text_w)/2:y=h-(text_h*2)\"",
            "-c:a", "aac",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-shortest",
            final_path
        ]
    else:
        cmd = [
            "ffmpeg",
            "-y",
            "-loop", "1",
            "-i", image_path,
            "-i", audio_path,
            "-vf", f"drawtext=fontfile={font_path}:text=\"{wrapped_text}\":fontcolor=white:fontsize=48:box=1:boxcolor=black@0.5:x=(w-text_w)/2:y=h-(text_h*2),scale=trunc(iw/2)*2:trunc(ih/2)*2\"",
            "-c:a", "aac",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-shortest",
            final_path
        ]




    subprocess.run(cmd, check=True)

    return JSONResponse({"final_video_url": f"/static/{final_filename}"})
