import subprocess
import time
from flask import Flask, jsonify, request, send_from_directory, redirect, url_for, flash, render_template
from threading import Thread
import os
from werkzeug.utils import secure_filename
import pika
from pymongo import MongoClient

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads/'
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
    return send_from_directory('ui', 'index.html')

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
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        channel = connection.channel()
        channel.queue_declare(queue='image_queue')
        channel.basic_publish(exchange='', routing_key='image_queue', body=file.read())
        connection.close()
        flash('Image successfully uploaded and displayed below')
        return send_from_directory('ui', 'index.html')
    else:
        flash('Allowed image types are - png, jpg, jpeg, gif')
        return redirect(request.url)

@app.route('/favicon.ico', methods=['GET'])
def get_favicon():
    return send_from_directory('favicon', 'favicon.ico')

def process_image(ch, method, properties, body):
    filename = secure_filename('image_' + str(time.time()) + '.jpg')
    with open(os.path.join(app.config['UPLOAD_FOLDER'], filename), 'wb') as f:
        f.write(body)
    darknet_path = 'darknet'
    cfg_path = '/darknet/cfg/yolov3.cfg'
    weights_path = '/darknet/yolov3.weights'
    cmd = [os.path.join(darknet_path, 'darknet'), 'detect', cfg_path, weights_path, os.path.join(app.config['UPLOAD_FOLDER'], filename)]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    labels = [line.decode('utf-8').strip() for line in result.stdout.splitlines()]
    with open(os.path.join(app.config['UPLOAD_FOLDER'], filename + '.txt'), 'w') as f:
        f.write('\n'.join(labels))
    label_data = {'filename': filename, 'labels': labels}
    collection.insert_one(label_data)
    ch.basic_ack(delivery_tag=method.delivery_tag)

channel.basic_qos(prefetch_count=1)
channel.basic_consume(queue='image_queue', on_message_callback=process_image)
channel.start_consuming()

if __name__ == '__main__':
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument('-p', '--port', type=int, default=5000)
    args = parser.parse_args()
    port = args.port
    app.run(host='0.0.0.0', port=port, debug=True)

