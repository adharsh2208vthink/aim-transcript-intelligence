"""
Analyst Agent — Local ML analysis on all non-skip videos (Tier 1 + Tier 2).

Per video:
  - spaCy NER: PERSON, ORG, and tech/tool entity extraction
  - VADER sentiment: pos/neg/neu scores + compound label
  - TF-IDF keywords: top 10 terms per transcript (for topic clustering)

All free, all local. Runs on the full corpus before any LLM is called.
Stores results back into episodic table.

Logs every analysis to episodic.agent_log.
"""

import json
import re
from datetime import datetime
from collections import Counter

import spacy
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from sklearn.feature_extraction.text import TfidfVectorizer
from tqdm import tqdm

from pipeline.database import get_connection

# Known tech/tool keywords for entity extraction (supplement spaCy)
TECH_KEYWORDS = {
    # LLMs & Models
    "gpt", "gpt-4", "gpt-3", "chatgpt", "claude", "gemini", "llama", "mistral",
    "phi", "falcon", "palm", "bert", "t5", "whisper", "stable diffusion", "midjourney",
    "dall-e", "sora", "gemma", "mixtral",
    # Frameworks & Tools
    "langchain", "llamaindex", "autogpt", "hugging face", "huggingface", "pytorch",
    "tensorflow", "keras", "sklearn", "scikit-learn", "spark", "hadoop", "kafka",
    "airflow", "mlflow", "wandb", "dvc", "ray", "triton", "onnx", "vllm",
    # Cloud & Infra
    "aws", "gcp", "azure", "sagemaker", "vertex ai", "bedrock", "openai", "anthropic",
    "cohere", "replicate", "together ai", "databricks", "snowflake", "pinecone",
    "weaviate", "chroma", "qdrant", "milvus",
    # Concepts
    "rag", "fine-tuning", "finetuning", "lora", "rlhf", "dpo", "ppo", "agent",
    "agentic", "mcp", "function calling", "vector database", "embeddings",
    "transformer", "diffusion", "gan", "vae", "llm", "slm", "vlm", "multimodal",
    # Indian AI
    "bhashini", "ai4bharat", "indic", "dhruva", "sarvam",
}

nlp = None
vader = None


def _load_models():
    global nlp, vader
    if nlp is None:
        try:
            nlp = spacy.load("en_core_web_sm")
        except OSError:
            import subprocess
            subprocess.run(["python", "-m", "spacy", "download", "en_core_web_sm"],
                           capture_output=True)
            nlp = spacy.load("en_core_web_sm")
    if vader is None:
        vader = SentimentIntensityAnalyzer()


def _log(con, video_id: str, action: str, detail: str):
    row = con.execute(
        "SELECT agent_log FROM episodic WHERE video_id = ?", [video_id]
    ).fetchone()
    log = json.loads(row[0]) if row and row[0] else []
    log.append({
        "agent": "analyst",
        "action": action,
        "detail": detail,
        "ts": datetime.utcnow().isoformat(),
    })
    con.execute(
        "UPDATE episodic SET agent_log = ? WHERE video_id = ?",
        [json.dumps(log), video_id],
    )


def _extract_entities(text: str) -> tuple[list, list, list]:
    """Returns (persons, orgs, tech_entities)."""
    doc = nlp(text[:100_000])  # spaCy max ~1M chars but keep it fast

    persons = [
        ent.text.strip() for ent in doc.ents
        if ent.label_ == "PERSON" and len(ent.text.strip()) > 2
    ]
    orgs = [
        ent.text.strip() for ent in doc.ents
        if ent.label_ == "ORG" and len(ent.text.strip()) > 2
    ]

    # Tech entities: spaCy PRODUCT + manual keyword scan
    tech = [
        ent.text.strip() for ent in doc.ents
        if ent.label_ in ("PRODUCT", "WORK_OF_ART") and len(ent.text.strip()) > 2
    ]
    text_lower = text.lower()
    for kw in TECH_KEYWORDS:
        if kw in text_lower:
            tech.append(kw)

    # Top N by frequency
    def top_n(items, n=15):
        return [item for item, _ in Counter(items).most_common(n)]

    return top_n(persons), top_n(orgs), top_n(list(set(tech)))


