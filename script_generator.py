import os
import json
import re
from groq import Groq
from logger import setup_logger

logger = setup_logger()

MODEL = "llama-3.1-8b-instant"


def generate_script(topic, config):
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

    duration = config["content"]["duration_seconds"]
    target_words = int(duration * 2.5)

    prompt = f"""Write a {duration}-second motivational YouTube Shorts script.

Topic: {topic['title']}
Hook: {topic['hook']}
Core message: {topic['core_message']}

Requirements:
- Exactly {target_words} words (plus or minus 10)
- Conversational, powerful, punchy language
- No filler words, no hashtags in the script
- Build energy from start to finish
- End with one strong call to action

Return ONLY a JSON object. No explanation, no markdown:
{{
  "narration": "full script text here...",
  "word_count": {target_words},
  "title": "YouTube title under 60 chars with #Shorts at end",
  "description": "2-3 sentence video description under 150 words",
  "hashtags": "#motivation #shorts #mindset #success #inspiration #discipline"
}}"""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
            max_tokens=1000,
        )
        text = response.choices[0].message.content
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            script = json.loads(match.group())
            logger.info(f"Script generated: {script.get('word_count', '?')} words")
            return script
    except Exception as e:
        logger.error(f"Script generation failed: {e}")
        raise

    raise ValueError("Could not parse script from Groq response")
