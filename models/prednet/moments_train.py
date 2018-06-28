'''
Train PredNet on Moments in Time sequences.
Adapted from https://github.com/coxlab/prednet/blob/master/kitti_train.py
'''
import os

from keras.models import Model
from keras.callbacks import LearningRateScheduler, ModelCheckpoint
from keras.callbacks import CSVLogger, EarlyStopping
from keras.optimizers import Adam

from moments_settings import *
import utils
import argparse
import sys
sys.path.append("../classifier")
from data import DataGenerator


def get_callbacks(results_dir, stopping_patience=None):
    
    # start with lr of 0.001 and then drop to 0.0001 after 75 epochs
    lr_schedule = lambda epoch: 0.001 if epoch < 75 else 0.0001    
    callbacks = [LearningRateScheduler(lr_schedule)]
    
    checkpoint_path = os.path.join(results_dir, 'weights.hdf5')
    csv_path = os.path.join(results_dir, 'train.log')
    checkpointer = ModelCheckpoint(filepath=checkpoint_path,
                                   monitor='val_loss',
                                   verbose=1, save_best_only=True)
    csv_logger = CSVLogger(csv_path)
    callbacks.append(checkpointer)
    callbacks.append(csv_logger)
    if stopping_patience:
        stopper = EarlyStopping(monitor='val_loss', 
                                patience=stopping_patience, 
                                verbose=0, mode='auto')
        callbacks.append(stopper)
    return callbacks
    
def train(config_name, training_data_dir, validation_data_dir, 
          base_results_dir, test_data_dir=None, epochs=150, 
          use_multiprocessing=False, workers=1, shuffle=True,
          n_timesteps=10, batch_size=4, stopping_patience=None, 
          classes=None, input_shape=None, max_queue_size=10, 
          training_max_per_class=None, frame_step=1, **config):
    
    model = utils.create_model(train=True, **config)
    model.summary()
    model.compile(loss='mean_absolute_error', optimizer='adam')
    
    layer_config = model.layers[1].get_config()
    data_format = layer_config['data_format'] if 'data_format' in layer_config else layer_config['dim_ordering']
    
    train_generator = DataGenerator(classes=classes,
                                    seq_length=n_timesteps,
                                    sample_step=frame_step,
                                    target_size=input_shape,
                                    batch_size=batch_size, shuffle=shuffle,
                                    data_format=data_format,
                                    output_mode='error',
                                    max_per_class=training_max_per_class)
    
    val_generator = DataGenerator(classes=classes,
                                  seq_length=n_timesteps,
                                  sample_step=frame_step,
                                  target_size=input_shape,
                                  batch_size=batch_size,
                                  data_format=data_format,
                                  output_mode='error')
    
    train_generator = train_generator.flow_from_directory(training_data_dir)
    val_generator = val_generator.flow_from_directory(validation_data_dir)
    
    results_dir = utils.get_create_results_dir(config_name, base_results_dir)
    callbacks = get_callbacks(results_dir, stopping_patience)
    
    history = model.fit_generator(train_generator, 
                                  len(train_generator), 
                                  epochs, callbacks=callbacks, 
                                  validation_data=val_generator, 
                                  validation_steps=len(val_generator), 
                                  use_multiprocessing=use_multiprocessing,
                                  max_queue_size=max_queue_size, 
                                  workers=workers)
    
    json_file = os.path.join(results_dir, 'model.json')
    json_string = model.to_json()
    with open(json_file, "w") as f:
        f.write(json_string)
        
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Train PredNet model.')
    parser.add_argument('config', help='experiment config name defined in moments_settings.py')
    FLAGS, unparsed = parser.parse_known_args()
    
    config = configs[FLAGS.config]
    
    print('\n==> Starting experiment: {}\n'.format(config['description']))
    
    train(FLAGS.config, **config)
    utils.save_experiment_config(FLAGS.config, config['base_results_dir'], config)