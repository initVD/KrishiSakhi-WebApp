from flask import Flask, render_template, request, redirect, url_for, session
import tensorflow as tf
import numpy as np
from PIL import Image
import io
import os
import sqlite3
import uuid
import google.generativeai as genai

app = Flask(__name__)
app.secret_key = 'AIzaSyAYq_YEbJmnN4lzMfG77TI4Zes-ZjYlAdQ'

# --- Configure the Gemini API ---
# IMPORTANT: PASTE YOUR API KEY HERE
GEMINI_API_KEY = 'AIzaSyAYq_YEbJmnN4lzMfG77TI4Zes-ZjYlAdQ'
genai.configure(api_key=GEMINI_API_KEY)
llm_model = genai.GenerativeModel('gemini-1.5-flash-latest')

# --- Folder to store uploaded images ---
UPLOAD_FOLDER = 'static/uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# --- Database Setup ---
def init_db():
    conn = sqlite3.connect('farmers.db')
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS farmers (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, phone TEXT UNIQUE NOT NULL,
        location TEXT NOT NULL, crop TEXT NOT NULL )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT, image_filename TEXT NOT NULL,
        predicted_label TEXT NOT NULL, is_correct INTEGER NOT NULL, actual_label TEXT )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- Get the absolute path to the script's directory ---
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
MODEL_PATH = os.path.join(BASE_DIR, 'finetuned_model.tflite')
LABELS_PATH = os.path.join(BASE_DIR, 'labels.txt')

# --- MODEL AND LABELS LOADING ---
interpreter = None
labels = []
input_details = None
output_details = None
try:
    interpreter = tf.lite.Interpreter(model_path=MODEL_PATH)
    interpreter.allocate_tensors()
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()
    with open(LABELS_PATH, 'r') as f:
        labels = f.read().splitlines()
    print(f"Successfully loaded {len(labels)} labels.")
except Exception as e:
    print(f"CRITICAL: Error loading model or labels: {e}")

def process_image(image_bytes):
    img = Image.open(io.BytesIO(image_bytes)).convert('RGB')
    img = img.resize((224, 224))
    img_array = np.array(img)
    img_array = img_array / 255.0
    img_array = np.expand_dims(img_array, axis=0).astype(np.float32)
    return img_array

# --- Web Page Routes ---

@app.route('/')
def home():
    if 'phone' in session:
        return render_template('index.html', farmer_name=session.get('name'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        phone = request.form['phone']
        conn = sqlite3.connect('farmers.db')
        cursor = conn.cursor()
        cursor.execute("SELECT name, location, crop FROM farmers WHERE phone = ?", (phone,))
        farmer = cursor.fetchone()
        conn.close()
        if farmer:
            session['phone'] = phone
            session['name'] = farmer[0]
            session['location'] = farmer[1]
            session['crop'] = farmer[2]
            return redirect(url_for('home'))
        else:
            return render_template('login.html', error="Phone number not found. Please register.")
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        location = request.form['location']
        crop = request.form['crop']
        
        try:
            conn = sqlite3.connect('farmers.db')
            cursor = conn.cursor()
            cursor.execute("INSERT INTO farmers (name, phone, location, crop) VALUES (?, ?, ?, ?)",
                           (name, phone, location, crop))
            conn.commit()
            conn.close()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            return render_template('register.html', error="This phone number is already registered.")
            
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/predict', methods=['POST'])
def predict():
    if interpreter is None or not labels:
        return render_template('index.html', prediction_text='Error: Server is not ready.', farmer_name=session.get('name'))
    
    file = request.files.get('image')
    if not file or file.filename == '':
        return render_template('index.html', prediction_text='No image selected.', farmer_name=session.get('name'))

    img_bytes = file.read()
    processed_image = process_image(img_bytes)
    
    interpreter.set_tensor(input_details[0]['index'], processed_image)
    interpreter.invoke()
    
    output_data = interpreter.get_tensor(output_details[0]['index'])
    probabilities = output_data[0]
    
    max_index = np.argmax(probabilities)
    max_prob = probabilities[max_index]
    
    CONFIDENCE_THRESHOLD = 0.5
    if max_prob > CONFIDENCE_THRESHOLD:
        prediction = labels[max_index].replace("___", " ").replace("_", " ")
        result_text = f"Diagnosis: {prediction} ({max_prob:.2%})"
    else:
        result_text = "Unknown or Not a Plant Leaf"
    
    return render_template('index.html', prediction_text=result_text, farmer_name=session.get('name'))

# This route is no longer needed as feedback is now part of the main page
# @app.route('/feedback', ...)

@app.route('/ask', methods=['POST'])
def ask():
    question = request.form.get('question')
    if not question:
        return render_template('index.html', farmer_name=session.get('name'), llm_answer="Please ask a question.")

    location = session.get('location', 'an unknown location')
    crop = session.get('crop', 'an unknown crop')

    prompt = f"""
    You are Krishi Sakhi, an expert AI assistant for farmers.
    Provide a clear, concise, and helpful answer to the following question.
    Give advice that is practical and relevant to the farmer's context.

    Farmer's Context:
    - Location: {location}
    - Main Crop: {crop}

    Farmer's Question:
    "{question}"

    Answer:
    """

    try:
        response = llm_model.generate_content(prompt)
        answer = response.text
    except Exception as e:
        print(f"Gemini API Error: {e}")
        answer = "Sorry, I could not process your request at the moment. Please try again later."
    
    return render_template('index.html', farmer_name=session.get('name'), llm_answer=answer)

if __name__ == '__main__':
    app.run(debug=True)