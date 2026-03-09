"""
Social Media Sentiment Analysis - Backend API
Features: Comment collection, LLM sentiment analysis, PR risk detection, reports
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from typing import Optional
import os
import json
import random
import re
from urllib.parse import quote
from datetime import datetime, timedelta

app = FastAPI(title="Sentiment Pulse API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage (replace with DB in production)
comments_db = []
analysis_cache = {}
collection_meta = {"source": None, "post_url": None}

# Pastel color palette for sentiment
SENTIMENT_COLORS = {
    "positive": "#B8E6B8",  # Soft mint
    "negative": "#FFB8B8",  # Soft coral
    "neutral": "#E6D5F5",   # Soft lavender
}


class CollectRequest(BaseModel):
    username: Optional[str] = None
    post_url: Optional[str] = None
    use_mock: bool = True  # Use mock data when no API key


class AnalyzeRequest(BaseModel):
    comment_ids: Optional[list] = None  # Analyze specific or all


@app.get("/api/health")
def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.post("/api/collect")
async def collect_comments(req: CollectRequest):
    """Collect comments from Instagram (mock or real API)"""
    analysis_cache.clear()
    if req.use_mock:
        mock_comments = _generate_mock_comments()
        comments_db.clear()
        comments_db.extend(mock_comments)
        collection_meta["source"] = "mock"
        collection_meta["post_url"] = None
        return {
            "success": True,
            "count": len(mock_comments),
            "source": "mock",
            "message": "Collected mock Instagram comments for demo"
        }
    if not req.post_url:
        raise HTTPException(400, "Missing post_url. Paste an Instagram post link.")
    access_token = os.getenv("META_ACCESS_TOKEN") or os.getenv("IG_ACCESS_TOKEN")
    if not access_token:
        raise HTTPException(
            400,
            "Missing META_ACCESS_TOKEN (or IG_ACCESS_TOKEN) on backend. "
            "Set it, then retry with 'Use mock demo data' disabled."
        )
    collected = await _collect_instagram_comments(post_url=req.post_url, access_token=access_token)
    comments_db.clear()
    comments_db.extend(collected)
    collection_meta["source"] = "instagram"
    collection_meta["post_url"] = req.post_url
    return {
        "success": True,
        "count": len(collected),
        "source": "instagram",
        "message": "Collected Instagram comments via Graph API"
    }


def _extract_instagram_shortcode(post_url: str) -> str:
    """
    Supported:
    - https://www.instagram.com/p/SHORTCODE/
    - https://www.instagram.com/reel/SHORTCODE/
    - https://www.instagram.com/tv/SHORTCODE/
    """
    m = re.search(r"instagram\.com/(p|reel|tv)/([^/?#]+)/?", post_url)
    if not m:
        raise ValueError("Unsupported Instagram URL format. Use a post/reel/tv share link.")
    return m.group(2)


async def _collect_instagram_comments(post_url: str, access_token: str) -> list:
    """
    Official approach (Graph API):
    1) Resolve share URL to media_id via instagram_oembed
    2) Fetch comments for that media_id

    Notes:
    - This requires a valid Meta access token & permissions.
    - If your app/token lacks permissions, the API will return an error; we surface it cleanly.
    """
    import httpx

    # Validate URL early (also extracts shortcode for nicer errors/logging)
    _ = _extract_instagram_shortcode(post_url)

    api_version = os.getenv("META_API_VERSION", "v20.0")
    async with httpx.AsyncClient(timeout=30.0) as client:
        oembed_url = f"https://graph.facebook.com/{api_version}/instagram_oembed?url={quote(post_url, safe='')}&access_token={quote(access_token, safe='')}"
        o = await client.get(oembed_url)
        odata = o.json()
        if o.status_code >= 400:
            raise HTTPException(400, f"Instagram oEmbed error: {odata.get('error', {}).get('message', o.text)}")
        media_id = odata.get("media_id")
        if not media_id:
            raise HTTPException(400, "Could not resolve media_id from share link. Check permissions/token.")

        comments_url = (
            f"https://graph.facebook.com/{api_version}/{media_id}/comments"
            f"?fields=id,text,username,timestamp,like_count,replies{{id,text,username,timestamp,like_count}}"
            f"&limit=50&access_token={quote(access_token, safe='')}"
        )
        c = await client.get(comments_url)
        cdata = c.json()
        if c.status_code >= 400:
            raise HTTPException(400, f"Instagram comments error: {cdata.get('error', {}).get('message', c.text)}")

    out = []
    for item in (cdata.get("data") or []):
        text = item.get("text") or ""
        cleaned = _preprocess_text(text)
        category = _classify_category(text)
        out.append({
            "id": item.get("id") or f"ig_{len(out)+1}",
            "username": item.get("username") or "@unknown",
            "text": text,
            "cleaned_text": cleaned,
            "category": category,
            "timestamp": item.get("timestamp") or datetime.now().isoformat(),
            "likes": item.get("like_count") or 0,
            "replies": len((item.get("replies") or {}).get("data") or []),
            # Will be set during /api/analyze (heuristic or LLM)
            "sentiment": "neutral",
            "emotion": "neutrality",
        })
    return out


def _generate_mock_comments():
    """Generate realistic mock Instagram comments for demo"""
    templates = [
        ("Love this product! Best purchase ever 💕", "positive"),
        ("Terrible experience. Never ordering again.", "negative"),
        ("It's okay, nothing special", "neutral"),
        ("Amazing quality and fast shipping!", "positive"),
        ("Customer service was unhelpful and rude", "negative"),
        ("Looks nice but took forever to arrive", "neutral"),
        ("Absolutely recommend to everyone!", "positive"),
        ("Broken on arrival. Very disappointed.", "negative"),
        ("Decent product for the price", "neutral"),
        ("Exceeded my expectations! 🌟", "positive"),
        ("Worst company I've ever dealt with", "negative"),
        ("It works as described", "neutral"),
        ("So happy with my order! Will buy again", "positive"),
        ("Refund process is a nightmare", "negative"),
        ("Average experience overall", "neutral"),
        ("The packaging was beautiful! Great attention to detail", "positive"),
        ("Product doesn't match the photos at all", "negative"),
        ("Could be better but not bad", "neutral"),
        ("Fast delivery and perfect condition!", "positive"),
        ("Still waiting after 3 weeks. No updates.", "negative"),
    ]
    users = ["@sarah_m", "@techguy", "@lifestyle_jane", "@mike_reviews", "@emma_style",
             "@david_k", "@anna_loves", "@chris_travels", "@jess_fashion", "@alex_tech"]
    
    comments = []
    target_count = 721  # Generate 721 comments as expected
    
    for i in range(target_count):
        # Cycle through templates and randomize
        text, sentiment = random.choice(templates)
        cleaned = _preprocess_text(text)
        category = _classify_category(text)
        comments.append({
            "id": f"cm_{i+1}",
            "username": random.choice(users),
            "text": text,
            "cleaned_text": cleaned,
            "category": category,
            "timestamp": (datetime.now() - timedelta(hours=random.randint(0, 168))).isoformat(),
            "likes": random.randint(0, 150),
            "replies": random.randint(0, 20),
            "sentiment": sentiment,
            "emotion": _get_emotion_for(sentiment),
        })
    return comments


def _get_emotion_for(sentiment):
    emotions = {
        "positive": ["joy", "gratitude", "excitement", "satisfaction", "love"],
        "negative": ["anger", "disappointment", "frustration", "sadness", "annoyance"],
        "neutral": ["indifference", "curiosity", "uncertainty", "neutrality", "mixed"],
    }
    return random.choice(emotions[sentiment])


def _preprocess_text(text: str) -> str:
    """Preprocessing: tokenization, stopword removal (simplified - spaCy/NLTK in prod)"""
    import re
    text = text.lower().strip()
    text = re.sub(r'[^\w\s]', ' ', text)  # Remove special chars
    text = re.sub(r'\s+', ' ', text)  # Normalize whitespace
    stopwords = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'it', 'its', 'to', 'of', 'and', 'or', 'but', 'in', 'on', 'at', 'for', 'with', 'this', 'that', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can'}
    words = [w for w in text.split() if w not in stopwords and len(w) > 1]
    return ' '.join(words)


def _classify_category(text: str) -> str:
    """Categorize: Pricing | Delivery | Complaints | Enquiries | Other"""
    t = text.lower()
    if any(w in t for w in ['price', 'cost', 'expensive', 'cheap', 'refund', 'money', 'worth']):
        return "Pricing"
    if any(w in t for w in ['shipping', 'delivery', 'arrive', 'waiting', 'order', 'dispatch']):
        return "Delivery"
    if any(w in t for w in ['terrible', 'worst', 'broken', 'rude', 'unhelpful', 'disappointed', 'nightmare']):
        return "Complaints"
    if any(w in t for w in ['how', 'when', 'where', 'what', '?', 'track', 'status']):
        return "Enquiries"
    return "Other"


def _infer_sentiment(text: str) -> str:
    """Lightweight sentiment classifier (fallback when no LLM)."""
    t = (text or "").lower()
    positive = [
        "love", "amazing", "great", "best", "excellent", "recommend", "happy", "perfect",
        "awesome", "fast", "beautiful", "exceeded", "good", "satisfied"
    ]
    negative = [
        "terrible", "worst", "broken", "rude", "unhelpful", "disappointed", "nightmare",
        "bad", "awful", "refund", "late", "waiting", "never", "doesn't", "dont", "no updates"
    ]
    score = 0
    for w in positive:
        if w in t:
            score += 1
    for w in negative:
        if w in t:
            score -= 1
    if score > 0:
        return "positive"
    if score < 0:
        return "negative"
    return "neutral"


def _infer_emotion(text: str, sentiment: str) -> str:
    """Simple emotion mapping (fallback)."""
    t = (text or "").lower()
    if sentiment == "positive":
        if any(w in t for w in ["love", "so happy", "excited", "🌟", "💕"]):
            return "joy"
        return "satisfaction"
    if sentiment == "negative":
        if any(w in t for w in ["angry", "rude", "worst"]):
            return "anger"
        if any(w in t for w in ["disappointed", "broken", "terrible"]):
            return "disappointment"
        return "frustration"
    return "neutrality"


@app.post("/api/analyze")
async def analyze_sentiment(req: AnalyzeRequest):
    """Run LLM-based sentiment & emotion analysis on comments"""
    if not comments_db:
        return {"error": "No comments. Run /api/collect first."}
    
    # In production: call OpenAI/Groq/Claude for real NLP.
    # Fallback here: heuristic sentiment/emotion/category + preprocessing.
    breakdown = {"positive": 0, "negative": 0, "neutral": 0}
    emotions = {}
    for c in comments_db:
        text = c.get("text", "")
        c["cleaned_text"] = c.get("cleaned_text") or _preprocess_text(text)
        c["category"] = c.get("category") or _classify_category(text)

        sentiment = c.get("sentiment")
        if sentiment not in ("positive", "negative", "neutral") or collection_meta.get("source") == "instagram":
            sentiment = _infer_sentiment(text)
            c["sentiment"] = sentiment
        e = c.get("emotion")
        if not e or collection_meta.get("source") == "instagram":
            e = _infer_emotion(text, sentiment)
            c["emotion"] = e

        breakdown[sentiment] += 1
        emotions[e] = emotions.get(e, 0) + 1
    
    analysis_cache["breakdown"] = breakdown
    analysis_cache["emotions"] = emotions
    analysis_cache["comments"] = comments_db
    analysis_cache["source"] = collection_meta.get("source")
    
    return {
        "success": True,
        "breakdown": breakdown,
        "emotions": emotions,
        "total": len(comments_db),
    }


@app.get("/api/comments")
def get_comments():
    return {"comments": comments_db}


@app.get("/api/analytics")
def get_analytics():
    """Analytics & visualization data"""
    if not analysis_cache:
        return {"error": "Run collect and analyze first."}
    
    breakdown = analysis_cache.get("breakdown", {})
    emotions = analysis_cache.get("emotions", {})
    total = sum(breakdown.values()) or 1
    
    return {
        "sentiment_distribution": [
            {"label": "Positive", "value": breakdown.get("positive", 0), "color": SENTIMENT_COLORS["positive"]},
            {"label": "Negative", "value": breakdown.get("negative", 0), "color": SENTIMENT_COLORS["negative"]},
            {"label": "Neutral", "value": breakdown.get("neutral", 0), "color": SENTIMENT_COLORS["neutral"]},
        ],
        "emotion_breakdown": [{"label": k, "value": v} for k, v in sorted(emotions.items(), key=lambda x: -x[1])],
        "percentages": {
            "positive": round(100 * breakdown.get("positive", 0) / total, 1),
            "negative": round(100 * breakdown.get("negative", 0) / total, 1),
            "neutral": round(100 * breakdown.get("neutral", 0) / total, 1),
        },
        "total": total,
    }


@app.get("/api/pr-risks")
def get_pr_risks():
    """PR Risk Identification - detect negative trends"""
    if not comments_db:
        return {"risks": [], "message": "No data yet"}
    
    neg_comments = [c for c in comments_db if c["sentiment"] == "negative"]
    risks = []
    
    # Detect themes in negative comments
    themes = {}
    for c in neg_comments:
        text = c["text"].lower()
        if "shipping" in text or "delivery" in text or "arrive" in text:
            themes["Delivery Issues"] = themes.get("Delivery Issues", 0) + 1
        if "customer service" in text or "rude" in text or "unhelpful" in text:
            themes["Customer Service"] = themes.get("Customer Service", 0) + 1
        if "quality" in text or "broken" in text or "match" in text:
            themes["Product Quality"] = themes.get("Product Quality", 0) + 1
        if "refund" in text or "money" in text:
            themes["Refund/Billing"] = themes.get("Refund/Billing", 0) + 1
    
    for theme, count in sorted(themes.items(), key=lambda x: -x[1]):
        severity = "high" if count >= 3 else "medium" if count >= 2 else "low"
        risks.append({
            "theme": theme,
            "count": count,
            "severity": severity,
            "recommendation": f"Address {theme} - {count} negative mentions"
        })
    
    return {
        "risks": risks,
        "negative_count": len(neg_comments),
        "risk_level": "elevated" if len(neg_comments) >= 5 else "moderate" if neg_comments else "low",
    }


@app.get("/api/preprocessing")
def get_preprocessing():
    """Data Ingestion pipeline: Raw → Preprocessing → Cleaned Text → NLP Engine"""
    if not comments_db:
        return {"error": "Run collect first."}
    samples = []
    for c in comments_db[:10]:
        samples.append({
            "raw": c["text"],
            "cleaned": c.get("cleaned_text", _preprocess_text(c["text"])),
            "username": c["username"],
        })
    return {"samples": samples, "total": len(comments_db)}


@app.get("/api/categorization")
def get_categorization():
    """Categorization: Pricing, Delivery, Complaints, Enquiries, Other"""
    if not comments_db:
        return {"error": "Run collect first."}
    by_category = {"Pricing": [], "Delivery": [], "Complaints": [], "Enquiries": [], "Other": []}
    for c in comments_db:
        cat = c.get("category", _classify_category(c["text"]))
        by_category.setdefault(cat, []).append(c)
    counts = {k: len(v) for k, v in by_category.items()}
    return {"by_category": by_category, "counts": counts}


@app.get("/api/expert-opinions")
def get_expert_opinions():
    """LLM-style expert opinions (mock - use Groq/OpenAI in prod)"""
    if not comments_db:
        return {"error": "Run collect and analyze first."}
    neg = [c for c in comments_db if c["sentiment"] == "negative"]
    pos = [c for c in comments_db if c["sentiment"] == "positive"]
    opinions = [
        "Based on sentiment analysis, delivery and customer service themes require immediate attention. Consider proactive outreach to affected customers.",
        "Positive feedback highlights product quality and fast shipping. Maintain these strengths while addressing negative themes.",
        "Risk level suggests implementing a feedback loop for high-engagement negative comments to prevent reputation escalation.",
    ]
    if neg:
        opinions.append(f"Top concern: {len(neg)} negative comments. Prioritize refund and delivery process improvements.")
    return {"opinions": opinions}


@app.get("/api/positive-highlights")
def get_positive_highlights():
    """Customer-facing: Positive highlights & feedback summary"""
    if not comments_db:
        return {"error": "Run collect first."}
    pos = [c for c in comments_db if c["sentiment"] == "positive"]
    highlights = [{"text": c["text"], "username": c["username"], "likes": c.get("likes", 0)} for c in pos[:8]]
    themes = {}
    for c in pos:
        t = c["text"].lower()
        if "quality" in t or "great" in t: themes["Quality"] = themes.get("Quality", 0) + 1
        if "shipping" in t or "delivery" in t: themes["Fast Shipping"] = themes.get("Fast Shipping", 0) + 1
        if "recommend" in t or "love" in t: themes["Recommendations"] = themes.get("Recommendations", 0) + 1
    return {"highlights": highlights, "feedback_themes": themes}


@app.get("/api/report")
def get_executive_report():
    """Automated Report & Executive Summary"""
    if not comments_db:
        return {"error": "Run collect and analyze first."}
    
    neg = [c for c in comments_db if c["sentiment"] == "negative"]
    pos = [c for c in comments_db if c["sentiment"] == "positive"]
    
    # Top 5 key customer issues (from negative)
    issues = []
    seen = set()
    for c in sorted(neg, key=lambda x: -x.get("likes", 0)):
        key = c["text"][:50]
        if key not in seen and len(issues) < 5:
            seen.add(key)
            issues.append({"text": c["text"], "username": c["username"], "likes": c.get("likes", 0)})
    
    # Most frequent positive feedback themes
    pos_themes = {}
    for c in pos:
        text = c["text"].lower()
        if "quality" in text or "great" in text or "amazing" in text:
            pos_themes["Product Quality"] = pos_themes.get("Product Quality", 0) + 1
        if "shipping" in text or "delivery" in text or "fast" in text:
            pos_themes["Fast Shipping"] = pos_themes.get("Fast Shipping", 0) + 1
        if "recommend" in text or "love" in text or "happy" in text:
            pos_themes["Customer Satisfaction"] = pos_themes.get("Customer Satisfaction", 0) + 1
    
    top_positive = [{"theme": k, "count": v} for k, v in sorted(pos_themes.items(), key=lambda x: -x[1])[:5]]
    
    return {
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "total_comments": len(comments_db),
            "positive_pct": round(100 * len(pos) / len(comments_db), 1),
            "negative_pct": round(100 * len(neg) / len(comments_db), 1),
            "neutral_pct": round(100 * (len(comments_db) - len(pos) - len(neg)) / len(comments_db), 1),
        },
        "top_5_issues": issues,
        "most_frequent_positive_feedback": top_positive,
        "trend_analysis": {
            "overall_sentiment": "positive" if len(pos) > len(neg) else "negative" if len(neg) > len(pos) else "neutral",
            "recommendation": "Continue monitoring. Consider addressing delivery and customer service themes." if neg else "Strong positive sentiment. Maintain quality and service.",
        },
    }


@app.get("/api/report/pdf")
def download_pdf_report():
    """Generate and download PDF report (FPDF)"""
    if not comments_db:
        raise HTTPException(400, "Run collect and analyze first.")
    try:
        from fpdf import FPDF
    except ImportError:
        raise HTTPException(500, "fpdf2 not installed. Run: pip install fpdf2")
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Sentiment Pulse - Executive Report", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 10, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True)
    pdf.ln(5)
    neg = [c for c in comments_db if c["sentiment"] == "negative"]
    pos = [c for c in comments_db if c["sentiment"] == "positive"]
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Summary", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Total: {len(comments_db)} | Positive: {len(pos)} | Negative: {len(neg)}", ln=True)
    pdf.ln(5)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Top 5 Issues", ln=True)
    pdf.set_font("Helvetica", "", 9)
    for i, c in enumerate(sorted(neg, key=lambda x: -x.get("likes", 0))[:5], 1):
        pdf.multi_cell(0, 6, f"{i}. {c['text'][:80]}...")
    pdf.ln(5)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Positive Highlights", ln=True)
    pdf.set_font("Helvetica", "", 9)
    for c in pos[:5]:
        pdf.multi_cell(0, 6, f"- {c['text'][:80]}...")
    pdf_output = bytes(pdf.output())
    return Response(content=pdf_output, media_type="application/pdf", headers={
        "Content-Disposition": "attachment; filename=sentiment_report.pdf"
    })


# Serve frontend
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_path):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_path, "assets")), name="assets")


@app.get("/")
def serve_index():
    index_path = os.path.join(frontend_path, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Frontend not found. Run from project root."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
