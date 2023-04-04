from io import BytesIO
import subprocess
import time
from flask import Flask, jsonify, request, send_from_directory, redirect, url_for, flash, render_template
from threading import Thread
import os
from werkzeug.utils import secure_filename
import pika
from pymongo import MongoClient



app = Flask(__name__, template_folder='ui')
UPLOAD_FOLDER = os.path.abspath('uploads')
UI_FOLDER = os.path.abspath('ui')
ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg'])
app.secret_key = "secret key"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
channel = connection.channel()
channel.queue_declare(queue='image_queue')

client = MongoClient('localhost', 27017)
db = client['image_labels']
collection = db['labels']

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/', methods=['GET'])
def home():
    return send_from_directory('ui', 'upload.html')

@app.route('/upload', methods=['GET'])
def upload():
    return send_from_directory('ui', 'upload.html')

@app.route('/insert_image', methods=['POST'])
def insert_image():
    if 'file' not in request.files:
        flash('No file part')
        return redirect(request.url)
        
    file = request.files['file']
    if file.filename == '':
        flash('No image selected for uploading')
        return redirect(request.url)
    
    if allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        with open(file_path, 'rb') as f:
            channel.basic_publish(exchange='', routing_key='image_queue', body=f.read())
            
        flash('Image successfully uploaded and displayed below')
        return send_from_directory('ui', 'index.html')
        
    else:
        flash('Allowed image types are - png, jpg, jpeg')
        return redirect(request.url)


@app.route('/db')
def index():
    # retrieve data from the database
    data = []
    for doc in collection.find():
        data.append(doc)

    # render HTML template with data
    return render_template('processed.html', data=data)



if __name__ == '__main__':
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument('-p', '--port', type=int, default=5000)
    args = parser.parse_args()
    port = args.port
    app.run(host='0.0.0.0', port=80, debug=True)

