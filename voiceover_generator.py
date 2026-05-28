import os
import asyncio
import edge_tts
from logger import setup_logger

logger = setup_logger()

VOICES = {
    "male_deep": "en-US-ChristopherNeural",
    "male_energetic": "en-US-GuyNeural",
    "female_powerful": "en-US-JennyNeural",
    "british_male": "en-GB-RyanNeural",
}


async def _generate_tts(text, output_path, voice, speed):
    communicate = edge_tts.Communicate(text, voice, rate=speed)
    await communicate.save(output_path)


def generate_voiceover(script, config, output_path="output/voiceover.mp3"):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    voice = config["audio"].get("voice", "en-US-ChristopherNeural")
    speed = config["audio"].get("speed", "+5%")
    narration = script["narration"]

    logger.info(f"Generating voiceover with {voice}...")

    try:
        asyncio.run(_generate_tts(narration, output_path, voice, speed))
        size = os.path.getsize(output_path)
        logger.info(f"Voiceover saved: {output_path} ({size} bytes)")
        return output_path
    except Exception as e:
        logger.error(f"Voiceover generation failed: {e}")
        raise
