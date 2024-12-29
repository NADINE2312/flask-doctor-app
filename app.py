from flask import Flask, render_template, request, redirect, url_for, flash,jsonify
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
import mysql.connector
from config import Config
from werkzeug.utils import secure_filename
import os
import tensorflow as tf
import numpy as np
from flask_cors import CORS
from io import BytesIO
from PIL import Image
import tensorflow as tf
import numpy as np
from flask import Flask, request, jsonify





# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)
app.config['UPLOAD_FOLDER'] = 'uploads'
CORS(app)  # Pour autoriser les requêtes depuis le frontend

# Charger le modèle
model = tf.keras.models.load_model("AIMODEL.h5")

bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# MySQL connection function
def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host=app.config['MYSQL_HOST'],
            user=app.config['MYSQL_USER'],
            password=app.config['MYSQL_PASSWORD'],
            database=app.config['MYSQL_DB']
        )
        return connection
    except mysql.connector.Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None

# User class for Flask-Login
class User:
    def __init__(self, id, username, role, is_active=True):
        self.id = id
        self.username = username
        self.role = role
        self.is_active = is_active

    def get_id(self):
        return str(self.id)

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    connection = get_db_connection()
    if not connection:
        return None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        cursor.close()
        connection.close()
        if user:
            return User(user['id'], user['username'], user['role'])
    except Exception as e:
        print(f"Error loading user: {e}")
    return None

# Routes
@app.route("/predict", methods=["POST"])
def predict():
    try:
        # Get the file from the request
        file = request.files["file"]

        # Read the image file and preprocess it
        img = Image.open(file.stream)
        img = img.resize((50, 50))  # Resize to (50, 50)
        img_array = np.array(img) / 255.0  # Normalize
        img_array = np.expand_dims(img_array, axis=0)  # Add batch dimension

        # Predict using the model
        predictions = model.predict(img_array)
        
        # Get probabilities for each class
        print("Raw Model Output (Probabilities):", predictions)

        predicted_class = np.argmax(predictions[0])
        confidence = float(predictions[0][predicted_class])

        # Map class labels
        classes = {0: "absence de cancer", 1: "présence de cancer"}
        class_label = classes.get(predicted_class, "inconnu")

        # Response
        response = {
            "predicted_class": class_label,
            "confidence": confidence,
            "raw_predictions": predictions[0].tolist()  # Include raw predictions in response for debugging
        }

        print(response)  # Log response for debugging
        return jsonify(response)

    except Exception as e:
        return jsonify({"error": str(e)})





## Signup Route


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        connection = get_db_connection()
        if not connection:
            flash('Error connecting to the database.', 'danger')
            return render_template('signup.html')

        try:
            cursor = connection.cursor()

            # Add the user to the users table
            cursor.execute("""
                INSERT INTO users (username, password, role)
                VALUES (%s, %s, %s)
            """, (username, hashed_password, role))
            user_id = cursor.lastrowid  # Get the newly created user's ID

            # If the role is doctor, add additional details to the doctors table
            if role == 'doctor':
                specialization = request.form['specialization']
                availability = request.form['availability']
                cursor.execute("""
                    INSERT INTO doctors (id, name, specialization, availability)
                    VALUES (%s, %s, %s, %s)
                """, (user_id, username, specialization, availability))

            connection.commit()
            cursor.close()
            connection.close()

            flash('Sign-up successful! You can now log in.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            print(f"Error during sign-up: {e}")
            flash('An error occurred during sign-up.', 'danger')

    return render_template('signup.html')


## Login Route
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        connection = get_db_connection()
        if not connection:
            flash('Error connecting to the database.', 'danger')
            return render_template('login.html')

        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()
            cursor.close()
            connection.close()

            if user and bcrypt.check_password_hash(user['password'], password):
                login_user(User(user['id'], user['username'], user['role']))

                if user['role'] == 'doctor':
                    return redirect(url_for('doctor_dashboard'))
                elif user['role'] == 'patient':
                    return redirect(url_for('patient_dashboard'))
                else:
                    flash('Invalid role. Please contact support.', 'danger')

            flash('Invalid username or password!', 'danger')
        except Exception as e:
            print(f"Error during login: {e}")
            flash('Error occurred during login.', 'danger')

    return render_template('login.html')


## Patient Dashboard
@app.route('/patient-dashboard')
@login_required
def patient_dashboard():
    if current_user.role != 'patient':
        return redirect(url_for('login'))

    connection = get_db_connection()
    if not connection:
        flash('Error connecting to the database.', 'danger')
        return render_template('patient_dashboard.html', doctors=[], confirmed_appointments=[])

    try:
        cursor = connection.cursor(dictionary=True)

        # Fetch list of doctors
        cursor.execute("SELECT * FROM doctors")
        doctors = cursor.fetchall()

        # Fetch confirmed appointments for the current patient
        cursor.execute("""
            SELECT a.id, d.name AS doctor_name, a.date, a.time, a.status
            FROM appointments a
            JOIN doctors d ON a.doctor_id = d.id
            WHERE a.patient_id = %s AND a.status = 'confirmed'
        """, (current_user.id,))
        confirmed_appointments = cursor.fetchall()

        cursor.close()
        connection.close()
    except Exception as e:
        print(f"Error fetching data: {e}")
        doctors = []
        confirmed_appointments = []

    return render_template('patient_dashboard.html', doctors=doctors, confirmed_appointments=confirmed_appointments)


## Book Appointment
@app.route('/book-appointment', methods=['POST'])
@login_required
def book_appointment():
    if current_user.role != 'patient':
        return redirect(url_for('login'))

    doctor_id = request.form['doctor_id']
    date = request.form['date']
    time = request.form['time']

    connection = get_db_connection()
    if not connection:
        flash('Error connecting to the database.', 'danger')
        return redirect(url_for('patient_dashboard'))

    try:
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO appointments (patient_id, doctor_id, date, time, status) VALUES (%s, %s, %s, %s, %s)",
            (current_user.id, doctor_id, date, time, 'pending')
        )
        connection.commit()
        cursor.close()
        connection.close()

        flash('Appointment booked successfully!', 'success')
    except Exception as e:
        print(f"Error booking appointment: {e}")
        flash('Error booking appointment.', 'danger')

    return redirect(url_for('patient_dashboard'))

