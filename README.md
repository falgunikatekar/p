# Sentiment Pulse — Social Media Intelligence

A pastel, colorful full-stack web application for **automated social media sentiment analysis** with LLM-powered insights.

## Features

- **Automated Social Media Comment Collection** — Gathers comments from Instagram (mock data for demo; real API integration ready)
- **Advanced Emotion & Opinion Analysis** — LLM-based NLP for context, tone, and intent
- **Sentiment Classification Engine** — Categorizes into Positive, Negative, and Neutral
- **Insightful Analytics & Visualization** — Donut charts, bar charts, and detailed breakdowns
- **PR Risk Identification Module** — Detects emerging negative trends and reputation threats
- **Automated Report & Executive Summary** — Top 5 customer issues, most frequent positive feedback, trend analysis

## Quick Start

### Prerequisites

- Python 3.10+

### Run the Application

```bash
# Install dependencies
pip install -r requirements.txt

# Start the server (serves frontend + API on http://localhost:8000)
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Or run directly:

```bash
cd backend
python main.py
```

Then open **http://localhost:8000** in your browser.

### Usage

1. Click **Collect Comments** to load mock Instagram comments
2. Click **Run Analysis** to classify sentiment and emotions
3. Navigate through **Dashboard**, **Comments**, **Analytics**, **PR Risks**, and **Executive Report**

## Project Structure

```
GDG/
├── backend/
│   └── main.py          # FastAPI backend (API + static files)
├── frontend/
│   ├── index.html       # Main HTML
│   └── assets/
│       ├── style.css    # Pastel UI styles
│       └── app.js       # Frontend logic
├── requirements.txt
└── README.md
```

## Real Instagram Integration

For production, integrate the [Instagram Graph API](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api) with:

- `instagram_business_manage_comments` permission
- OAuth flow for access tokens

### Run with a share link (real collection)

1) Create a Meta app + token with required permissions  
2) Set environment variable on your machine (PowerShell):

```powershell
$env:META_ACCESS_TOKEN="YOUR_TOKEN"
```

3) Start the backend, open the website, paste the Instagram share link (e.g. `https://www.instagram.com/p/SHORTCODE/`), and **disable** “Use mock demo data”, then click **Collect Comments**.

This project resolves the share link using the `instagram_oembed` endpoint, then pulls comments via Graph API.

## LLM Integration

The backend supports OpenAI-compatible APIs for advanced sentiment analysis. Add your API key via environment variable:

```
OPENAI_API_KEY=sk-...
```

The demo uses pre-tagged mock sentiment; real LLM calls will be used when the key is configured.
