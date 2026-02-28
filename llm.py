import json
import ollama

MODEL = "llama3.1:8b"

SAGE_SYSTEM = """You are Sage, a warm, knowledgeable college counselor helping a high school student explore their college options. Your approach:

- Ask ONE thoughtful question at a time, then wait for the student's response
- Build on previous answers to dig deeper into interests and goals
- Reference specific things the student has shared (grades, activities, preferences)
- Be encouraging but honest about competitiveness
- Share specific knowledge about colleges, programs, and admissions
- Help the student discover what matters most to them
- Keep responses conversational and not too long (2-4 paragraphs max)

You have access to the student's academic profile and should reference it naturally."""


def check_available():
    try:
        ollama.list()
        return True
    except Exception:
        return False


def _build_student_context(profile, courses, gpa):
    parts = ["## Student Profile"]
    if profile.get("name"):
        parts.append(f"Name: {profile['name']}")
    if profile.get("high_school"):
        parts.append(f"School: {profile['high_school']}")
    if profile.get("grad_year"):
        parts.append(f"Graduation Year: {profile['grad_year']}")

    parts.append(f"\nGPA: {gpa['unweighted']:.2f} unweighted / {gpa['weighted']:.2f} weighted")
    if profile.get("sat_score"):
        parts.append(f"SAT: {profile['sat_score']}")
    if profile.get("act_score"):
        parts.append(f"ACT: {profile['act_score']}")

    if courses:
        parts.append(f"\nCourses ({len(courses)} total):")
        for c in courses:
            parts.append(f"  - {c['name']} ({c['course_type']}): {c['grade']} [{c['year']}]")

    if profile.get("major_interests"):
        parts.append(f"\nMajor Interests: {profile['major_interests']}")
    if profile.get("extracurriculars"):
        parts.append(f"Extracurriculars: {profile['extracurriculars']}")
    if profile.get("location_pref"):
        parts.append(f"Location Preference: {profile['location_pref']}")
    if profile.get("size_pref"):
        parts.append(f"Size Preference: {profile['size_pref']}")
    if profile.get("budget"):
        parts.append(f"Budget: {profile['budget']}")
    if profile.get("important_factors"):
        parts.append(f"Important Factors: {profile['important_factors']}")

    return "\n".join(parts)


def stream_chat(profile, courses, gpa, history):
    """Yield tokens from Ollama streaming response."""
    context = _build_student_context(profile, courses, gpa)

    messages = [
        {"role": "system", "content": SAGE_SYSTEM + "\n\n" + context},
    ]
    for msg in history:
        if msg["role"] in ("user", "assistant"):
            messages.append({"role": msg["role"], "content": msg["content"]})

    stream = ollama.chat(model=MODEL, messages=messages, stream=True)
    for chunk in stream:
        token = chunk.get("message", {}).get("content", "")
        if token:
            yield token


MATCH_SYSTEM = """You are a college admissions expert. Based on the student profile below, generate a list of 12-15 college recommendations divided into three tiers:

- **Reach** (4-5 schools): Highly competitive for this student but possible
- **Match** (4-5 schools): Good alignment with student's academic profile
- **Safety** (3-5 schools): Strong likelihood of admission

For each school, provide:
- name: Full college name
- tier: "reach", "match", or "safety"
- reasoning: 1-2 sentences explaining why this school fits
- fit_score: 1-100 score for overall fit
- location: City, State
- size: "Small", "Medium", or "Large"

IMPORTANT: Respond with ONLY valid JSON — an array of objects. No markdown, no explanation outside the JSON."""


def generate_college_matches(profile, courses, gpa, chat_insights=""):
    """Generate college recommendations using Ollama."""
    context = _build_student_context(profile, courses, gpa)
    if chat_insights:
        context += f"\n\n## Insights from Counselor Interview\n{chat_insights}"

    response = ollama.chat(
        model=MODEL,
        messages=[
            {"role": "system", "content": MATCH_SYSTEM},
            {"role": "user", "content": context + "\n\nGenerate college recommendations as JSON:"},
        ],
    )

    text = response["message"]["content"].strip()

    # Try to extract JSON from response
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])
    if text.startswith("["):
        matches = json.loads(text)
    else:
        # Find the JSON array in the response
        start = text.index("[")
        end = text.rindex("]") + 1
        matches = json.loads(text[start:end])

    # Validate and normalize
    valid = []
    for m in matches:
        if "name" in m and "tier" in m:
            valid.append({
                "name": m["name"],
                "tier": m["tier"] if m["tier"] in ("reach", "match", "safety") else "match",
                "reasoning": m.get("reasoning", ""),
                "fit_score": int(m.get("fit_score", 50)),
                "location": m.get("location", ""),
                "size": m.get("size", ""),
            })
    return valid
