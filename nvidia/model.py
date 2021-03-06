# Import basic

# from keras.models import Sequential
import argparse

from keras.layers.core import Dense, Flatten, Dropout
from keras.layers.convolutional import Convolution2D
from keras.callbacks import ModelCheckpoint, CSVLogger, EarlyStopping, TensorBoard
from keras.layers import Input, Dense, Flatten, ELU, merge
from keras.models import Model
from keras.regularizers import l2
from keras.optimizers import Adam
from loader import generate_thunderhill_batches, getDataFromFolder
from config import *

""" Usefeful link
		ImageDataGenerator 		- https://keras.io/preprocessing/image/
		Saving / Loading model  - http://machinelearningmastery.com/save-load-keras-deep-learning-models/
		NVIDIA					- https://arxiv.org/pdf/1604.07316v1.pdf
		Features Extraction     - https://keras.io/applications/
		ewma					- http://pandas.pydata.org/pandas-docs/version/0.17.0/generated/pandas.ewma.html
		Callbacks				- https://keras.io/callbacks/

		Dropout 5x5
"""
def NvidiaModel(learning_rate, dropout):
    input_model = Input(shape=(HEIGHT, WIDTH, DEPTH))
    x = Convolution2D(24, 5, 5, border_mode='valid', subsample=(2, 2), W_regularizer=l2(learning_rate))(input_model)
    x = ELU()(x)
    x = Convolution2D(36, 5, 5, border_mode='valid', subsample=(2, 2), W_regularizer=l2(learning_rate))(x)
    x = ELU()(x)
    x = Convolution2D(48, 5, 5, border_mode='valid', subsample=(2, 2), W_regularizer=l2(learning_rate))(x)
    x = ELU()(x)
    x = Convolution2D(64, 3, 3, border_mode='valid', subsample=(1, 1), W_regularizer=l2(learning_rate))(x)
    x = ELU()(x)
    x = Convolution2D(64, 3, 3, border_mode='valid', subsample=(1, 1), W_regularizer=l2(learning_rate))(x)
    x = ELU()(x)
    x = Flatten()(x)
    x = Dense(100)(x)
    x = ELU()(x)
    x = Dropout(dropout)(x)
    x = Dense(50)(x)
    x = ELU()(x)
    x = Dropout(dropout)(x)
    x = Dense(10)(x)
    x = ELU()(x)
    predictions = Dense(1)(x)
    model = Model(input=input_model, output=predictions)
    model.compile(optimizer='adam', loss='mse')
    return model


def Comma(includeTop=True):
    input_model = Input(shape=(HEIGHT, WIDTH, DEPTH))
    x = Convolution2D(16, 8, 8, activation='elu', subsample=(4, 4), border_mode="same", init='he_normal', name='block1_conv1')(input_model)
    x = Convolution2D(32, 5, 5, activation='elu', subsample=(2, 2), border_mode="same", init='he_normal', name='block2_conv1')(x)
    x = Convolution2D(64, 5, 5, activation='elu', subsample=(2, 2), border_mode="same", init='he_normal', name='block3_conv1')(x)
    x = Dropout(0.2)(x)

    if includeTop:
        x = Flatten()(x)
        x = Dense(512, activation='elu', name='fc1')(x)
        x = Dropout(0.5)(x)
        x = Dense(1, name='prediction')(x)

    model = Model(input=input_model, output=x, name='comma')
    model.compile(optimizer=Adam(lr=0.0002), loss='mse')
    return model


