import os
from werkzeug.utils import secure_filename
import subprocess
import time
from pymongo import MongoClient
import pika
from utility.yolo_detection_images import detectObjects

UPLOAD_FOLDER = 'queue/'
ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg'])

connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
channel = connection.channel()
channel.queue_declare(queue='image_queue')

# client = MongoClient('localhost', 27017)
# db = client['image_labels']
# collection = db['labels']

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_image(ch, method, properties, body):
    print("Received an image from the queue")
    filename = secure_filename('image_' + str(time.time()) + '.jpg')
    with open(os.path.join(UPLOAD_FOLDER, filename), 'wb') as f:
        f.write(body)
    print("Saved the image to disk as", filename)
    img_path = UPLOAD_FOLDER + '/' + filename
    results = detectObjects(img_path)
    with open(os.path.join(UPLOAD_FOLDER, filename + '.txt'), 'w') as f:
        f.write(str(results))
    print("Detected the following labels:", results)
    print("Uploaded the label data to the database")
    ch.basic_ack(delivery_tag=method.delivery_tag)
    print("Acknowledged the message")




channel.basic_qos(prefetch_count=1)
channel.basic_consume(queue='image_queue', on_message_callback=process_image)
channel.start_consuming()