@app.route('/doctor-dashboard')
@login_required
def doctor_dashboard():
    if current_user.role != 'doctor':
        return redirect(url_for('login'))

    connection = get_db_connection()
    if not connection:
        flash('Error connecting to the database.', 'danger')
        return render_template('doctor_dashboard.html', appointments=[], doctor={})

    try:
        cursor = connection.cursor(dictionary=True)

        # Fetch appointments for the current doctor
        cursor.execute("""
            SELECT a.id, p.username AS patient_name, a.date, a.time, a.status
            FROM appointments a
            JOIN users p ON a.patient_id = p.id
            WHERE a.doctor_id = %s
        """, (current_user.id,))
        appointments = cursor.fetchall()

        # Fetch doctor's details
        cursor.execute("SELECT specialization, availability FROM doctors WHERE id = %s", (current_user.id,))
        doctor = cursor.fetchone()

        cursor.close()
        connection.close()
    except Exception as e:
        print(f"Error fetching data: {e}")
        appointments = []
        doctor = {}

    return render_template('doctor_dashboard.html', appointments=appointments, doctor=doctor)

## Confirm or Cancel Appointment
@app.route('/confirm-appointment', methods=['POST'])
@login_required
def confirm_appointment():
    if current_user.role != 'doctor':
        return redirect(url_for('login'))

    appointment_id = request.form['appointment_id']

    connection = get_db_connection()
    if not connection:
        flash('Error connecting to the database.', 'danger')
        return redirect(url_for('doctor_dashboard'))

    try:
        cursor = connection.cursor()
        cursor.execute("UPDATE appointments SET status = 'confirmed' WHERE id = %s", (appointment_id,))
        connection.commit()
        cursor.close()
        connection.close()

        flash('Appointment confirmed!', 'success')
    except Exception as e:
        print(f"Error confirming appointment: {e}")
        flash('Error confirming appointment.', 'danger')

    return redirect(url_for('doctor_dashboard'))

@app.route('/cancel-appointment', methods=['POST'])
@login_required
def cancel_appointment():
    if current_user.role != 'doctor':
        return redirect(url_for('login'))

    appointment_id = request.form['appointment_id']

    connection = get_db_connection()
    if not connection:
        flash('Error connecting to the database.', 'danger')
        return redirect(url_for('doctor_dashboard'))

    try:
        cursor = connection.cursor()
        cursor.execute("UPDATE appointments SET status = 'canceled' WHERE id = %s", (appointment_id,))
        connection.commit()
        cursor.close()
        connection.close()

        flash('Appointment canceled!', 'success')
    except Exception as e:
        print(f"Error canceling appointment: {e}")
        flash('Error canceling appointment.', 'danger')

    return redirect(url_for('doctor_dashboard'))

## Update Doctor Details
@app.route('/update-doctor-details', methods=['POST'])
@login_required
def update_doctor_details():
    if current_user.role != 'doctor':
        return redirect(url_for('login'))

    specialization = request.form['specialization']
    availability = request.form['availability']

    connection = get_db_connection()
    if not connection:
        flash('Error connecting to the database.', 'danger')
        return redirect(url_for('doctor_dashboard'))

    try:
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE doctors SET specialization = %s, availability = %s WHERE id = %s",
            (specialization, availability, current_user.id)
        )
        connection.commit()
        cursor.close()
        connection.close()

        flash('Details updated successfully!', 'success')
    except Exception as e:
        print(f"Error updating details: {e}")
        flash('Error updating details.', 'danger')

    return redirect(url_for('doctor_dashboard'))

## Logout
@app.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True)
