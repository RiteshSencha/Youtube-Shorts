import os
import json
import yaml
import random
import argparse
from datetime import datetime
from logger import setup_logger
from topic_generator import generate_best_topic
from script_generator import generate_script
from voiceover_generator import generate_voiceover
from video_assembler import assemble_video, get_audio_duration
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

        # 2. Generate script
        logger.info("=== STEP 2: Generating script ===")
        script = generate_script(topic, config)
        metadata["steps"]["script"] = script

        # 3. Generate voiceover
        logger.info("=== STEP 3: Generating voiceover ===")
        audio_path = f"output/voiceover_{timestamp}.mp3"
        generate_voiceover(script, config, audio_path)
        metadata["steps"]["audio"] = audio_path

        # 4. Assemble video (AI images + Ken Burns + text + audio)
        logger.info("=== STEP 4: Assembling AI video ===")
        bg_placeholder = f"output/background_{timestamp}.mp4"
        final_path = f"output/final_{timestamp}.mp4"
        assemble_video(bg_placeholder, audio_path, script["narration"], final_path)
        metadata["steps"]["final_video"] = final_path

        # 5. Upload to YouTube
        if not test_mode:
            logger.info("=== STEP 5: Uploading to YouTube ===")
            video_id, url = upload_to_youtube(final_path, script, topic, config)
            metadata["steps"]["youtube"] = {"video_id": video_id, "url": url}
            logger.info(f"SUCCESS: {url}")
        else:
            logger.info("=== TEST MODE: Skipping upload ===")
            logger.info(f"Video saved: {final_path}")

        meta_path = f"output/metadata_{timestamp}.json"
        with open(meta_path, "w") as f:
            json.dump(metadata, f, indent=2)

        return metadata

    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        metadata["error"] = str(e)
        with open(f"output/metadata_{timestamp}_ERROR.json", "w") as f:
            json.dump(metadata, f, indent=2)
        raise


def main():
    parser = argparse.ArgumentParser(description="YouTube Shorts Bot")
    parser.add_argument("--auth", action="store_true", help="Authenticate YouTube OAuth")
    parser.add_argument("--test", action="store_true", help="Test mode — no upload")
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()

    config = load_config(args.config)

    if args.auth:
        authenticate_youtube()
        logger.info("Auth complete.")
        return

    run_pipeline(config, test_mode=args.test)


if __name__ == "__main__":
    main()