def Hybrid():
    input_model = Input(shape=(HEIGHT, WIDTH, DEPTH))
    nvidia = Convolution2D(24, 5, 5, activation='elu', border_mode='same', subsample=(4, 4), init='he_normal', name='nvidia_conv1')(input_model)
    nvidia = Convolution2D(36, 5, 5, activation='elu', border_mode='same', subsample=(2, 2), init='he_normal', name='nvidia_conv2')(nvidia)
    nvidia = Convolution2D(48, 5, 5, activation='elu', border_mode='same', subsample=(2, 2), init='he_normal', name='nvidia_conv3')(nvidia)
    nvidia = Convolution2D(64, 3, 3, activation='elu', border_mode='same', subsample=(1, 1), init='he_normal', name='nvidia_conv4')(nvidia)
    nvidia = Convolution2D(64, 3, 3, activation='elu', border_mode='same', subsample=(1, 1), init='he_normal', name='nvidia_conv5')(nvidia)
    nvidia = Flatten()(nvidia)
    nvidia = Dense(100, activation='elu', init='he_normal', name='nvidia_fc1')(nvidia)
    nvidia = Dropout(0.5)(nvidia)
    nvidia = Dense(50, activation='elu', init='he_normal', name='nvidia_fc2')(nvidia)
    nvidia = Dropout(0.5)(nvidia)
    nvidia = Dense(10, activation='elu', init='he_normal', name='nvidia_fc3')(nvidia)

    comma = Convolution2D(16, 8, 8, activation='elu', subsample=(4, 4), border_mode="same", init='he_normal', name='comma_conv1')(input_model)
    comma = Convolution2D(32, 5, 5, activation='elu', subsample=(2, 2), border_mode="same", init='he_normal', name='comma_conv2')(comma)
    comma = Convolution2D(64, 5, 5, activation='elu', subsample=(2, 2), border_mode="same", init='he_normal', name='comma_conv3')(comma)
    comma = Dropout(0.2)(comma)
    comma = Flatten()(comma)
    comma = Dense(512, activation='elu', name='comma_fc1')(comma)
    comma = Dropout(0.5)(comma)

    concat = merge([nvidia, comma], mode='concat', concat_axis=-1, name="merged_layer")
    concat = Dense(1, name='prediction')(concat)

    model = Model(input=input_model, output=concat, name='hybrid')
    model.compile(optimizer=Adam(lr=0.0002), loss='mse')
    return model

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Steering angle model trainer')
    parser.add_argument('--batch', type=int, default=BATCH_SIZE, help='Batch size.')
    parser.add_argument('--epoch', type=int, default=EPOCHS, help='Number of epochs.')
    parser.add_argument('--alpha', type=float, default=ALPHA, help='Learning rate')
    parser.add_argument('--dropout', type=float, default=DROPOUT, help='Dropout rate')
    parser.add_argument('--width', type=int, default=WIDTH, help='width')
    parser.add_argument('--height', type=int, default=HEIGHT, help='height')
    parser.add_argument('--depth', type=int, default=DEPTH, help='depth')
    parser.add_argument('--adjustement', type=float, default=ADJUSTMENT, help='x per pixel')
    parser.add_argument('--weights', type=str, help='Load weights')
    parser.add_argument('--model', type=int, required=True, help='Chose a model')
    parser.add_argument('--dataset', type=str, required=True, help='dataset path')
    parser.add_argument('--output', type=str, required=True, help='output path')
    args = parser.parse_args()

    if not os.path.exists(args.output):
        os.makedirs(args.output)

    print('-------------')
    print('BATCH        : {}'.format(args.batch))
    print('EPOCH        : {}'.format(args.epoch))
    print('ALPA         : {}'.format(args.alpha))
    print('DROPOUT      : {}'.format(args.dropout))
    print('Load Weights?: {}'.format(args.weights))
    print('Dataset      : {}'.format(args.dataset))
    print('OUTPUT       : {}'.format(args.output))
    print('MODEL        ; {}'.format(args.model))
    print('-------------')

    df_train, df_val = getDataFromFolder(args.dataset, args.output)
    print('TRAIN:', len(df_train))
    print('VALIDATION:', len(df_val))

    models = [NvidiaModel(args.alpha, args.dropout), Comma(), Hybrid()]
    model = models[args.model]

    print(model.summary())

    # Saves the model...
    with open(os.path.join(args.output, 'model.json'), 'w') as f:
        f.write(model.to_json())

    try:
        if args.weights:
            print('Loading weights from file ...')
            model.load_weights(args.weights)
    except IOError:
        print("No model found")

    checkpointer = ModelCheckpoint(os.path.join(args.output, 'weights.{epoch:02d}-{val_loss:.3f}.hdf5'))
    early_stop = EarlyStopping(monitor='val_loss', patience=20, verbose=0, mode='auto')
    logger = CSVLogger(filename=os.path.join(args.output, 'history.csv'))
    board = TensorBoard(log_dir=args.output, histogram_freq=0, write_graph=True, write_images=True)

    history = model.fit_generator(
        generate_thunderhill_batches(df_train, args),
        nb_epoch=args.epoch,
        samples_per_epoch=args.batch*50,
        validation_data=generate_thunderhill_batches(df_val, args),
        nb_val_samples=args.batch*10,
        callbacks=[
            checkpointer,
            early_stop,
            logger,
            board
        ]
    )