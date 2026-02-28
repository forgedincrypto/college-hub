# College Hub

A local-first college application planner powered by Ollama. Track your grades, chat with an AI counselor, get college recommendations, and manage your applications — all in one place.

## Features

- **Grades & GPA** — Add courses manually or upload a PDF/DOCX transcript for AI-powered parsing. Calculates weighted and unweighted GPA with AP/IB/Honors/DE bonuses.
- **Transcript Upload** — Upload your transcript and Ollama extracts courses, grades, and course types into an editable review table for selective import.
- **AI Chat** — Talk to Sage, an AI college counselor that knows your academic profile and helps you explore options.
- **College Matches** — Generate personalized reach/match/safety recommendations based on your profile and chat history.
- **Application Tracker** — Track deadlines, essay status, letters of recommendation, and more for each school.
- **Student Profile** — Store your preferences for location, school size, budget, major interests, and extracurriculars.

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Install and start Ollama, then pull the model
ollama pull llama3.1:8b

# Run the app
python app.py
```

Open [http://localhost:5000](http://localhost:5000) in your browser.

## Requirements

- Python 3.10+
- [Ollama](https://ollama.com) with `llama3.1:8b`

## Tech Stack

- **Backend:** Flask, SQLite
- **AI:** Ollama (llama3.1:8b)
- **Transcript Parsing:** pdfplumber, python-docx
- **Frontend:** Vanilla HTML/CSS/JS with a dark theme
