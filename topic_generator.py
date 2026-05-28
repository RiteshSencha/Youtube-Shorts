import os
import json
import re
from groq import Groq
from logger import setup_logger

logger = setup_logger()

MODEL = "llama3-8b-8192"


def _call_groq(prompt):
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.9,
        max_tokens=800,
    )
    return response.choices[0].message.content


def generate_best_topic(config, count=5):
    topics = ", ".join(config["content"]["topics"])
    avoid = ", ".join(config["content"]["avoid"])

    prompt = f"""Generate {count} different viral YouTube Shorts motivation topics.

Theme areas: {topics}
Avoid: {avoid}

Return ONLY a JSON array of {count} objects. No explanation, no markdown, just the array:
[
  {{
    "title": "short punchy title under 60 chars",
    "hook": "one powerful opening sentence that grabs attention in 3 seconds",
    "core_message": "the main motivational message in one sentence",
    "keywords": ["keyword1", "keyword2"],
    "pexels_search": "2-3 word visual search term",
    "virality_score": 8
  }}
]

Order by virality_score descending."""

    try:
        text = _call_groq(prompt)
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if match:
            topics_list = json.loads(match.group())
            best = max(topics_list, key=lambda x: x.get("virality_score", 0))
            logger.info(f"Best topic: {best['title']} (virality: {best.get('virality_score')})")
            return best
    except Exception as e:
        logger.error(f"Multi-topic generation failed: {e}, trying single topic")

    return generate_topic(config)


def generate_topic(config):
    topics = ", ".join(config["content"]["topics"])
    avoid = ", ".join(config["content"]["avoid"])

    prompt = f"""Generate one viral YouTube Shorts motivation topic.

Theme areas: {topics}
Avoid: {avoid}

Return ONLY a JSON object. No explanation, no markdown:
{{
  "title": "short punchy title under 60 chars",
  "hook": "one powerful opening sentence",
  "core_message": "the main motivational message",
  "keywords": ["keyword1", "keyword2"],
  "pexels_search": "2-3 word visual search term",
  "virality_score": 8
}}"""

    try:
        text = _call_groq(prompt)
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            topic = json.loads(match.group())
            logger.info(f"Topic generated: {topic['title']}")
            return topic
    except Exception as e:
        logger.error(f"Topic generation failed: {e}")
        raise

    raise ValueError("Could not parse topic from Groq response")
