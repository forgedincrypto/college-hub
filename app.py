import sys, json
sys.stdout.reconfigure(encoding="utf-8")

import os
import tempfile

from flask import Flask, render_template, request, jsonify, Response, redirect, url_for
import db
import llm
import transcript

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10MB upload limit


@app.before_request
def ensure_db():
    db.init_db()


# ── Dashboard ────────────────────────────────────────────────────

@app.route("/")
def dashboard():
    stats = db.get_dashboard_stats()
    return render_template("dashboard.html", stats=stats)


# ── Grades ───────────────────────────────────────────────────────

@app.route("/grades")
def grades():
    courses = db.get_courses()
    gpa = db.calc_gpa(courses)
    profile = db.get_profile()
    return render_template("grades.html", courses=courses, gpa=gpa, profile=profile)


@app.route("/grades/add", methods=["POST"])
def grades_add():
    db.add_course(
        name=request.form["name"],
        grade=request.form["grade"],
        year=request.form["year"],
        course_type=request.form.get("course_type", "Regular"),
        credits=float(request.form.get("credits", 1.0)),
    )
    return redirect(url_for("grades"))


@app.route("/grades/delete/<int:course_id>", methods=["POST"])
def grades_delete(course_id):
    db.delete_course(course_id)
    return redirect(url_for("grades"))


@app.route("/grades/scores", methods=["POST"])
def grades_scores():
    sat = request.form.get("sat_score")
    act = request.form.get("act_score")
    updates = {}
    if sat:
        updates["sat_score"] = int(sat) if sat.strip() else None
    if act is not None:
        updates["act_score"] = int(act) if act.strip() else None
    if updates:
        db.update_profile(**updates)
    return redirect(url_for("grades"))


@app.route("/grades/upload", methods=["POST"])
def grades_upload():
    """Upload a transcript file, extract text, and parse courses via Ollama."""
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "No file selected"}), 400

    ext = f.filename.rsplit(".", 1)[-1].lower()
    if ext not in ("pdf", "docx"):
        return jsonify({"error": "Only PDF and DOCX files are supported"}), 400

    if not llm.check_available():
        return jsonify({"error": "Ollama is not running. Please start Ollama and try again."}), 503

    # Save to temp file, extract, parse, then clean up
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}")
    try:
        f.save(tmp)
        tmp.close()
        raw_text = transcript.extract_text(tmp.name, f.filename)
        if not raw_text.strip():
            return jsonify({"error": "Could not extract any text from the file"}), 400
        courses = transcript.parse_transcript(raw_text)
        if not courses:
            return jsonify({"error": "No courses found in the transcript"}), 400
        return jsonify({"courses": courses})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


@app.route("/grades/import", methods=["POST"])
def grades_import():
    """Bulk-import courses from the parsed transcript review."""
    data = request.get_json()
    courses = data.get("courses", [])
    if not courses:
        return jsonify({"error": "No courses to import"}), 400

    count = 0
    for c in courses:
        name = c.get("name", "").strip()
        grade = c.get("grade", "")
        year = c.get("year", "Junior")
        course_type = c.get("course_type", "Regular")
        try:
            credits = float(c.get("credits", 1.0))
        except (ValueError, TypeError):
            credits = 1.0
        if name and grade:
            db.add_course(name=name, grade=grade, year=year, course_type=course_type, credits=credits)
            count += 1

    return jsonify({"ok": True, "count": count})


# ── Profile ──────────────────────────────────────────────────────

@app.route("/profile")
def profile():
    p = db.get_profile()
    return render_template("profile.html", profile=p)


@app.route("/profile/save", methods=["POST"])
def profile_save():
    fields = [
        "name", "high_school", "grad_year", "major_interests",
        "extracurriculars", "location_pref", "size_pref", "budget",
        "setting_pref", "important_factors", "additional_notes",
    ]
    updates = {}
    for f in fields:
        val = request.form.get(f, "")
        if f == "grad_year":
            updates[f] = int(val) if val.strip() else None
        else:
            updates[f] = val
    db.update_profile(**updates)
    return redirect(url_for("profile"))


# ── Chat ─────────────────────────────────────────────────────────

@app.route("/chat")
def chat():
    convos = db.get_conversations()
    return render_template("chat.html", conversations=convos)


@app.route("/chat/new", methods=["POST"])
def chat_new():
    cid = db.create_conversation()
    return jsonify({"id": cid})


@app.route("/chat/<int:conversation_id>/messages")
def chat_messages(conversation_id):
    msgs = db.get_messages(conversation_id)
    return jsonify(msgs)


