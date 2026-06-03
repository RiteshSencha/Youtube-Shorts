import os
import re
import json
import random
import requests
import subprocess
from logger import setup_logger

logger = setup_logger()

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


def generate_ai_images(sentences, topic_title, out_dir, count=4):
    """Generate one AI image per group of sentences."""
    os.makedirs(out_dir, exist_ok=True)
    images = []

    # Build prompts based on topic
    base_prompt = f"cinematic {topic_title}, dramatic science photography, dark moody atmosphere, 4k ultra detailed"
    prompts = [
        f"{base_prompt}, wide establishing shot",
        f"macro extreme closeup scientific detail, {topic_title}, dramatic lighting",
        f"deep space science visualization, {topic_title}, photorealistic",
        f"cinematic science documentary shot, {topic_title}, atmospheric",
    ]

    # Only generate as many images as we need (max count)
    num_images = min(count, len(sentences))

    for i in range(num_images):
        img_path = os.path.join(out_dir, f"ai_img_{i:02d}.jpg")
        prompt = prompts[i % len(prompts)]
        seed = random.randint(1, 99999)

        try:
            logger.info(f"Generating AI image {i+1}/{num_images}...")
            url = POLLINATIONS_URL.format(
                prompt=requests.utils.quote(prompt),
                seed=seed
            )
            resp = requests.get(url, timeout=90)
            resp.raise_for_status()
            with open(img_path, "wb") as f:
                f.write(resp.content)
            images.append(img_path)
            logger.info(f"AI image {i+1} saved.")
        except Exception as e:
            logger.error(f"AI image {i+1} failed: {e}, using gradient")
            img_path = _create_gradient(img_path, i)
            images.append(img_path)

    return images


def _create_gradient(output_path, index=0):
    colors = ["0x050520", "0x100520", "0x051020", "0x050a15"]
    color = colors[index % len(colors)]
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", f"color=c={color}:size=1080x1920:rate=30",
        "-frames:v", "1", output_path
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


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


def create_segment_clip(image_path, audio_path, sentence, seg_duration,
                        seg_index, total_segs, is_first, font_path, out_path):
    """Create one video clip: Ken Burns on image + text overlay."""
    frames = int(seg_duration * 30)
    drift = random.choice([80, -80, 60, -60])
    effect_template = random.choice(KEN_BURNS_EFFECTS)
    effect = effect_template.format(d=frames, drift=drift)

    wrapped_lines = _wrap(_escape(sentence), max_chars=20)
    line_h = 72
    total_h = len(wrapped_lines) * line_h
    start_y_base = 960 - total_h // 2  # vertical center

    # Build drawtext filters
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

    # Main sentence text lines
    for i, line in enumerate(wrapped_lines):
        y = start_y_base + i * line_h
        dt_filters.append(
            f"drawtext=fontfile='{font_path}':"
            f"text='{line}':"
            f"fontsize=62:fontcolor=white:"
            f"x=(w-text_w)/2:y={y}:"
            f"shadowcolor=black:shadowx=4:shadowy=4"
        )

    # Minimal progress bar only — no text counter
    bar_filled = int((seg_index + 1) / total_segs * 980)
    dt_filters.append(
        f"drawbox=x=50:y=1870:w=980:h=6:color=0x333333@0.7:t=fill"
    )
    dt_filters.append(
        f"drawbox=x=50:y=1870:w={bar_filled}:h=6:color=0xFFD700@0.9:t=fill"
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
        "-loop", "1", "-i", image_path,
        "-t", str(seg_duration),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-an",
        out_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"Clip error: {result.stderr[-500:]}")
        raise RuntimeError(f"Clip {seg_index} failed")
    return out_path


def assemble_video(bg_placeholder, audio_path, narration, output_path="output/final.mp4"):
    """Main assembly: AI images + Ken Burns + text + audio."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    out_dir = os.path.dirname(output_path)
    font_path = get_font()

    duration = get_audio_duration(audio_path)

    # Split narration into sentences
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', narration.strip()) if s.strip()]
    if not sentences:
        sentences = [narration]

    # Time each sentence by word count
    word_counts = [len(s.split()) for s in sentences]
    total_words = sum(word_counts)
    raw_durs = [max(2.0, (wc / total_words) * duration) for wc in word_counts]
    scale = duration / sum(raw_durs)
    durations = [d * scale for d in raw_durs]

    logger.info(f"Pipeline: {len(sentences)} sentences | {duration:.1f}s total")

    # Extract topic from bg_placeholder path for image prompts
    topic_hint = os.path.basename(bg_placeholder).replace("background_", "").replace(".mp4", "").replace("_", " ")

    # Generate AI images
    num_images = min(4, len(sentences))
    images = generate_ai_images(sentences, topic_hint, out_dir, count=num_images)

    # Create one clip per sentence
    clip_paths = []
    for i, (sentence, dur) in enumerate(zip(sentences, durations)):
        img = images[i % len(images)]
        clip_path = os.path.join(out_dir, f"clip_{i:03d}.mp4")
        create_segment_clip(
            image_path=img,
            audio_path=audio_path,
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

    # Concat all clips
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

    # Merge video + audio
    cmd = [
        "ffmpeg", "-y",
        "-i", concat_video,
        "-i", audio_path,
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "128k",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-shortest",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"Merge error: {result.stderr[-500:]}")
        raise RuntimeError("Audio merge failed")

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    logger.info(f"Final video: {output_path} ({size_mb:.1f} MB)")

    # Cleanup temp files
    for cp in clip_paths:
        try: os.remove(cp)
        except: pass
    for f in [concat_file, concat_video]:
        try: os.remove(f)
        except: pass

    return output_path
