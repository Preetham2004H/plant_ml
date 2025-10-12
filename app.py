from flask import Flask, render_template, request, jsonify, session, redirect
from flask_cors import CORS
import tensorflow as tf
from tensorflow.keras.models import load_model
from PIL import Image
import numpy as np
import io
import base64
from pymongo import MongoClient
import bcrypt
import os
from dotenv import load_dotenv
import google.generativeai as genai
import requests
from datetime import datetime, timedelta
import secrets
import gdown

# Load environment variables
load_dotenv()

# Initialize Flask App
app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
CORS(app)

# MongoDB Setup
client = MongoClient(os.getenv('MONGODB_URI'))
db = client['plant_disease_db']
users_collection = db['users']
predictions_collection = db['predictions']

# Gemini API Setup
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

# Google Drive model download configuration
MODEL_PATH = 'models/plant_disease_model.h5'
MODEL_DRIVE_ID = '11C1dg8Rxiypd8Kq_d_n6AHktr-mocBie'  # Replace with YOUR file ID if different

# Create models directory if it doesn't exist
os.makedirs('models', exist_ok=True)

# Download model from Google Drive if not present
if not os.path.exists(MODEL_PATH):
    print("📥 Downloading model from Google Drive...")
    try:
        gdown.download(
            f'https://drive.google.com/uc?id={MODEL_DRIVE_ID}',
            MODEL_PATH,
            quiet=False
        )
        print("✅ Model downloaded successfully!")
    except Exception as e:
        print(f"❌ Error downloading model: {e}")

# Load Plant Disease Model
try:
    disease_model = load_model(MODEL_PATH)
    print("✓ Model loaded successfully!")
except Exception as e:
    print(f"✗ Error loading model: {e}")
    disease_model = None

# 38 Disease Classes from Kaggle Dataset
CLASS_NAMES = [
    'Apple___Apple_scab', 'Apple___Black_rot', 'Apple___Cedar_apple_rust', 'Apple___healthy',
    'Blueberry___healthy', 'Cherry_(including_sour)___Powdery_mildew',
    'Cherry_(including_sour)___healthy', 'Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot',
    'Corn_(maize)___Common_rust_', 'Corn_(maize)___Northern_Leaf_Blight', 'Corn_(maize)___healthy',
    'Grape___Black_rot', 'Grape___Esca_(Black_Measles)', 'Grape___Leaf_blight_(Isariopsis_Leaf_Spot)',
    'Grape___healthy', 'Orange___Haunglongbing_(Citrus_greening)', 'Peach___Bacterial_spot',
    'Peach___healthy', 'Pepper,_bell___Bacterial_spot', 'Pepper,_bell___healthy',
    'Potato___Early_blight', 'Potato___Late_blight', 'Potato___healthy',
    'Raspberry___healthy', 'Soybean___healthy', 'Squash___Powdery_mildew',
    'Strawberry___Leaf_scorch', 'Strawberry___healthy', 'Tomato___Bacterial_spot',
    'Tomato___Early_blight', 'Tomato___Late_blight', 'Tomato___Leaf_Mold',
    'Tomato___Septoria_leaf_spot', 'Tomato___Spider_mites Two-spotted_spider_mite',
    'Tomato___Target_Spot', 'Tomato___Tomato_Yellow_Leaf_Curl_Virus', 'Tomato___Tomato_mosaic_virus',
    'Tomato___healthy'
]

# Language translations mapping
LANGUAGE_CODES = {
    'Hindi': 'hi',
    'Kannada': 'kn',
    'Tamil': 'ta',
    'Telugu': 'te',
    'Marathi': 'mr',
    'Bengali': 'bn',
    'English': 'en'
}


# ============== HELPER FUNCTIONS ==============

def get_plant_list():
    """Extract unique plant names from class names"""
    plants = set()
    for class_name in CLASS_NAMES:
        plant_name = class_name.split('___')[0]
        # Clean up plant names
        plant_name = plant_name.replace('_', ' ').replace('(including sour)', '').replace(',', '').strip()
        plants.add(plant_name)
    return sorted(list(plants))


PLANT_LIST = get_plant_list()


def validate_plant_image(image_data, selected_plant):
    """Validate if uploaded image matches the selected plant using Gemini API"""
    try:
        img = Image.open(io.BytesIO(image_data))

        prompt = f"""Analyze this image and determine:
        1. Is this a plant leaf image? (YES/NO)
        2. Does this appear to be a {selected_plant} plant? (YES/NO)

        Respond with ONLY two words separated by comma: 
        First word: YES or NO for plant leaf
        Second word: YES or NO for {selected_plant} match

        Example response: YES, YES
        Do not provide any other text."""

        model = genai.GenerativeModel('gemini-1.5-flash-exp-0827')  # Updated to a valid experimental model name; adjust if needed
        response = model.generate_content([prompt, img])
        result = response.text.strip().upper()

        # Parse response
        parts = result.split(',')
        is_plant = 'YES' in parts[0]
        is_correct_plant = 'YES' in parts[1] if len(parts) > 1 else False

        return is_plant, is_correct_plant
    except Exception as e:
        print(f"Validation error: {e}")
        return True, True  # Default to True if validation fails


