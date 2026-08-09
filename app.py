import os
import secrets

from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.exceptions import HTTPException

import repository as repo
from repository import STATUSES, PRIORITIES

app = Flask(__name__)
# Only signs flash cookies. A per-process random key is fine: the worst case is
# that a restart drops a pending flash message.
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)

MAX_TITLE = 200
MAX_MESSAGE = 4000


@app.template_filter("pretty")
def pretty(value):
    return str(value).replace("_", " ")


@app.template_filter("when")
def when(dt):
    return dt.strftime("%b %d, %Y · %H:%M") if dt else ""


@app.template_filter("ref")
def ref(ticket_id):
    """Ticket numbers read as #0001 everywhere — queue, detail page, tab title."""
    return f"#{ticket_id:04d}"


@app.get("/healthz")
def healthz():
    """Deployment check: proves the app can actually reach Lakebase."""
    try:
        repo.status_counts()
        return {"status": "ok", "database": "connected"}, 200
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}, 503


@app.get("/")
def index():
    status = request.args.get("status") or None
    if status and status not in STATUSES:
        flash(f"Unknown status filter '{status}'. Showing all tickets.", "error")
        status = None

    tickets = repo.list_tickets(status)
    counts = repo.status_counts()
    return render_template(
        "index.html",
        tickets=tickets,
        counts=counts,
        total=sum(counts.values()),
        statuses=STATUSES,
        priorities=PRIORITIES,
        active=status,
    )


@app.post("/tickets")
def create_ticket():
    title = request.form.get("title", "").strip()
    created_by = request.form.get("created_by", "").strip()
    priority = request.form.get("priority", "medium")
    category = request.form.get("category", "").strip() or None
    first_message = request.form.get("first_message", "").strip() or None

    errors = []
    if not title:
        errors.append("Add a title so the ticket can be identified.")
    elif len(title) > MAX_TITLE:
        errors.append(f"Titles are limited to {MAX_TITLE} characters.")
    if not created_by:
        errors.append("Add your name or email so replies reach you.")
    if priority not in PRIORITIES:
        errors.append("Pick a priority from the list.")
    if first_message and len(first_message) > MAX_MESSAGE:
        errors.append(f"Messages are limited to {MAX_MESSAGE} characters.")

    if errors:
        for e in errors:
            flash(e, "error")
        return redirect(url_for("index"))

    ticket_id = repo.create_ticket(title, created_by, priority, category, first_message)
    flash(f"Ticket #{ticket_id} created.", "success")
    return redirect(url_for("view_ticket", ticket_id=ticket_id))


@app.get("/tickets/<int:ticket_id>")
def view_ticket(ticket_id):
    ticket = repo.get_ticket(ticket_id)
    if not ticket:
        flash(f"Ticket #{ticket_id} no longer exists.", "error")
        return redirect(url_for("index"))

    messages = repo.get_messages(ticket_id)
    for m in messages:
        # There is no role column: anyone who isn't the reporter is the desk.
        m["from_desk"] = m["author"] != ticket["created_by"]

    return render_template(
        "ticket.html",
        ticket=ticket,
        messages=messages,
        statuses=STATUSES,
    )


@app.post("/tickets/<int:ticket_id>/messages")
def add_message(ticket_id):
    text = request.form.get("message_text", "").strip()
    author = request.form.get("author", "").strip()

    errors = []
    if not text:
        errors.append("Write a message before sending.")
    elif len(text) > MAX_MESSAGE:
        errors.append(f"Messages are limited to {MAX_MESSAGE} characters.")
    if not author:
        errors.append("Add your name or email.")

    if errors:
        for e in errors:
            flash(e, "error")
        return redirect(url_for("view_ticket", ticket_id=ticket_id))

    if not repo.get_ticket(ticket_id):
        flash(f"Ticket #{ticket_id} no longer exists.", "error")
        return redirect(url_for("index"))

    repo.add_message(ticket_id, text, author)
    return redirect(url_for("view_ticket", ticket_id=ticket_id))


@app.post("/tickets/<int:ticket_id>/status")
def update_status(ticket_id):
    status = request.form.get("status", "")
    if status not in STATUSES:
        flash("Pick a status from the list.", "error")
        return redirect(url_for("view_ticket", ticket_id=ticket_id))

    if repo.update_status(ticket_id, status) == 0:
        flash(f"Ticket #{ticket_id} no longer exists.", "error")
        return redirect(url_for("index"))

    flash(f"Ticket #{ticket_id} moved to {pretty(status)}.", "success")
    return redirect(url_for("view_ticket", ticket_id=ticket_id))


@app.post("/tickets/<int:ticket_id>/delete")
def delete_ticket(ticket_id):
    confirm = request.form.get("confirm_id", "").strip()
    if confirm != str(ticket_id):
        flash(f"Type {ticket_id} in the confirmation box to delete this ticket.", "error")
        return redirect(url_for("view_ticket", ticket_id=ticket_id))

    if repo.delete_ticket(ticket_id) == 0:
        flash(f"Ticket #{ticket_id} no longer exists.", "error")
    else:
        flash(f"Ticket #{ticket_id} and its messages were deleted.", "success")
    return redirect(url_for("index"))


@app.errorhandler(HTTPException)
def http_error(exc):
    """404s, 405s and friends keep their real status instead of becoming 500s."""
    message = ("That page isn't part of Support Desk." if exc.code == 404
               else exc.description)
    return render_template("error.html", code=exc.code, message=message), exc.code


@app.errorhandler(Exception)
def unhandled(exc):
    app.logger.exception("Unhandled error")
    return render_template(
        "error.html",
        code="500",
        message="Something went wrong handling that request. If this is the "
                "first run after a deploy, the usual cause is the app's "
                "Lakebase environment variables or its Postgres grants.",
        detail=str(exc),
    ), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), debug=False)
