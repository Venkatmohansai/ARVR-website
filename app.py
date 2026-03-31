import os
import uuid
from flask import Flask, render_template, request, redirect, session, abort
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import cloudinary
import cloudinary.uploader

# -----------------------------
# LOAD ENV VARIABLES
# -----------------------------

load_dotenv()

app = Flask(__name__, template_folder="templates")

# -----------------------------
# SECRET KEY
# -----------------------------

app.secret_key = os.environ.get("SECRET_KEY", "fallback-secret-key")

# -----------------------------
# DATABASE CONFIG
# -----------------------------

DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:

    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace(
            "postgres://",
            "postgresql://"
        )

    if "sslmode=" not in DATABASE_URL:
        DATABASE_URL += "?sslmode=require"

else:
    DATABASE_URL = "sqlite:///local.db"

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# -----------------------------
# CLOUDINARY CONFIG
# -----------------------------

cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET"),
    secure=True
)

# -----------------------------
# ADMIN PIN
# -----------------------------

ADMIN_PIN = os.environ.get("ADMIN_PIN", "1234")

# -----------------------------
# UPLOAD SETTINGS
# -----------------------------

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "glb"}


def allowed_file(filename):
    return "." in filename and \
           filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# -----------------------------
# DATABASE MODEL
# -----------------------------

class Project(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(120), nullable=False)

    file_url = db.Column(db.String(500), nullable=False)

    public_id = db.Column(db.String(300), nullable=False)

    type = db.Column(db.String(50), nullable=False)


# -----------------------------
# CREATE TABLES
# -----------------------------

with app.app_context():
    db.create_all()


# -----------------------------
# DASHBOARD
# -----------------------------

@app.route("/")
def dashboard():

    projects = Project.query.order_by(Project.id.desc()).all()

    return render_template("dashboard.html", projects=projects)


# -----------------------------
# IMAGE AR VIEW
# -----------------------------

@app.route("/image-ar/<int:project_id>")
def image_ar(project_id):

    project = Project.query.get_or_404(project_id)

    if project.type != "image":
        abort(404)

    return render_template("image_ar.html", project=project)


# -----------------------------
# MODEL AR VIEW
# -----------------------------

@app.route("/model-ar/<int:project_id>")
def model_ar(project_id):

    project = Project.query.get_or_404(project_id)

    if project.type != "model":
        abort(404)

    return render_template("model_ar.html", project=project)


# -----------------------------
# CREATE PROJECT PAGE
# -----------------------------

@app.route("/create")
def create_project():

    if not session.get("create_auth"):

        return render_template(
            "pin_login.html",
            next_page="/create"
        )

    return render_template("create_project.html")


# -----------------------------
# VERIFY ADMIN PIN
# -----------------------------

@app.route("/verify-pin", methods=["POST"])
def verify_pin():

    pin = request.form.get("pin")

    next_page = request.form.get("next_page") or "/"

    if pin == ADMIN_PIN:

        session["create_auth"] = True
        session.permanent = True

        return redirect(next_page)

    return render_template(
        "pin_login.html",
        error="Wrong PIN",
        next_page=next_page
    )


# -----------------------------
# SAVE PROJECT (UPLOAD)
# -----------------------------

@app.route("/save", methods=["POST"])
def save():

    if not session.get("create_auth"):
        return redirect("/create")

    name = request.form.get("name")
    ptype = request.form.get("type")
    file = request.files.get("file")

    if not file or file.filename == "":
        return "No file selected", 400

    if not allowed_file(file.filename):
        return "File type not allowed", 400

    try:

        filename = secure_filename(file.filename)

        public_id = str(uuid.uuid4()) + "_" + filename

        # SAVE LOCALLY
        local_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(local_path)

        # UPLOAD TO CLOUDINARY
        upload_result = cloudinary.uploader.upload(
            local_path,
            public_id=public_id,
            resource_type="auto"
        )

        file_url = upload_result["secure_url"]

        project = Project(
            name=name,
            file_url=file_url,
            public_id=public_id,
            type=ptype
        )

        db.session.add(project)
        db.session.commit()

        return redirect("/")

    except Exception as e:

        db.session.rollback()

        return f"Upload error: {e}", 500


# -----------------------------
# DELETE PROJECT
# -----------------------------

@app.route("/delete/<int:id>")
def delete_project(id):

    if not session.get("create_auth"):
        return redirect("/create")

    project = Project.query.get_or_404(id)

    try:

        cloudinary.uploader.destroy(project.public_id)

        db.session.delete(project)
        db.session.commit()

    except Exception as e:

        db.session.rollback()

        return f"Delete failed: {e}", 500

    return redirect("/")


# -----------------------------
# LOGOUT
# -----------------------------

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/")


# -----------------------------
# WALL AR TOOL
# -----------------------------

@app.route("/wall-ar")
def wall_ar():

    return render_template("wall_ar.html")


# -----------------------------
# RUN SERVER
# -----------------------------

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