def preprocess_image(image_data):
    """Preprocess image for model prediction"""
    img = Image.open(io.BytesIO(image_data))
    img = img.convert('RGB')
    img = img.resize((256, 256))
    img_array = np.array(img) / 255.0
    img_array = np.expand_dims(img_array, axis=0)
    return img_array


def filter_classes_by_plant(plant_name):
    """Filter class names by selected plant"""
    filtered_classes = []
    for idx, class_name in enumerate(CLASS_NAMES):
        class_plant = class_name.split('___')[0]
        class_plant_clean = class_plant.replace('_', ' ').replace('(including sour)', '').replace(',', '').strip()

        if class_plant_clean.lower() == plant_name.lower():
            filtered_classes.append((idx, class_name))

    return filtered_classes


def get_disease_info_gemini(disease_name, plant_name, language='English'):
    """Get disease information, prevention, and remedies using Gemini API"""
    try:
        prompt = f"""You are an agricultural expert. Provide detailed information about the {plant_name} plant disease: {disease_name}

Please provide the response in {language} language and include:

1. **Disease Overview** (2-3 sentences about what this disease is)

2. **Symptoms** (List 4-5 specific symptoms to look for):
   - Symptom 1
   - Symptom 2
   - Symptom 3
   - Symptom 4

3. **Causes** (What causes this disease):
   - Main cause
   - Contributing factors

4. **Prevention Measures** (5-6 practical steps):
   - Step 1
   - Step 2
   - Step 3
   - Step 4
   - Step 5

5. **Treatment & Remedies** (5-6 practical solutions):
   - Organic remedy 1
   - Organic remedy 2
   - Chemical treatment (if needed)
   - Home remedies

6. **Additional Tips for Farmers**

Format the response clearly with proper headings and bullet points.
Use simple, farmer-friendly language that is easy to understand."""

        model = genai.GenerativeModel('gemini-1.5-flash-exp-0827')  # Updated to a valid experimental model name
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Gemini API Error: {e}")
        return f"Error getting disease information: {str(e)}"


def detect_with_gemini(image_data, plant_name, language='English'):
    """Fallback detection using Gemini API when model fails"""
    try:
        img = Image.open(io.BytesIO(image_data))

        prompt = f"""You are an expert agricultural pathologist. Analyze this {plant_name} leaf image and provide:

1. **Confirmation**: Is this a {plant_name} plant? (YES/NO)
2. **Disease Status**: Healthy or Disease Name
3. **Confidence Level**: Percentage (90-100%)
4. **Visual Analysis**: What you observe in the image

Then provide detailed information in {language} language:

5. **Symptoms Visible**: List specific symptoms you can see
6. **Possible Causes**: What might have caused this condition
7. **Prevention Measures**: 5 practical steps to prevent this (if disease detected)
8. **Treatment Recommendations**: 5 safe and farmer-friendly treatments

Format the response clearly with proper headings and bullet points. Do not use markdown headers."""

        model = genai.GenerativeModel('gemini-1.5-flash-exp-0827')  # Updated to a valid experimental model name
        response = model.generate_content([prompt, img])
        return response.text
    except Exception as e:
        print(f"Gemini detection error: {e}")
        return f"Error in Gemini detection: {str(e)}"


def get_crop_recommendation(temperature, humidity, rainfall, soil_type):
    """Get crop recommendation based on weather and soil"""
    try:
        prompt = f"""As an agricultural expert, recommend the top 5 most suitable crops for the following conditions:

- Temperature: {temperature}°C
- Humidity: {humidity}%
- Rainfall: {rainfall}mm
- Soil Type: {soil_type}

Provide:
1. Crop name
2. Why it's suitable for these conditions
3. Expected yield potential
4. Best planting time/season

Format as a clear, numbered list. Keep recommendations practical and region-appropriate for Indian agriculture."""

        model = genai.GenerativeModel('gemini-1.5-flash-exp-0827')  # Updated to a valid experimental model name
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Recommendation error: {e}")
        return f"Error getting recommendations: {str(e)}"


def query_gemini_weather(city):
    """Query Gemini for weather information"""
    try:
        prompt = f"""Provide the current weather and 7-day forecast for {city}. 

        Include:
        - Current temperature, humidity, wind speed, precipitation, and weather condition
        - 7-day forecast with date, high/low temperatures, precipitation, and condition

        Format the response in a clear, structured way."""

        model = genai.GenerativeModel('gemini-1.5-flash-exp-0827')  # Updated to a valid experimental model name
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Weather query error: {e}")
        return f"Error getting weather information: {str(e)}"


