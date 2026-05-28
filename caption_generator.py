import os
import re
from logger import setup_logger

logger = setup_logger()


def text_to_srt(narration, duration_seconds, output_path="output/captions.srt"):
    """Generate SRT captions by splitting narration evenly across duration."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    words = narration.split()
    # Group into chunks of 4-6 words per caption line
    chunk_size = 5
    chunks = [" ".join(words[i:i+chunk_size]) for i in range(0, len(words), chunk_size)]

    time_per_chunk = duration_seconds / len(chunks)

    def fmt_time(seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    srt_lines = []
    for i, chunk in enumerate(chunks):
        start = i * time_per_chunk
        end = start + time_per_chunk - 0.1
        srt_lines.append(f"{i+1}")
        srt_lines.append(f"{fmt_time(start)} --> {fmt_time(end)}")
        srt_lines.append(chunk.upper())
        srt_lines.append("")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(srt_lines))

    logger.info(f"Captions generated: {len(chunks)} lines → {output_path}")
    return output_path
