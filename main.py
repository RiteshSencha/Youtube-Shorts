import os
import sys
import json
import yaml
import random
import argparse
from datetime import datetime
from logger import setup_logger
from topic_generator import generate_best_topic
from script_generator import generate_script
from voiceover_generator import generate_voiceover
from caption_generator import text_to_srt
from video_assembler import download_pexels_video, assemble_video, get_audio_duration
from uploader import authenticate_youtube, upload_to_youtube

logger = setup_logger()


def load_config(path="config.yaml"):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(path, "r") as f:
        return yaml.safe_load(f)


def run_pipeline(config, test_mode=False):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs("output", exist_ok=True)
    os.makedirs("tokens", exist_ok=True)

    metadata = {"timestamp": timestamp, "steps": {}}

    try:
        # 1. Generate topic
        logger.info("=== STEP 1: Generating topic ===")
        topic = generate_best_topic(config)
        metadata["steps"]["topic"] = topic
        logger.info(f"Topic: {topic['title']}")

        # 2. Generate script
        logger.info("=== STEP 2: Generating script ===")
        script = generate_script(topic, config)
        metadata["steps"]["script"] = script

        # 3. Generate voiceover
        logger.info("=== STEP 3: Generating voiceover ===")
        audio_path = f"output/voiceover_{timestamp}.mp3"
        generate_voiceover(script, config, audio_path)
        metadata["steps"]["audio"] = audio_path

        # 4. Get audio duration for captions
        duration = get_audio_duration(audio_path)

        # 5. Generate captions
        logger.info("=== STEP 4: Generating captions ===")
        captions_path = f"output/captions_{timestamp}.srt"
        text_to_srt(script["narration"], duration, captions_path)
        metadata["steps"]["captions"] = captions_path

        # 6. Download background footage
        logger.info("=== STEP 5: Fetching background video ===")
        pexels_key = os.environ.get("PEXELS_API_KEY", "")
        bg_path = f"output/background_{timestamp}.mp4"
        pexels_queries = config["video"]["pexels_queries"]
        query = topic.get("pexels_search", random.choice(pexels_queries))
        download_pexels_video(query, pexels_key, bg_path)
        metadata["steps"]["background"] = bg_path

        # 7. Assemble final video
        logger.info("=== STEP 6: Assembling video ===")
        final_path = f"output/final_{timestamp}.mp4"
        assemble_video(bg_path, audio_path, captions_path, final_path)
        metadata["steps"]["final_video"] = final_path

        # 8. Upload to YouTube
        if not test_mode:
            logger.info("=== STEP 7: Uploading to YouTube ===")
            video_id, url = upload_to_youtube(final_path, script, topic, config)
            metadata["steps"]["youtube"] = {"video_id": video_id, "url": url}
            logger.info(f"SUCCESS: {url}")
        else:
            logger.info("=== TEST MODE: Skipping upload ===")
            logger.info(f"Video saved locally: {final_path}")

        # Save metadata
        meta_path = f"output/metadata_{timestamp}.json"
        with open(meta_path, "w") as f:
            json.dump(metadata, f, indent=2)

        return metadata

    except Exception as e:
        logger.error(f"Pipeline failed at step: {e}")
        metadata["error"] = str(e)
        meta_path = f"output/metadata_{timestamp}_ERROR.json"
        with open(meta_path, "w") as f:
            json.dump(metadata, f, indent=2)
        raise


def main():
    parser = argparse.ArgumentParser(description="YouTube Shorts Automation Bot")
    parser.add_argument("--auth", action="store_true", help="Authenticate YouTube OAuth")
    parser.add_argument("--test", action="store_true", help="Test mode (no upload)")
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    args = parser.parse_args()

    config = load_config(args.config)

    if args.auth:
        logger.info("Running YouTube authentication...")
        authenticate_youtube()
        logger.info("Authentication complete. Token saved to tokens/youtube_token.json")
        return

    run_pipeline(config, test_mode=args.test)


if __name__ == "__main__":
    main()