def test_gemini_connection():
    """Test Gemini API connection"""
    try:
        print("\n" + "=" * 60)
        print("Testing Gemini API Connection...")
        print("=" * 60)

        model = genai.GenerativeModel('gemini-1.5-flash-exp-0827')  # Updated to a valid experimental model name
        response = model.generate_content("Say 'Hello, PlantCare AI is ready!'")
        print(f"✓ Gemini API is working!")
        print(f"✓ Response: {response.text}")
        print(f"✓ Available plants: {len(PLANT_LIST)} types")
        print("=" * 60 + "\n")
    except Exception as e:
        print(f"✗ Error testing Gemini API: {e}\n")


# ============== AUTHENTICATION ROUTES ==============

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/login')
def login():
    return render_template('auth.html')


@app.route('/signup')
def signup():
    return render_template('auth.html')


@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')
    return render_template('dashboard.html', plants=PLANT_LIST)


@app.route('/weather')
def weather():
    if 'user_id' not in session:
        return redirect('/login')
    return render_template('weather.html')


@app.route('/detect')
def detect():
    if 'user_id' not in session:
        return redirect('/login')
    return render_template('detect.html', plants=PLANT_LIST)


@app.route('/model-info')
def model_info():
    if 'user_id' not in session:
        return redirect('/login')
    return render_template('model_info.html')


