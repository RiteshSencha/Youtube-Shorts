import os
import re
import json
import random
import requests
import subprocess
from logger import setup_logger

logger = setup_logger()

PEXELS_VIDEO_API = "https://api.pexels.com/videos/search"
PEXELS_PHOTO_API = "https://api.pexels.com/v1/search"

FONT_PATHS = [
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]


def get_font():
    for fp in FONT_PATHS:
        if os.path.exists(fp):
            return fp
    raise RuntimeError("No font found. Install fonts-liberation.")


def fetch_pexels_video(query, api_key, output_path, min_duration=8, used_ids=None):
    """Download a portrait video clip from Pexels."""
    try:
        headers = {"Authorization": api_key}
        params = {"query": query, "per_page": 20, "orientation": "portrait", "size": "medium"}
        resp = requests.get(PEXELS_VIDEO_API, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        videos = resp.json().get("videos", [])
        if not videos:
            return None

        # Filter for usable clips, avoid already-used videos
        usable = [v for v in videos
                  if v.get("duration", 0) >= min_duration
                  and v.get("id") not in (used_ids or set())]
        if not usable:
            usable = [v for v in videos if v.get("id") not in (used_ids or set())]
        if not usable:
            usable = videos

        video = random.choice(usable[:10])
        # Pick best quality video file
        files = sorted(video.get("video_files", []), key=lambda x: x.get("width", 0), reverse=True)
        portrait_files = [f for f in files if f.get("height", 0) > f.get("width", 0)]
        chosen = (portrait_files or files)[0]
        video_url = chosen["link"]

        r = requests.get(video_url, timeout=60, stream=True)
        r.raise_for_status()
        with open(output_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

        size_kb = os.path.getsize(output_path) // 1024
        if size_kb < 50:
            return None
        logger.info(f"Pexels video saved: {output_path} ({size_kb}KB, {video.get('duration')}s)")
        return output_path
    except Exception as e:
        logger.error(f"Pexels video failed: {e}")
        return None


def fetch_pexels_photo(query, api_key, output_path):
    """Fallback: portrait photo from Pexels."""
    try:
        headers = {"Authorization": api_key}
        params = {"query": query, "per_page": 15, "orientation": "portrait"}
        resp = requests.get(PEXELS_PHOTO_API, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        photos = resp.json().get("photos", [])
        if not photos:
            return None
        photo = random.choice(photos[:8])
        img_url = photo["src"].get("large2x") or photo["src"]["large"]
        r = requests.get(img_url, timeout=30)
        r.raise_for_status()
        if len(r.content) < 10000:
            return None
        with open(output_path, "wb") as f:
            f.write(r.content)
        logger.info(f"Pexels photo saved: {output_path} ({len(r.content)//1024}KB)")
        return output_path
    except Exception as e:
        logger.error(f"Pexels photo failed: {e}")
        return None


def create_solid_background(output_path, index=0):
    """Last resort — dark gradient background."""
    colors = [("0x050520", "0x0a0a30"), ("0x100520", "0x200a30"),
              ("0x051020", "0x0a2030"), ("0x050a15", "0x0a1525")]
    c1, c2 = colors[index % len(colors)]
    cmd = ["ffmpeg", "-y", "-f", "lavfi",
           "-i", f"color=c={c1}:size=1080x1920:rate=30",
           "-t", "10", output_path]
    subprocess.run(cmd, capture_output=True)
    return output_path


def generate_backgrounds(topic, out_dir, count=4):
    """Download video clips from Pexels matching the topic."""
    os.makedirs(out_dir, exist_ok=True)
    pexels_key = os.environ.get("PEXELS_API_KEY", "")
    subject = topic.get("pexels_search", topic.get("title", "science"))

    queries = [
        subject,
        f"{subject} closeup",
        f"{subject} nature",
        f"{subject} slow motion",
        f"{subject} wildlife",
        f"{subject} macro",
        f"{subject} aerial",
        f"{subject} underwater",
        f"{subject} timelapse",
        f"{subject} cinematic",
        f"{subject} 4k",
        f"{subject} dramatic",
    ]
    random.shuffle(queries)

    used_video_ids = set()
    clips = []
    for i in range(count):
        clip_path = os.path.join(out_dir, f"bg_{i:02d}.mp4")
        photo_path = os.path.join(out_dir, f"bg_{i:02d}.jpg")
        result = None

        if pexels_key:
            # Try two different queries per slot to maximise variety
            for attempt in range(2):
                q = queries[(i * 2 + attempt) % len(queries)]
                result = fetch_pexels_video(q, pexels_key, clip_path, used_ids=used_video_ids)
                if result:
                    break

        # Fallback to photo if video fails
        if not result and pexels_key:
            result = fetch_pexels_photo(queries[i % len(queries)], pexels_key, photo_path)

        if not result:
            logger.warning(f"Using solid background for clip {i+1}")
            result = create_solid_background(clip_path, i)

        clips.append(result)
        logger.info(f"Background {i+1}/{count} ready")

    return clips


def get_audio_duration(audio_path):
    cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", audio_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    data = json.loads(result.stdout)
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "audio":
            return float(stream.get("duration", 55))
    return 55.0


def _escape(text):
    text = text.replace("\\", "")
    text = text.replace("'", "’")
    text = text.replace(":", "\\:")
    text = text.replace("%", "\\%")
    text = text.replace("[", "").replace("]", "")
    return text


def _wrap(text, max_chars=20):
    words = text.split()
    lines, current, length = [], [], 0
    for word in words:
        if length + len(word) + 1 > max_chars and current:
            lines.append(" ".join(current))
            current, length = [word], len(word)
        else:
            current.append(word)
            length += len(word) + 1
    if current:
        lines.append(" ".join(current))
    return lines


def is_video_file(path):
    return path and path.endswith(".mp4")


def create_segment_clip(bg_path, sentence, seg_duration,
                        seg_index, total_segs, is_first, font_path, out_path):

    wrapped_lines = _wrap(_escape(sentence), max_chars=22)
    line_h = 75
    total_h = len(wrapped_lines) * line_h
    start_y_base = 960 - total_h // 2

    dt_filters = []

    if is_first:
        dt_filters.append(
            f"drawtext=fontfile='{font_path}':"
            f"text='DID YOU KNOW ?':"
            f"fontsize=58:fontcolor=0xFFD700:"
            f"x=(w-text_w)/2:y=160:"
            f"shadowcolor=black:shadowx=3:shadowy=3"
        )

    for i, line in enumerate(wrapped_lines):
        y = start_y_base + i * line_h
        # Dark semi-transparent box behind text
        box_pad = 18
        dt_filters.append(
            f"drawtext=fontfile='{font_path}':"
            f"text='{line}':"
            f"fontsize=64:fontcolor=white:"
            f"x=(w-text_w)/2:y={y}:"
            f"shadowcolor=black:shadowx=5:shadowy=5:"
            f"box=1:boxcolor=black@0.45:boxborderw={box_pad}"
        )

    all_dt = ",".join(dt_filters)

    if is_video_file(bg_path):
        # Use real video clip — scale/crop to portrait, trim to segment duration
        vf = (
            f"scale=1080:1920:force_original_aspect_ratio=increase,"
            f"crop=1080:1920,"
            f"eq=brightness=-0.05:saturation=1.3,"
            f"{all_dt}"
        )
        cmd = [
            "ffmpeg", "-y",
            "-stream_loop", "-1", "-i", bg_path,
            "-t", str(seg_duration),
            "-vf", vf,
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-pix_fmt", "yuv420p",
            "-r", "30",
            "-an",
            out_path
        ]
    else:
        # Fallback: still image with Ken Burns
        frames = int(seg_duration * 30)
        effect = f"zoompan=z='min(zoom+0.002,1.35)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s=1080x1920:fps=30"
        vf = (
            f"scale=1080:1920:force_original_aspect_ratio=increase,"
            f"crop=1080:1920,"
            f"{effect},"
            f"eq=brightness=-0.05:saturation=1.3,"
            f"{all_dt}"
        )
        cmd = [
            "ffmpeg", "-y",
            "-framerate", "30",
            "-loop", "1", "-i", bg_path,
            "-t", str(seg_duration),
            "-vf", vf,
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-pix_fmt", "yuv420p",
            "-r", "30",
            "-an",
            out_path
        ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"Clip {seg_index} error: {result.stderr[-500:]}")
        raise RuntimeError(f"Clip {seg_index} failed")
    return out_path


def assemble_video(topic, audio_path, narration, output_path="output/final.mp4"):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    out_dir = os.path.dirname(output_path)
    font_path = get_font()
    duration = get_audio_duration(audio_path)

    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', narration.strip()) if s.strip()]
    if not sentences:
        sentences = [narration]

    word_counts = [len(s.split()) for s in sentences]
    total_words = sum(word_counts)
    raw_durs = [max(2.0, (wc / total_words) * duration) for wc in word_counts]
    scale = duration / sum(raw_durs)
    durations = [d * scale for d in raw_durs]

    logger.info(f"Pipeline: {len(sentences)} sentences | {duration:.1f}s")

    backgrounds = generate_backgrounds(topic, out_dir, count=len(sentences))

    clip_paths = []
    for i, (sentence, dur) in enumerate(zip(sentences, durations)):
        bg = backgrounds[i]
        clip_path = os.path.join(out_dir, f"clip_{i:03d}.mp4")
        create_segment_clip(
            bg_path=bg,
            sentence=sentence,
            seg_duration=dur,
            seg_index=i,
            total_segs=len(sentences),
            is_first=(i == 0),
            font_path=font_path,
            out_path=clip_path
        )
        clip_paths.append(clip_path)
        logger.info(f"Clip {i+1}/{len(sentences)} done")

    concat_file = os.path.join(out_dir, "concat.txt")
    with open(concat_file, "w") as f:
        for cp in clip_paths:
            f.write(f"file '{os.path.abspath(cp)}'\n")

    concat_video = os.path.join(out_dir, "concat_video.mp4")
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", concat_file,
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-pix_fmt", "yuv420p",
        concat_video
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"Concat error: {result.stderr[-500:]}")
        raise RuntimeError("Concat failed")

    cmd = [
        "ffmpeg", "-y",
        "-i", concat_video,
        "-i", audio_path,
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "128k",
        "-map", "0:v:0", "-map", "1:a:0",
        "-shortest",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"Merge error: {result.stderr[-500:]}")
        raise RuntimeError("Audio merge failed")

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    logger.info(f"Final video: {output_path} ({size_mb:.1f} MB)")

    for cp in clip_paths:
        try: os.remove(cp)
        except: pass
    for bg in backgrounds:
        try: os.remove(bg)
        except: pass
    for f in [concat_file, concat_video]:
        try: os.remove(f)
        except: pass

    return output_path
