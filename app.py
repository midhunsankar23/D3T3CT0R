import subprocess
import time
from flask import Flask, jsonify, request, send_from_directory, redirect, url_for, flash, render_template
from threading import Thread
import os
from werkzeug.utils import secure_filename
import pika


app = Flask(__name__)
UPLOAD_FOLDER = 'uploads/'
ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg'])
app.secret_key = "secret key"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024


connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
channel = connection.channel()
channel.queue_declare(queue='image_queue')


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/', methods=['GET'])
def home():
    return send_from_directory('ui', 'index.html')


# get file from upload.html
@app.route('/upload', methods=['GET'])
def upload():
    return send_from_directory('ui', 'upload.html')


# insert image to rabbitmq
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
        # Open a connection to RabbitMQ server
        connection = pika.BlockingConnection(
            pika.ConnectionParameters('localhost'))
        channel = connection.channel()
        # Declare a queue named 'image_queue'
        channel.queue_declare(queue='image_queue')
        # Publish the file to the 'image_queue' queue
        channel.basic_publish(
            exchange='', routing_key='image_queue', body=file.read())
        connection.close()
        flash('Image successfully uploaded and displayed below')
        return send_from_directory('ui', 'index.html')
    else:
        flash('Allowed image types are - png, jpg, jpeg, gif')
        return redirect(request.url)


@app.route('/favicon.ico', methods=['GET'])
def get_favicon():
    return send_from_directory('favicon', 'favicon.ico')

# Define a callback function to handle incoming messages from the 'image_queue'
def process_image(ch, method, properties, body):
    # Create a unique filename for the image
    filename = secure_filename('image_' + str(time.time()) + '.jpg')
    # Save the image to disk
    with open(os.path.join(app.config['UPLOAD_FOLDER'], filename), 'wb') as f:
        f.write(body)
    # Run the image through the YOLO model using Darknet
    darknet_path = 'darknet'
    cfg_path = '/darknet/cfg/yolov3.cfg'
    weights_path = '/darknet/yolov3.weights'
    cmd = [os.path.join(darknet_path, 'darknet'), 'detect', cfg_path, weights_path, os.path.join(app.config['UPLOAD_FOLDER'], filename)]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # Extract the labels from the output and write them to a text file
    labels = [line.decode('utf-8').strip() for line in result.stdout.splitlines()]
    with open(os.path.join(app.config['UPLOAD_FOLDER'], filename + '.txt'), 'w') as f:
        f.write('\n'.join(labels))
    # Acknowledge the message
    ch.basic_ack(delivery_tag=method.delivery_tag)

# Set up the consumer to consume messages from the 'image_queue'
channel.basic_qos(prefetch_count=1)
channel.basic_consume(queue='image_queue', on_message_callback=process_image)

# Start consuming messages from the 'image_queue'
channel.start_consuming()


if __name__ == '__main__':
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument('-p', '--port', type=int, default=5000)
    args = parser.parse_args()
    port = args.port
    app.run(host='0.0.0.0', port=port, debug=True)
    

# TODO - fix same name for image file
