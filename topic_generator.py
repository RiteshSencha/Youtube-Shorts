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

    prompt = f"""You are a science content creator for YouTube Shorts. Generate {count} SCIENCE FACT video topics.

STRICT RULES:
- Every topic MUST be a real, verifiable, specific scientific fact with a number or statistic
- ABSOLUTELY NO motivation, self-help, inspiration, mindset, or galaxy-brain metaphors
- Must be shocking, weird, or counterintuitive
- Must be about: {topics}
- GOOD examples: "Mantis Shrimp Can Punch at 80km/h", "Your Body Makes 25 Million New Cells Per Second", "Sharks Are Older Than Trees"
- BAD examples: anything with "mind", "galaxy", "potential", "journey", "inspire", "amazing you"

Return ONLY a JSON array, no explanation, no markdown:
[
  {{
    "title": "Shocking science fact title under 60 chars (e.g. 'Your Brain Produces Enough Electricity to Power a Light Bulb')",
    "hook": "One shocking opening fact sentence (e.g. 'Did you know your stomach acid can dissolve razor blades?')",
    "core_message": "The main science fact explained simply in one sentence",
    "keywords": ["science", "facts"],
    "pexels_search": "2-3 word visual search term related to the science topic",
    "virality_score": 8
  }}
]

Order by virality_score descending. Make every topic genuinely surprising and educational."""

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

    prompt = f"""You are a science content creator for YouTube Shorts. Generate ONE science fact video topic.

STRICT RULES:
- Must be a real, specific scientific fact with a number or statistic
- ABSOLUTELY NO motivation, self-help, inspiration, or vague metaphors
- Must be shocking, weird, or counterintuitive
- Topic area: {topics}
- GOOD: "Octopuses Have 3 Hearts and Blue Blood", "The Sun Makes a Sound But We Can't Hear It"
- BAD: anything vague, motivational or about "potential", "mind", "journey"

Return ONLY a JSON object, no explanation:
{{
  "title": "Shocking science fact title under 60 chars",
  "hook": "One shocking opening science fact sentence starting with 'Did you know'",
  "core_message": "The main science fact in one sentence",
  "keywords": ["science", "facts", "didyouknow"],
  "pexels_search": "2-3 word visual search related to the science topic",
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