@app.route('/api/signup', methods=['POST'])
def api_signup():
    try:
        data = request.json
        name = data.get('name')
        email = data.get('email')
        password = data.get('password')

        if users_collection.find_one({'email': email}):
            return jsonify({'success': False, 'message': 'Email already exists'}), 400

        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        user = {
            'name': name,
            'email': email,
            'password': hashed_password,
            'created_at': datetime.now()
        }

        result = users_collection.insert_one(user)

        return jsonify({'success': True, 'message': 'Signup successful'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/login', methods=['POST'])
def api_login():
    try:
        data = request.json
        email = data.get('email')
        password = data.get('password')

        user = users_collection.find_one({'email': email})

        if not user:
            return jsonify({'success': False, 'message': 'Invalid email or password'}), 401

        if bcrypt.checkpw(password.encode('utf-8'), user['password']):
            session['user_id'] = str(user['_id'])
            session['user_name'] = user['name']
            return jsonify({'success': True, 'message': 'Login successful'})
        else:
            return jsonify({'success': False, 'message': 'Invalid email or password'}), 401
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/logout', methods=['POST'])
def api_logout():
    session.clear()
    return jsonify({'success': True, 'message': 'Logout successful'})


@app.route('/api/plants', methods=['GET'])
def get_plants():
    """Return list of available plants"""
    return jsonify({'success': True, 'plants': PLANT_LIST})


# ============== DISEASE DETECTION ROUTES ==============

@app.route('/api/detect-disease', methods=['POST'])
def detect_disease():
    try:
        if 'image' not in request.files:
            return jsonify({'success': False, 'message': 'No image uploaded'}), 400

        image_file = request.files['image']
        language = request.form.get('language', 'English')
        plant_name = request.form.get('plant_name', '')

        if not plant_name:
            return jsonify({'success': False, 'message': 'Please select a plant type first'}), 400

        image_data = image_file.read()

        # Validate if image is a plant and matches selected plant
        is_plant, is_correct_plant = validate_plant_image(image_data, plant_name)

        if not is_plant:
            return jsonify({
                'success': False,
                'message': 'Please upload a plant leaf image only. The uploaded image does not appear to be a plant.'
            }), 400

        if not is_correct_plant:
            return jsonify({
                'success': False,
                'message': f'The uploaded image does not appear to be a {plant_name} plant. Please upload a {plant_name} leaf image or select the correct plant type.'
            }), 400

        # Filter classes for selected plant
        plant_classes = filter_classes_by_plant(plant_name)

        if not plant_classes:
            return jsonify({
                'success': False,
                'message': f'No disease data available for {plant_name}. Using AI analysis instead.'
            }), 400

        # Try model prediction first
        model_success = False
        if disease_model:
            try:
                img_array = preprocess_image(image_data)
                predictions = disease_model.predict(img_array)

                # Get predictions for the selected plant only
                plant_predictions = []
                for idx, class_name in plant_classes:
                    conf = float(predictions[0][idx])
                    plant_predictions.append((idx, class_name, conf))

                # Sort by confidence
                plant_predictions.sort(key=lambda x: x[2], reverse=True)

                # Get top prediction for this plant
                if plant_predictions:
                    predicted_class_idx, disease_class_name, confidence = plant_predictions[0]

                    if confidence > 0.5:  # Threshold for plant-specific detection
                        model_success = True

                        # Extract disease name
                        disease_name = disease_class_name.split('___')[
                            1] if '___' in disease_class_name else disease_class_name
                        disease_name = disease_name.replace('_', ' ')

                        # Get detailed info from Gemini
                        disease_info = get_disease_info_gemini(disease_name, plant_name, language)

                        # Save prediction
                        prediction_record = {
                            'user_id': session.get('user_id'),
                            'plant_name': plant_name,
                            'disease_name': disease_name,
                            'confidence': confidence,
                            'language': language,
                            'timestamp': datetime.now(),
                            'method': 'model'
                        }
                        predictions_collection.insert_one(prediction_record)

                        return jsonify({
                            'success': True,
                            'method': 'model',
                            'plant_name': plant_name,
                            'disease_name': disease_name,
                            'confidence': confidence,
                            'disease_info': disease_info
                        })
            except Exception as e:
                print(f"Model prediction error: {e}")

        # Fallback to Gemini if model fails or low confidence
        if not model_success:
            gemini_result = detect_with_gemini(image_data, plant_name, language)

            prediction_record = {
                'user_id': session.get('user_id'),
                'plant_name': plant_name,
                'language': language,
                'timestamp': datetime.now(),
                'method': 'gemini',
                'result': gemini_result
            }
            predictions_collection.insert_one(prediction_record)

            return jsonify({
                'success': True,
                'method': 'gemini',
                'plant_name': plant_name,
                'disease_info': gemini_result
            })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ============== WEATHER ROUTES ==============

@app.route('/api/weather', methods=['GET'])
def get_weather():
    try:
        city = request.args.get('city', 'Bangalore')

        # Using Open-Meteo API (free, no API key needed)
        geocode_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1&language=en&format=json"
        geo_response = requests.get(geocode_url)
        geo_data = geo_response.json()

        if 'results' not in geo_data:
            return jsonify({'success': False, 'message': 'City not found'}), 404

        lat = geo_data['results'][0]['latitude']
        lon = geo_data['results'][0]['longitude']

        # Get weather data
        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m&daily=temperature_2m_max,temperature_2m_min,precipitation_sum&timezone=auto"
        weather_response = requests.get(weather_url)
        weather_data = weather_response.json()

        return jsonify({
            'success': True,
            'weather': weather_data,
            'city': city
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/weather_gemini', methods=['GET'])
def weather_gemini():
    city = request.args.get('city', '').strip()
    if not city:
        return jsonify({'success': False, 'message': 'City parameter required'}), 400

    try:
        weather_info = query_gemini_weather(city)
        return jsonify({'success': True, 'city': city, 'weather_info': weather_info})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ============== CROP RECOMMENDATION ROUTES ==============

@app.route('/api/crop-recommendation', methods=['POST'])
def crop_recommendation():
    try:
        data = request.json
        temperature = data.get('temperature')
        humidity = data.get('humidity')
        rainfall = data.get('rainfall')
        soil_type = data.get('soil_type', 'loamy')

        recommendations = get_crop_recommendation(temperature, humidity, rainfall, soil_type)

        return jsonify({
            'success': True,
            'recommendations': recommendations
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ============== SAVE/RETRIEVE RECORDS ROUTES ==============

@app.route('/api/save-report', methods=['POST'])
def save_report():
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': 'Not authenticated'}), 401

        data = request.json
        data['user_id'] = session['user_id']
        data['timestamp'] = datetime.now()

        # Save to MongoDB
        result = db['saved_reports'].insert_one(data)

        return jsonify({'success': True, 'id': str(result.inserted_id)})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/save-diagnosis', methods=['POST'])
def save_diagnosis():
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': 'Not authenticated'}), 401

        data = request.json
        data['user_id'] = session['user_id']
        data['timestamp'] = datetime.now()

        # Save to MongoDB
        result = db['diagnosis_records'].insert_one(data)

        return jsonify({'success': True, 'id': str(result.inserted_id)})
    except Exception as e:
        return jupytext({'success': False, 'message': str(e)}), 500


@app.route('/api/get-saved-records', methods=['GET'])
def get_saved_records():
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': 'Not authenticated'}), 401

        user_id = session['user_id']

        # Get saved reports and diagnoses
        reports = list(db['saved_reports'].find({'user_id': user_id}).sort('timestamp', -1))
        diagnoses = list(db['diagnosis_records'].find({'user_id': user_id}).sort('timestamp', -1))

        # Convert ObjectId to string
        for item in reports + diagnoses:
            item['_id'] = str(item['_id'])
            if 'timestamp' in item:
                item['timestamp'] = item['timestamp'].isoformat()

        return jsonify({
            'success': True,
            'reports': reports,
            'diagnoses': diagnoses
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ============== MAIN ==============

if __name__ == '__main__':
    test_gemini_connection()
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))