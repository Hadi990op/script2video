"""Keyword extraction from a script, without any LLM.

Splits the script into scenes, extracts 1-2 keywords per scene
using stopword filtering + word-frequency scoring.
"""
import math
import re
from collections import Counter

# Minimal English + Roman-Urdu stopword list
STOPWORDS = set("""
a an and are as at be been but by can could do does for from get got had has have
he her him his how i if in into is it its just like me more most my no not of oh
on or out so some than that the their them they this these to too up us was we
were what when which who will with would you your about after also all any
been being because before between both during each even every first from had
having here into itself last less may might much must never next now off only
other over own same still such then there through under until very while
kya hai ho hain ki ke ka se ko ye wo na nahi tu main aur ya mera meri
apna apni kare karna karne liye bhi to par per magar lekin phir abhi ab
""".split())

# Words that indicate visual/action scenes and should boost a keyword
VISUAL_HINTS = {
    "city", "mountain", "ocean", "sea", "river", "forest", "sunset", "sunrise",
    "sky", "night", "day", "street", "road", "people", "man", "woman", "child",
    "fire", "water", "rain", "snow", "desert", "bird", "animal", "car", "train",
    "plane", "boat", "food", "coffee", "music", "dance", "sport", "game",
    "computer", "phone", "book", "school", "market", "village", "building",
    "bridge", "field", "tree", "flower", "storm", "cloud", "beach", "wind",
}


def _clean(text: str) -> str:
    return re.sub(r"[^\w\s']", " ", text.lower())


def extract_keywords(script: str, max_scenes: int = 12):
    """Split script into scenes and pick keywords for each.

    Returns list of dicts: [{"text": scene_text, "keywords": ["kw1", "kw2"]}]
    """
    words = _clean(script).split()
    total = len(words)
    if total == 0:
        return []

    # Scene size: aim for max_scenes scenes of 6-8 second clips
    n_scenes = max(1, min(max_scenes, math.ceil(total / 12)))
    chunk = math.ceil(total / n_scenes)

    scenes = []
    for i in range(n_scenes):
        seg = words[i * chunk:(i + 1) * chunk]
        if not seg:
            continue
        scenes.append(seg)

    # Global word frequency to reward distinctive words
    freq = Counter(w for seg in scenes for w in seg if w not in STOPWORDS)

    results = []
    for seg in scenes:
        scored = {}
        for w in seg:
            if w in STOPWORDS or len(w) < 3:
                continue
            score = freq[w]
            if w in VISUAL_HINTS:
                score += 5
            scored[w] = max(scored.get(w, 0), score)
        # Sort by score, take top 2 keywords
        top = sorted(scored, key=scored.get, reverse=True)[:2]
        text = " ".join(seg)
        results.append({"text": text, "keywords": top})
    return results
