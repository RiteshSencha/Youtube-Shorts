import os
import re
import json
import requests
import subprocess
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from io import BytesIO
from logger import setup_logger

logger = setup_logger()

POLLINATIONS_URL = "https://image.pollinations.ai/prompt/{prompt}?width=1080&height=1920&nologo=true&seed={seed}"
FONT_BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
FONT_REGULAR = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"


def generate_ai_image(prompt, output_path, seed=42):
    """Generate AI background image via Pollinations.ai — completely free, no API key."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    enhanced = f"cinematic dark {prompt}, dramatic space science background, moody atmospheric lighting, 4k ultra detailed"
    url = POLLINATIONS_URL.format(
        prompt=requests.utils.quote(enhanced),
        seed=seed
    )

    try:
        logger.info(f"Generating AI image: {prompt}")
        resp = requests.get(url, timeout=90)
        resp.raise_for_status()
        with open(output_path, "wb") as f:
            f.write(resp.content)
        logger.info(f"AI image saved: {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"AI image failed: {e} — using gradient fallback")
        return _create_gradient(output_path)


def _create_gradient(output_path):
    img = Image.new("RGB", (1080, 1920))
    draw = ImageDraw.Draw(img)
    for y in range(1920):
        r = int(5 + (y / 1920) * 10)
        g = int(5 + (y / 1920) * 5)
        b = int(20 + (y / 1920) * 30)
        draw.line([(0, y), (1080, y)], fill=(r, g, b))
    img.save(output_path, "JPEG", quality=95)
    return output_path


def _load_fonts():
    sizes = {}
    for font_path in [FONT_BOLD, "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]:
        if os.path.exists(font_path):
            try:
                sizes["header"] = ImageFont.truetype(font_path, 72)
                sizes["main"] = ImageFont.truetype(font_path, 56)
                sizes["small"] = ImageFont.truetype(font_path, 38)
                return sizes
            except Exception:
                continue
    # Fallback to default font
    default = ImageFont.load_default()
    return {"header": default, "main": default, "small": default}


def _wrap_text(text, font, max_width, draw):
    words = text.split()
    lines = []
    current = []

    for word in words:
        test = " ".join(current + [word])
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] > max_width and current:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return lines


def create_segment_frame(sentence, bg_image_path, frame_path, seg_index, total_segs, is_hook=False):
    """Create one visual card for a sentence segment."""
    # Load and process background
    try:
        img = Image.open(bg_image_path).convert("RGB")
    except Exception:
        img = Image.new("RGB", (1080, 1920), (5, 5, 20))

    img = img.resize((1080, 1920), Image.LANCZOS)
    img = img.filter(ImageFilter.GaussianBlur(radius=10))

    # Darken background significantly
    enhancer = ImageEnhance.Brightness(img)
    img = enhancer.enhance(0.35)

    # Add subtle dark gradient overlay at top and bottom
    overlay = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    ov_draw = ImageDraw.Draw(overlay)
    for y in range(300):
        alpha = int(180 * (1 - y / 300))
        ov_draw.line([(0, y), (1080, y)], fill=(0, 0, 0, alpha))
    for y in range(300):
        alpha = int(180 * (y / 300))
        ov_draw.line([(0, 1920 - 300 + y), (1080, 1920 - 300 + y)], fill=(0, 0, 0, alpha))

    img = img.convert("RGBA")
    img = Image.alpha_composite(img, overlay)
    img = img.convert("RGB")

    draw = ImageDraw.Draw(img)
    fonts = _load_fonts()

    # — Top: channel branding —
    draw.text((540, 100), "SCIENCE FACTS DAILY", font=fonts["small"],
              fill="#FFD700", anchor="mm", stroke_width=2, stroke_fill="black")

    # — "DID YOU KNOW?" banner on first segment —
    if is_hook:
        banner_y = 220
        draw.rounded_rectangle([140, banner_y - 45, 940, banner_y + 45], radius=30,
                                fill=(255, 215, 0, 220))
        draw.text((540, banner_y), "DID YOU KNOW?", font=fonts["header"],
                  fill="#0a0a1a", anchor="mm")

    # — Main text centered —
    max_text_width = 920
    lines = _wrap_text(sentence, fonts["main"], max_text_width, draw)
    line_height = 75
    total_text_height = len(lines) * line_height
    start_y = (1920 - total_text_height) // 2 - 40

    for i, line in enumerate(lines):
        y = start_y + i * line_height
        # Shadow
        draw.text((543, y + 4), line, font=fonts["main"], fill="black", anchor="mm")
        # Main white text
        draw.text((540, y), line, font=fonts["main"], fill="white", anchor="mm")

    # — Bottom: progress dots —
    dot_y = 1820
    dot_r = 10
    spacing = 32
    total_w = (total_segs - 1) * spacing
    start_x = (1080 - total_w) // 2
    for i in range(total_segs):
        x = start_x + i * spacing
        color = "#FFD700" if i == seg_index else "#444444"
        draw.ellipse([x - dot_r, dot_y - dot_r, x + dot_r, dot_y + dot_r], fill=color)

    img.save(frame_path, "JPEG", quality=95)
    return frame_path


def get_audio_duration(audio_path):
    cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", audio_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    data = json.loads(result.stdout)
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "audio":
            return float(stream.get("duration", 55))
    return 55.0


def assemble_video(ai_image_path, audio_path, narration, output_path="output/final.mp4"):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    duration = get_audio_duration(audio_path)

    # Split narration into sentences
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', narration.strip()) if s.strip()]
    if not sentences:
        sentences = [narration]

    # Calculate time per segment proportional to word count
    word_counts = [len(s.split()) for s in sentences]
    total_words = sum(word_counts)
    seg_durations = [max(2.0, (wc / total_words) * duration) for wc in word_counts]

    # Normalize to actual audio duration
    scale = duration / sum(seg_durations)
    seg_durations = [d * scale for d in seg_durations]

    logger.info(f"Creating {len(sentences)} text cards for {duration:.1f}s video")

    out_dir = os.path.dirname(output_path)
    frame_paths = []

    for i, (sentence, seg_dur) in enumerate(zip(sentences, seg_durations)):
        frame_path = os.path.join(out_dir, f"frame_{i:03d}.jpg")
        create_segment_frame(
            sentence, ai_image_path, frame_path,
            seg_index=i, total_segs=len(sentences),
            is_hook=(i == 0)
        )
        frame_paths.append((frame_path, seg_dur))
        logger.info(f"Frame {i+1}/{len(sentences)}: {sentence[:40]}... ({seg_dur:.1f}s)")

    # Write FFmpeg concat file
    concat_path = os.path.join(out_dir, "concat.txt")
    with open(concat_path, "w") as f:
        for frame_path, dur in frame_paths:
            f.write(f"file '{os.path.abspath(frame_path)}'\n")
            f.write(f"duration {dur:.3f}\n")
        # Repeat last frame to avoid black tail
        f.write(f"file '{os.path.abspath(frame_paths[-1][0])}'\n")

    # Assemble final video
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", concat_path,
        "-i", audio_path,
        "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,fps=30",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "128k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        output_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"FFmpeg error: {result.stderr[-800:]}")
        raise RuntimeError("Video assembly failed")

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    logger.info(f"Video assembled: {output_path} ({size_mb:.1f} MB)")

    # Cleanup temp frames
    for frame_path, _ in frame_paths:
        try:
            os.remove(frame_path)
        except Exception:
            pass
    try:
        os.remove(concat_path)
    except Exception:
        pass

    return output_path
