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

    prompt = f"""You are a viral science YouTube Shorts scriptwriter. Write a {duration}-second script.

Topic: {topic['title']}
Hook: {topic['hook']}
Core fact: {topic['core_message']}

STRICT RULES:
- SCIENCE FACTS ONLY — absolutely NO motivation, self-help or inspirational content
- First sentence MUST be just the shocking number/stat — e.g. "80 kilometers per hour." or "3 hearts."
- Second sentence explains what it is — e.g. "That's how fast a mantis shrimp punches."
- Maximum 8 words per sentence — shorter is better
- Add ONE cliffhanger mid-script — e.g. "But here's the crazy part." or "Wait, it gets weirder."
- Conversational tone — like you're texting a friend
- End with "Follow for more insane science facts."
- Target: exactly {target_words} words

GOOD example (copy this structure exactly):
"25 million. That's how many new cells your body just made. While you read that sentence. But here's the crazy part. Your body also destroys 25 million cells at the same time. Every single second. Perfect balance. Follow for more insane science facts."

BAD example (never do this):
"Did you know that the human body is amazing and makes lots of cells every day..."

Return ONLY a JSON object:
{{
  "narration": "script here...",
  "word_count": {target_words},
  "title": "Shocking science title under 55 chars #Shorts",
  "description": "2 sentence description",
  "hashtags": "#shorts #trending #explore #sciencefacts #science_facts #foryou #viral #didyouknow #funfacts #amazingfacts #scienceshorts #educational #learnontiktok"
}}"""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
            max_tokens=1200,
        )
        text = response.choices[0].message.content
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            clean = match.group()
            clean = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', clean)
            clean = clean.replace('\t', ' ')
            clean = re.sub(r'\n', ' ', clean)
            script = json.loads(clean)
            logger.info(f"Script generated: {script.get('word_count', '?')} words")
            return script
    except Exception as e:
        logger.error(f"Script generation failed: {e}")
        raise

    raise ValueError("Could not parse script from Groq response")
