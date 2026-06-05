import os
import re
import json
import random
import requests
import subprocess
from logger import setup_logger

logger = setup_logger()

PEXELS_PHOTO_API = "https://api.pexels.com/v1/search"
POLLINATIONS_URL = "https://image.pollinations.ai/prompt/{prompt}?width=1080&height=1920&nologo=true&seed={seed}"

FONT_PATHS = [
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]

KEN_BURNS_EFFECTS = [
    "zoompan=z='min(zoom+0.0025,1.4)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={d}:s=1080x1920:fps=30",
    "zoompan=z='if(lte(zoom,1.0),1.4,max(1.001,zoom-0.0025))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={d}:s=1080x1920:fps=30",
    "zoompan=z='min(zoom+0.002,1.35)':x='iw/2-(iw/zoom/2)+{drift}*(on/{d})':y='ih/2-(ih/zoom/2)':d={d}:s=1080x1920:fps=30",
    "zoompan=z='1.35':x='iw/2-(iw/zoom/2)+80*(on/{d})':y='ih/2-(ih/zoom/2)-50*(on/{d})':d={d}:s=1080x1920:fps=30",
]


def get_font():
    for fp in FONT_PATHS:
        if os.path.exists(fp):
            return fp
    raise RuntimeError("No font found. Install fonts-liberation.")


def fetch_pexels_photo(query, api_key, output_path):
    """Download a portrait photo from Pexels — primary background source."""
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


def fetch_pollinations_image(prompt, output_path, seed=42):
    """AI-generated image via Pollinations.ai — secondary fallback."""
    try:
        url = POLLINATIONS_URL.format(
            prompt=requests.utils.quote(prompt),
            seed=seed
        )
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
        if len(resp.content) < 10000:
            return None
        with open(output_path, "wb") as f:
            f.write(resp.content)
        logger.info(f"Pollinations image saved ({len(resp.content)//1024}KB)")
        return output_path
    except Exception as e:
        logger.error(f"Pollinations failed: {e}")
        return None


def create_solid_background(output_path, index=0):
    """Last resort — dark gradient background."""
    colors = [
        ("0x050520", "0x0a0a30"),
        ("0x100520", "0x200a30"),
        ("0x051020", "0x0a2030"),
        ("0x050a15", "0x0a1525"),
    ]
    c1, c2 = colors[index % len(colors)]
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", f"gradients=s=1080x1920:c0={c1}:c2={c2}:type=linear:speed=0",
        "-frames:v", "1", "-update", "1", output_path
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        # Ultra fallback
        cmd2 = [
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", f"color=c={c1}:size=1080x1920:rate=1",
            "-frames:v", "1", output_path
        ]
        subprocess.run(cmd2, capture_output=True)
    return output_path


def generate_backgrounds(topic, out_dir, count=4):
    """Generate background images: Pexels first, Pollinations fallback."""
    os.makedirs(out_dir, exist_ok=True)
    pexels_key = os.environ.get("PEXELS_API_KEY", "")
    topic_search = topic.get("pexels_search", topic.get("title", "science"))
    title = topic.get("title", "science facts")

    images = []
    queries = [
        topic_search,
        f"{topic_search} closeup",
        f"{topic_search} nature",
        "science laboratory microscope",
    ]

    for i in range(count):
        img_path = os.path.join(out_dir, f"bg_{i:02d}.jpg")
        result = None

        # Try Pexels photo first
        if pexels_key:
            result = fetch_pexels_photo(queries[i % len(queries)], pexels_key, img_path)

        # Try Pollinations as fallback
        if not result:
            prompt = f"cinematic {queries[i % len(queries)]}, dark dramatic photography, 4k"
            result = fetch_pollinations_image(prompt, img_path, seed=random.randint(1, 99999))

        # Solid color as last resort
        if not result:
            logger.warning(f"Using solid background for image {i+1}")
            result = create_solid_background(img_path, i)

        images.append(result)
        logger.info(f"Background {i+1}/{count} ready")

    return images


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


def create_segment_clip(image_path, sentence, seg_duration,
                        seg_index, total_segs, is_first, font_path, out_path):
    frames = int(seg_duration * 30)
    drift = random.choice([80, -80, 60, -60])
    effect = random.choice(KEN_BURNS_EFFECTS).format(d=frames, drift=drift)

    wrapped_lines = _wrap(_escape(sentence), max_chars=20)
    line_h = 72
    total_h = len(wrapped_lines) * line_h
    start_y_base = 960 - total_h // 2

    dt_filters = []

    # "DID YOU KNOW?" on first clip
    if is_first:
        dt_filters.append(
            f"drawtext=fontfile='{font_path}':"
            f"text='DID YOU KNOW ?':"
            f"fontsize=60:fontcolor=0xFFD700:"
            f"x=(w-text_w)/2:y=160:"
            f"shadowcolor=black:shadowx=3:shadowy=3"
        )

    # Main sentence lines
    for i, line in enumerate(wrapped_lines):
        y = start_y_base + i * line_h
        dt_filters.append(
            f"drawtext=fontfile='{font_path}':"
            f"text='{line}':"
            f"fontsize=62:fontcolor=white:"
            f"x=(w-text_w)/2:y={y}:"
            f"shadowcolor=black:shadowx=4:shadowy=4"
        )

    all_dt = ",".join(dt_filters)

    vf = (
        f"scale=1080:1920:force_original_aspect_ratio=increase,"
        f"crop=1080:1920,"
        f"{effect},"
        f"colorchannelmixer=rr=0.55:gg=0.55:bb=0.65,"
        f"{all_dt}"
    )

    cmd = [
        "ffmpeg", "-y",
        "-framerate", "30",
        "-loop", "1", "-i", image_path,
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

    # Generate backgrounds
    num_images = min(4, len(sentences))
    images = generate_backgrounds(topic, out_dir, count=num_images)

    # Create clips
    clip_paths = []
    for i, (sentence, dur) in enumerate(zip(sentences, durations)):
        img = images[i % len(images)]
        clip_path = os.path.join(out_dir, f"clip_{i:03d}.mp4")
        create_segment_clip(
            image_path=img,
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

    # Concat clips
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

    # Merge with audio
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

    # Cleanup
    for cp in clip_paths:
        try: os.remove(cp)
        except: pass
    for f in [concat_file, concat_video]:
        try: os.remove(f)
        except: pass

    return output_path
