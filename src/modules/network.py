import Algorithmia
from time import sleep
from requests.exceptions import ConnectionError
import torch
import zipfile
import json
from src.modules.forecast_model import ForecastModel
from uuid import uuid4

client = Algorithmia.client()

MODEL_FILE_NAME = 'model_architecture.pb'
META_DATA_FILE_NAME = 'meta_data.json'


class AlgorithmError(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


r"""
Our model state is preserved in two files:
- The serialized torch graph representing the model called 'model_architecture.pb'
- A meta data file containing other information such as architecture and information around training, called 'meta_data.json'

"""

def get_model_package(remote_package_path: str):
    local_file_path = get_data(remote_package_path)
    model_file, meta_data_file = unzip(local_file_path)
    model = torch.jit.load(model_file)
    meta_data = json.loads(meta_data_file.read().decode('utf-8'))
    return model, meta_data

def save_model_package(model: ForecastModel, meta_data: dict, remote_file_path: str):
    file_paths = list()
    file_paths.append(save_model(model))
    file_paths.append(save_metadata(meta_data))
    local_zip_arch = zip(file_paths)
    output_path = put_file(local_zip_arch, remote_file_path)
    return output_path



def get_data(remote_file_path: str):
    try:
        result = client.file(remote_file_path).getFile().name
    except ConnectionError:
        result = get_data(remote_file_path)
    return result


def put_file(local_path: str, remote_path: str):
    try:
        client.file(remote_path).putFile(local_path)
    except ConnectionError:
        sleep(5)
        return put_file(local_path, remote_path)
    return remote_path


def unzip(local_path: str):
    archive = zipfile.ZipFile(local_path, 'r')
    model_binary = archive.open(MODEL_FILE_NAME)
    meta_data_binary = archive.open(META_DATA_FILE_NAME)
    return model_binary, meta_data_binary


def zip(file_paths: list):
    filename = "/tmp/{}.zip".format(str(uuid4()))
    archive = zipfile.ZipFile(filename, 'w')
    for path in file_paths:
        archive.write(path, arcname=path.split('/')[-1])
    archive.close()
    return filename




def save_model(model: torch.jit.ScriptModule):
    local_file_path = "/tmp/{}".format(MODEL_FILE_NAME)
    model.save(local_file_path)
    return local_file_path


def save_metadata(data: dict):
    local_file_path = "/tmp/{}".format(META_DATA_FILE_NAME)
    with open(local_file_path, 'w') as f:
        json.dump(data, f)
    return local_file_path

def load_json(file_path: str):
    with open(file_path, 'r') as f:
        data = json.load(f)
    return data