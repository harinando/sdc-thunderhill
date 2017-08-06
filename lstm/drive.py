import argparse
import base64
from datetime import datetime
import os
import shutil
from io import BytesIO
import pickle

import numpy as np
from PIL import Image
from pandas.stats.moments import ewma

import socketio
import eventlet
import eventlet.wsgi
from flask import Flask
from keras.models import load_model
from keras.models import model_from_json
from keras.models import Model
import h5py
from keras import __version__ as keras_version
from transformations import Preproc
from config import SVR_MODEL, CNN_INPUT_SIZE, SEQ_LENGTH, HEIGHT, WIDTH, DEPTH, LAYER
from model import load_from_h5

sio = socketio.Server()
app = Flask(__name__)
model = None
prev_image_array = [np.random.rand(CNN_INPUT_SIZE)]*SEQ_LENGTH

lstm = None
feature_extractor_model = None

class SimplePIController:
    def __init__(self, Kp, Ki):
        self.Kp = Kp
        self.Ki = Ki
        self.set_point = 0.
        self.error = 0.
        self.integral = 0.

    def set_desired(self, desired):
        self.set_point = desired

    def update(self, measurement):
        # proportional error
        self.error = self.set_point - measurement

        # integral error
        self.integral += self.error

        return self.Kp * self.error + self.Ki * self.integral

controller = SimplePIController(0.1, 0.002)
set_speed = 70
controller.set_desired(set_speed)

# with open('/Users/nando/Downloads/.hdf5_checkpoints-16/model.json', 'r') as f:
#     feature_extractor_model = model_from_json(f.read())
#
# feature_extractor_model.compile("adam", "mse")
# feature_extractor_model.load_weights('/Users/nando/Downloads/.hdf5_checkpoints-16/model.h5')
# feature_extractor = Model(input=feature_extractor_model.layers[0].input, output=feature_extractor_model.layers[LAYER].output)
# feature_extractor.compile(optimizer='adam', loss='mse')

feature_extractor = load_from_h5('/Users/nando/Downloads/model.h5', LAYER)

# X_scaler = pickle.load(open('scaler.p', 'rb'))
# svr = pickle.load(open(SVR_MODEL, 'rb'))

@sio.on('telemetry')
def telemetry(sid, data):
    if data:
        # The current steering angle of the car
        steering_angle = data["steering_angle"]
        # The current throttle of the car
        throttle = data["throttle"]
        # The current speed of the car
        speed = data["speed"]
        # The current image from the center camera of the car
        imgString = data["image"]

        # The current image position
        positionX, positionY, positionZ = data['position'].split(":")

        # the current image rotation
        rotationX, rotationY, rotationZ = data['rotation'].split(":")
        # image = Image.open(BytesIO(base64.b64decode(imgString)))
        # image_array = np.asarray(image)
        # steering_angle = float(model.predict(image_array[None, :, :, :], batch_size=1))
        #
        # throttle = controller.update(float(speed))
        # print(steering_angle, throttle)
        # send_control(steering_angle, throttle)
        image = Image.open(BytesIO(base64.b64decode(imgString)))
        # image_array = cv2.cvtColor(np.asarray(image), code=cv2.COLOR_RGB2BGR)

        image_array = np.asarray(image)
        image_array = Preproc(image_array)

        ################### LSTM
        transformed_image_array = feature_extractor.predict(np.reshape(image_array, (1, HEIGHT, WIDTH, DEPTH)))[0]
        # Adding other features speed and other stuff...
        # X = np.array([positionX, positionY, positionZ, rotationX, rotationY, rotationZ, speed], dtype=float)
        # X = X_scaler.transform(X)
        # transformed_image_array = np.hstack((transformed_image_array, X))
        prev_image_array.pop(0)
        prev_image_array.append(transformed_image_array)
        steering_angle = float(model.predict(np.array(prev_image_array)[None, :]))
        ############################# Steering angles ##########################################################
        # transformed_image_array = image_array[None, :, :, :]
        # steering_angle = float(model.predict(transformed_image_array, batch_size=1))

        # The driving model currently just outputs a constant throttle. Feel free to edit this.
        throttle = args.throttle
        ############################# THROTTLE ##########################################################
        # X = np.array([positionX, positionY, positionZ, rotationX, rotationY, rotationZ, 0, speed, steering_angle], dtype=float)
        # X_test = X_scaler.transform(X.reshape(1, -1))
        # throttle = np.min([1, svr.predict(X_test)])
        ############################## BRAKE ############################################################
        # if np.abs(steering_angle) > 0.2 and int(speed) > 50:
        #     throttle = -throttle/4
        # elif np.abs(steering_angle) > 0.5:
        #     throttle = -throttle

        print(steering_angle, throttle)
        send_control(steering_angle, throttle)

        # save frame
        if args.image_folder != '':
            timestamp = datetime.utcnow().strftime('%Y_%m_%d_%H_%M_%S_%f')[:-3]
            image_filename = os.path.join(args.image_folder, timestamp)
            image.save('{}.jpg'.format(image_filename))
    else:
        # NOTE: DON'T EDIT THIS.
        sio.emit('manual', data={}, skip_sid=True)


@sio.on('connect')
def connect(sid, environ):
    print("connect ", sid)
    send_control(0, 0)


def send_control(steering_angle, throttle):
    sio.emit(
        "steer",
        data={
            'steering_angle': steering_angle.__str__(),
            'throttle': throttle.__str__()
        },
        skip_sid=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Remote Driving')
    parser.add_argument(
        'model',
        type=str,
        help='Path to model h5 file. Model should be on the same path.'
    )
    parser.add_argument(
        'image_folder',
        type=str,
        nargs='?',
        default='',
        help='Path to image folder. This is where the images from the run will be saved.'
    )

    parser.add_argument('--throttle', type=float, default=0.3, help='Throttle')

    args = parser.parse_args()

    # check that model Keras version is same as local Keras version
    f = h5py.File(args.model, mode='r')
    model_version = f.attrs.get('keras_version')
    keras_version = str(keras_version).encode('utf8')

    if model_version != keras_version:
        print('You are using Keras version ', keras_version,
              ', but the model was built using ', model_version)

    model = load_model(args.model)

    print(model.summary())

    print('model loaded....')

    if args.image_folder != '':
        print("Creating image folder at {}".format(args.image_folder))
        if not os.path.exists(args.image_folder):
            os.makedirs(args.image_folder)
        else:
            shutil.rmtree(args.image_folder)
            os.makedirs(args.image_folder)
        print("RECORDING THIS RUN ...")
    else:
        print("NOT RECORDING THIS RUN ...")

    # wrap Flask application with engineio's middleware
    app = socketio.Middleware(sio, app)

    # deploy as an eventlet WSGI server
    eventlet.wsgi.server(eventlet.listen(('', 4567)), app)
