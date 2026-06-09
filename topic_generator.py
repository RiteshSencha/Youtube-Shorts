import os
import json
import re
from groq import Groq
from logger import setup_logger

logger = setup_logger()

MODEL = "llama-3.1-8b-instant"


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

    prompt = f"""You are a viral science content creator for YouTube Shorts. Generate {count} SCIENCE FACT video topics.

STRICT RULES:
- Every title MUST start with or prominently feature a specific number or statistic
- Must be a real, verifiable scientific fact — shocking, weird, or counterintuitive
- ABSOLUTELY NO motivation, self-help, inspiration, mindset, or vague metaphors
- Must be about: {topics}
- GOOD titles: "A Mantis Shrimp Punches at 80 km/h", "You Make 25 Million New Cells Per Second", "Sharks Existed 200 Million Years Before Trees", "A Teaspoon of Neutron Star Weighs 1 Billion Tons"
- BAD titles: anything without a number, anything vague, motivational, or about "potential", "mind", "journey"

Return ONLY a JSON array, no explanation, no markdown:
[
  {{
    "title": "Science fact title under 60 chars that MUST include a specific number",
    "hook": "One sentence starting with the shocking number — e.g. '80 km/h. That's how fast a mantis shrimp punches.'",
    "core_message": "The main science fact explained simply in one sentence",
    "keywords": ["science", "facts"],
    "pexels_search": "2-3 word visual search term for the main subject (animal/object/place)",
    "virality_score": 8
  }}
]

Order by virality_score descending. Every topic must have a jaw-dropping specific number."""

    try:
        text = _call_groq(prompt)
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if match:
            clean = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', match.group())
            topics_list = json.loads(clean)
            best = max(topics_list, key=lambda x: x.get("virality_score", 0))
            logger.info(f"Best topic: {best['title']} (virality: {best.get('virality_score')})")
            return best
    except Exception as e:
        logger.error(f"Multi-topic generation failed: {e}, trying single topic")

    return generate_topic(config)


def generate_topic(config):
    topics = ", ".join(config["content"]["topics"])

    prompt = f"""You are a viral science content creator for YouTube Shorts. Generate ONE science fact video topic.

STRICT RULES:
- Title MUST include a specific number or statistic
- Must be a real, shocking, counterintuitive scientific fact
- ABSOLUTELY NO motivation, self-help, inspiration, or vague metaphors
- Topic area: {topics}
- GOOD: "Octopuses Have 3 Hearts and Blue Blood", "A Neutron Star Teaspoon Weighs 1 Billion Tons"
- BAD: anything without a number, anything vague or motivational

Return ONLY a JSON object, no explanation:
{{
  "title": "Science fact title under 60 chars that MUST include a specific number",
  "hook": "One sentence starting with the shocking number — e.g. '3 hearts. That's what an octopus has.'",
  "core_message": "The main science fact in one sentence",
  "keywords": ["science", "facts", "didyouknow"],
  "pexels_search": "2-3 word visual search for the main subject",
  "virality_score": 8
}}"""

    try:
        text = _call_groq(prompt)
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            clean = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', match.group())
            topic = json.loads(clean)
            logger.info(f"Topic generated: {topic['title']}")
            return topic
    except Exception as e:
        logger.error(f"Topic generation failed: {e}")
        raise

    raise ValueError("Could not parse topic from Groq response")
