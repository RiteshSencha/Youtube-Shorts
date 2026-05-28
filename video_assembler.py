import os
import random
import requests
import subprocess
from datetime import datetime
from logger import setup_logger

logger = setup_logger()

PEXELS_API = "https://api.pexels.com/videos/search"


def download_pexels_video(query, api_key, output_path="output/background.mp4"):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    headers = {"Authorization": api_key}
    params = {"query": query, "per_page": 10, "orientation": "portrait", "size": "medium"}

    try:
        resp = requests.get(PEXELS_API, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        videos = resp.json().get("videos", [])

        if not videos:
            logger.warning(f"No Pexels results for '{query}', trying 'motivation'")
            params["query"] = "motivation success"
            resp = requests.get(PEXELS_API, headers=headers, params=params, timeout=15)
            videos = resp.json().get("videos", [])

        if not videos:
            return _create_gradient_background(output_path)

        video = random.choice(videos[:5])
        # Pick highest quality portrait file
        files = [f for f in video["video_files"] if f.get("quality") in ("hd", "sd")]
        files.sort(key=lambda x: x.get("height", 0), reverse=True)
        download_url = files[0]["link"] if files else video["video_files"][0]["link"]

        logger.info(f"Downloading Pexels video: {download_url[:60]}...")
        video_resp = requests.get(download_url, stream=True, timeout=60)
        with open(output_path, "wb") as f:
            for chunk in video_resp.iter_content(chunk_size=8192):
                f.write(chunk)

        logger.info(f"Background video saved: {output_path}")
        return output_path

    except Exception as e:
        logger.error(f"Pexels download failed: {e}")
        return _create_gradient_background(output_path)


def _create_gradient_background(output_path):
    """Fallback: solid dark background with FFmpeg."""
    logger.info("Creating fallback gradient background")
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", "color=c=0x1a1a2e:size=1080x1920:rate=30",
        "-t", "60", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        output_path
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


def get_audio_duration(audio_path):
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_streams", audio_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    import json
    data = json.loads(result.stdout)
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "audio":
            return float(stream.get("duration", 55))
    return 55.0


def assemble_video(bg_video_path, audio_path, captions_path, output_path="output/final.mp4"):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    duration = get_audio_duration(audio_path)
    logger.info(f"Assembling video | duration: {duration:.1f}s")

    # Caption style: bold white text, black outline, centered bottom third
    caption_style = (
        "FontName=Arial,Bold=1,FontSize=22,"
        "PrimaryColour=&Hffffff,OutlineColour=&H000000,"
        "Outline=2,Shadow=1,Alignment=2,MarginV=300"
    )

    cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "-1", "-i", bg_video_path,
        "-i", audio_path,
        "-t", str(duration + 0.5),
        "-vf", (
            f"scale=1080:1920:force_original_aspect_ratio=increase,"
            f"crop=1080:1920,"
            f"subtitles={captions_path}:force_style='{caption_style}'"
        ),
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        output_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"FFmpeg error: {result.stderr[-500:]}")
        raise RuntimeError("Video assembly failed")

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    logger.info(f"Video assembled: {output_path} ({size_mb:.1f} MB)")
    return output_path