@app.route("/chat/<int:conversation_id>/send", methods=["POST"])
def chat_send(conversation_id):
    data = request.get_json()
    user_msg = data.get("message", "").strip()
    if not user_msg:
        return jsonify({"error": "Empty message"}), 400

    db.add_message(conversation_id, "user", user_msg)

    # Build context
    profile = db.get_profile()
    courses = db.get_courses()
    gpa = db.calc_gpa(courses)
    history = db.get_messages(conversation_id)

    def generate():
        full_response = []
        try:
            for chunk in llm.stream_chat(profile, courses, gpa, history):
                full_response.append(chunk)
                yield f"data: {json.dumps({'token': chunk})}\n\n"
        except Exception as e:
            error_msg = str(e)
            yield f"data: {json.dumps({'error': error_msg})}\n\n"
            full_response.append(f"\n\n[Error: {error_msg}]")

        # Save assistant message
        db.add_message(conversation_id, "assistant", "".join(full_response))

        # Auto-title on first exchange
        msgs = db.get_messages(conversation_id)
        if len(msgs) <= 2:
            title = user_msg[:50] + ("..." if len(user_msg) > 50 else "")
            db.update_conversation_title(conversation_id, title)
            yield f"data: {json.dumps({'title': title})}\n\n"

        yield "data: [DONE]\n\n"

    return Response(generate(), mimetype="text/event-stream")


@app.route("/chat/<int:conversation_id>/delete", methods=["POST"])
def chat_delete(conversation_id):
    db.delete_conversation(conversation_id)
    return jsonify({"ok": True})


# ── College Matches ──────────────────────────────────────────────

@app.route("/colleges")
def colleges():
    matches = db.get_college_matches()
    grouped = {"reach": [], "match": [], "safety": []}
    for m in matches:
        grouped.get(m["tier"], []).append(m)
    return render_template("colleges.html", grouped=grouped, total=len(matches))


@app.route("/colleges/generate", methods=["POST"])
def colleges_generate():
    profile = db.get_profile()
    courses = db.get_courses()
    gpa = db.calc_gpa(courses)

    # Gather chat insights
    convos = db.get_conversations()
    chat_insights = ""
    for c in convos[:3]:
        msgs = db.get_messages(c["id"])
        for m in msgs:
            if m["role"] == "assistant":
                chat_insights += m["content"] + "\n"
    chat_insights = chat_insights[:3000]

    try:
        matches = llm.generate_college_matches(profile, courses, gpa, chat_insights)
        db.save_college_matches(matches)
        return jsonify({"ok": True, "count": len(matches)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/colleges/clear", methods=["POST"])
def colleges_clear():
    db.delete_all_matches()
    return jsonify({"ok": True})


@app.route("/colleges/track", methods=["POST"])
def colleges_track():
    data = request.get_json()
    db.add_application(college_name=data["name"])
    return jsonify({"ok": True})


# ── Application Tracker ──────────────────────────────────────────

@app.route("/tracker")
def tracker():
    apps = db.get_applications()
    return render_template("tracker.html", applications=apps)


@app.route("/tracker/add", methods=["POST"])
def tracker_add():
    data = request.form
    db.add_application(
        college_name=data["college_name"],
        deadline=data.get("deadline") or None,
        app_type=data.get("app_type", "Regular Decision"),
    )
    return redirect(url_for("tracker"))


@app.route("/tracker/update/<int:app_id>", methods=["POST"])
def tracker_update(app_id):
    data = request.get_json()
    allowed = [
        "status", "deadline", "app_type", "essay_status",
        "lor_count", "transcript_sent", "test_scores_sent",
        "financial_aid", "notes", "college_name",
    ]
    updates = {k: v for k, v in data.items() if k in allowed}
    # Convert int fields
    for int_field in ["lor_count", "transcript_sent", "test_scores_sent", "financial_aid"]:
        if int_field in updates:
            updates[int_field] = int(updates[int_field])
    if updates:
        db.update_application(app_id, **updates)
    return jsonify({"ok": True})


@app.route("/tracker/delete/<int:app_id>", methods=["POST"])
def tracker_delete(app_id):
    db.delete_application(app_id)
    return jsonify({"ok": True})


# ── LLM status ───────────────────────────────────────────────────

@app.route("/api/llm-status")
def llm_status():
    available = llm.check_available()
    return jsonify({"available": available})


if __name__ == "__main__":
    db.init_db()
    print("College Application Hub running at http://localhost:5000")
    app.run(debug=True, port=5000)
