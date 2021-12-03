import os
import smtplib
from dotenv import load_dotenv
from flask_wtf import FlaskForm
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user
from flask import Flask, render_template, url_for, redirect, send_from_directory
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import StringField, TextAreaField, PasswordField
from wtforms.validators import DataRequired, Email, Length
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from pdf2image import convert_from_path
from email.mime.text import MIMEText

app = Flask(__name__)
load_dotenv()

# Flask Server Config
app.secret_key = os.environ.get("FLASK_SECRET_KEY")
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.environ.get("UPLOAD_FOLDER")

# Database Config
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# E-Mail Config
admin_email = os.environ.get("ADMIN_EMAIL")
password = os.environ.get("ADMIN_EMAIL_PASSWORD")
receiver = os.environ.get("EMAIL_RECEIVER")


def send_mail(client_address, client_subject, client_message):

    client_message = str("From: " + client_address +
                         "<br />" + "<br />"
                         " Message:" +
                         "<br/>" + client_message)

    msg = MIMEText(client_message, "html")
    msg["From"] = admin_email
    msg["To"] = receiver
    msg["Subject"] = client_subject

    s = smtplib.SMTP_SSL(host="smtp.gmail.com", port=465)
    s.login(user=admin_email, password=password)
    s.sendmail(admin_email, receiver, msg.as_string())
    s.quit()


class User(UserMixin, db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(15), unique=True)
    email = db.Column(db.String(50), unique=True)
    password = db.Column(db.String(80))


class TimetableConfig(db.Model):
    __tablename__ = "persistentConfig"
    id = db.Column(db.Integer, primary_key=True)
    pdf = db.Column(db.String(256), unique=True)
    jpeg = db.Column(db.String(256), unique=True)
    webp = db.Column(db.String(256), unique=True)


class ContactForm(FlaskForm):
    client_address = StringField('eMail Address', validators=[
        DataRequired()], render_kw={"placeholder": "Email"})
    client_subject = StringField('Subject', validators=[DataRequired()], render_kw={
        "placeholder": "Subject"})
    client_message = TextAreaField(
        'Message', validators=[DataRequired()], render_kw={"placeholder": "Message"})


class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()], render_kw={
                           "placeholder": "Username"})
    password = PasswordField('Password', validators=[DataRequired()], render_kw={
                             "placeholder": "Password"})


class RegisterForm(FlaskForm):
    username = StringField('username', validators=[DataRequired(), Length(
        min=4, max=15)], render_kw={"placeholder": "Username"})
    email = StringField('email', validators=[DataRequired(), Email(
        message='Invalid email'), Length(max=50)], render_kw={"placeholder": "E-Mail Address"})
    password = StringField('password', validators=[DataRequired(), Length(
        min=8, max=80)], render_kw={"placeholder": "Password"})


class UploadFile(FlaskForm):
    file = FileField('Files', validators=[FileRequired(
    ), FileAllowed(['pdf'])])


# app.config['TIMETABLE_PDF'] = ""
# app.config['TIMETABLE_JPEG'] = ""
# app.config['TIMETABLE_WEBP'] = ""


# PUBLIC PAGES
@app.route("/")
@app.route("/index")
def index():
    return render_template("public/index.html")


@app.route("/timetable")
def timtable():
    t = TimetableConfig.query.filter_by(id=1).first()
    if t:
        timetable_pdf = t.pdf
        timetable_jpeg = t.jpeg
        timetable_webp = "uploads/" + t.webp

    return render_template("public/timetable.html", timetablePDF=timetable_pdf,
                           timetableJPEG=timetable_jpeg, timetableWebP=timetable_webp)


@app.route("/articles")
def articles():
    return render_template("public/articles.html")


@app.route("/audio")
def audio():
    return render_template("public/audio.html")


@app.route("/about")
def about():
    return render_template("public/about.html")


@app.route("/contact")
def contact():
    form = ContactForm()

    if form.validate_on_submit():

        client_address = form.client_address.data
        client_subject = client_address + " : " + form.client_subject.data
        client_message = form.client_message.data
        send_mail(client_address, client_subject, client_message)

        return redirect('/')

    return render_template("public/contact.html", form=form)


@app.route('/downloads/<path:filename>')
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)


# PRIVATE PAGES
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route("/admin/login", methods=('GET', 'POST'))
def login():
    form = LoginForm()

    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user:
            if check_password_hash(user.password, form.password.data):
                login_user(user, remember=False)
                return redirect(url_for('admin_portal'))

        return redirect(url_for('admin_portal'))

    return render_template("admin/admin-login.html", name="Login", form=form)


@app.route('/admin/register', methods=['GET', 'POST'])
@login_required
def admin_register():
    form = RegisterForm()

    if form.validate_on_submit():
        hashed_password = generate_password_hash(
            form.password.data, method='sha256')

        new_user = User(username=form.username.data,
                        email=form.email.data,
                        password=hashed_password)

        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for("admin_portal"))

    return render_template('admin/admin-register.html', form=form)


@app.route("/admin/portal")
@login_required
def admin_portal():
    form = UploadFile()

    return render_template("admin/admin-portal.html", name="Portal", form=form)


@app.route("/admin/articles")
@login_required
def admin_articles():
    return render_template("admin/admin-articles.html", name="Article Editor")


@app.route('/admin/uploads', methods=['GET', 'POST'])
@login_required
def admin_upload_file():

    form = UploadFile()

    if form.validate_on_submit():
        f = form.file.data
        upload_dir = app.config['UPLOAD_FOLDER']

        # Add uploaded File to Uploads Folder
        timetable_pdf = secure_filename(f.filename)
        f.save(os.path.join(upload_dir, timetable_pdf))

        # Save first PDF Page in JPEG & WebP formats
        timetable_webp = os.path.splitext(timetable_pdf)[0] + ".webp"
        timetable_jpeg = os.path.splitext(timetable_pdf)[0] + ".jpg"
        pdf_location = upload_dir + timetable_pdf

        images = convert_from_path(pdf_location, 500)
        images[0].save(os.path.join(upload_dir, timetable_webp))
        images[0].save(os.path.join(upload_dir, timetable_jpeg))

        # Save File Names to Database
        file_data = TimetableConfig(
            id=1,
            pdf=timetable_pdf,
            jpeg=timetable_jpeg,
            webp=timetable_webp
        )

        db.session.query(TimetableConfig).delete()
        db.session.commit()

        db.session.add(file_data)
        db.session.commit()

    return redirect(url_for('admin_portal'))


@app.route("/admin/logout")
@login_required
def logout():
    logout_user()
    return redirect('/')


# ERROR HANDLERS
@app.errorhandler(404)
def page_not_found(e):
    return render_template('error/404.html'), 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