def _sentiment(text: str) -> tuple[float, float, float, str]:
    """Returns (pos, neg, neu, label)."""
    # VADER works best on sentences; chunk to avoid memory issues
    chunk_size = 5000
    chunks = [text[i:i+chunk_size] for i in range(0, min(len(text), 50_000), chunk_size)]
    scores = [vader.polarity_scores(c) for c in chunks]

    pos = sum(s["pos"] for s in scores) / len(scores)
    neg = sum(s["neg"] for s in scores) / len(scores)
    neu = sum(s["neu"] for s in scores) / len(scores)
    compound = sum(vader.polarity_scores(c)["compound"] for c in chunks) / len(chunks)

    if compound >= 0.05:
        label = "positive"
    elif compound <= -0.05:
        label = "negative"
    else:
        label = "neutral"

    return round(pos, 4), round(neg, 4), round(neu, 4), label


def analyze_video(video_id: str, text: str, con) -> dict:
    persons, orgs, tech = _extract_entities(text)
    pos, neg, neu, label = _sentiment(text)

    _log(con, video_id, "analyzed",
         f"persons={len(persons)} orgs={len(orgs)} tech={len(tech)} sentiment={label}")

    return {
        "entities_person": json.dumps(persons),
        "entities_org": json.dumps(orgs),
        "entities_tech": json.dumps(tech),
        "sentiment_pos": pos,
        "sentiment_neg": neg,
        "sentiment_neu": neu,
        "sentiment_label": label,
    }


def _build_tfidf_topics(video_ids: list, texts: list) -> dict:
    """
    Runs TF-IDF across the corpus, returns top-10 keywords per video.
    Returns {video_id: [kw1, kw2, ...]}
    """
    if not texts:
        return {}

    # Clean texts
    clean = [re.sub(r"[^a-zA-Z\s]", " ", t.lower()) for t in texts]

    vectorizer = TfidfVectorizer(
        max_features=5000,
        stop_words="english",
        ngram_range=(1, 2),
        min_df=2,
    )
    try:
        tfidf_matrix = vectorizer.fit_transform(clean)
    except ValueError:
        return {}

    feature_names = vectorizer.get_feature_names_out()
    result = {}
    for i, vid in enumerate(video_ids):
        row = tfidf_matrix[i].toarray()[0]
        top_indices = row.argsort()[-10:][::-1]
        keywords = [feature_names[j] for j in top_indices if row[j] > 0]
        result[vid] = keywords

    return result


def run(limit: int = None):
    """Analyze all TRIAGED (non-skip) videos."""
    _load_models()
    con = get_connection()

    query = """
        SELECT video_id, transcript
        FROM episodic
        WHERE status = 'TRIAGED'
          AND triage_tier != 'skip'
          AND transcript IS NOT NULL
    """
    if limit:
        query += f" LIMIT {limit}"
    rows = con.execute(query).fetchall()

    print(f"Analyst: analyzing {len(rows)} videos (NER + sentiment)...")

    video_ids = [r[0] for r in rows]
    texts = [r[1] for r in rows]

    # TF-IDF corpus-wide (batch)
    print("  Building TF-IDF topic keywords across corpus...")
    tfidf_topics = _build_tfidf_topics(video_ids, texts)

    stats = {"analyzed": 0, "errors": 0}

    for video_id, text in tqdm(zip(video_ids, texts), total=len(video_ids), desc="Analyst"):
        try:
            result = analyze_video(video_id, text, con)
            topics = json.dumps(tfidf_topics.get(video_id, []))

            con.execute("""
                UPDATE episodic SET
                    topics          = ?,
                    entities_person = ?,
                    entities_org    = ?,
                    entities_tech   = ?,
                    sentiment_pos   = ?,
                    sentiment_neg   = ?,
                    sentiment_neu   = ?,
                    sentiment_label = ?,
                    status          = 'ANALYZED',
                    updated_at      = CURRENT_TIMESTAMP
                WHERE video_id = ?
            """, [
                topics,
                result["entities_person"],
                result["entities_org"],
                result["entities_tech"],
                result["sentiment_pos"],
                result["sentiment_neg"],
                result["sentiment_neu"],
                result["sentiment_label"],
                video_id,
            ])
            stats["analyzed"] += 1
        except Exception as e:
            _log(con, video_id, "analysis_error", str(e)[:100])
            stats["errors"] += 1

    # Also mark skip videos as ANALYZED (no processing needed)
    con.execute("""
        UPDATE episodic SET status = 'ANALYZED', updated_at = CURRENT_TIMESTAMP
        WHERE status = 'TRIAGED' AND triage_tier = 'skip'
    """)

    con.close()
    print(f"\nAnalyst complete:")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    return stats


if __name__ == "__main__":
    run()
