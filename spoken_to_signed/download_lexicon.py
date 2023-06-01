import argparse
import csv
import os
from datetime import datetime
from typing import List, Dict

from pose_format import PoseHeader, Pose
from pose_format.numpy import NumPyPoseBody
from pose_format.utils.reader import BufferReader
from tqdm import tqdm

LEXICON_INDEX = ['path', 'spoken_language', 'signed_language', 'words', 'glosses', 'priority']


def init_index(index_path: str):
    if not os.path.isfile(index_path):
        # Create csv file with specified header
        with open(index_path, 'w', encoding='utf-8', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(LEXICON_INDEX)


def load_signsuisse(directory_path: str) -> List[Dict[str, str]]:
    import tensorflow_datasets as tfds
    # noinspection PyUnresolvedReferences
    import sign_language_datasets.datasets.signsuisse as signsuisse
    # noinspection PyUnresolvedReferences
    from sign_language_datasets.datasets.signsuisse.signsuisse import _POSE_HEADERS
    from sign_language_datasets.datasets.config import SignDatasetConfig

    IANA_TAGS = {
        "ch-de": "sgg",
        "ch-fr": "ssr",
        "ch-it": "slf",
    }

    # for cache busting, we use today's date
    date_str = datetime.now().strftime("%Y-%m-%d")
    config = SignDatasetConfig(name=date_str, version="1.0.0", include_video=False, include_pose="holistic")
    dataset = tfds.load(name='sign_suisse', builder_kwargs={"config": config})

    with open(_POSE_HEADERS["holistic"], "rb") as buffer:
        pose_header = PoseHeader.read(BufferReader(buffer.read()))

    for datum in tqdm(dataset["train"]):
        uid_raw = datum['id'].numpy().decode('utf-8')
        spoken_language = datum['spokenLanguage'].numpy().decode('utf-8')
        signed_language = IANA_TAGS[datum['signedLanguage'].numpy().decode('utf-8')]
        words = datum['name'].numpy().decode('utf-8')

        # Load pose and save to file
        tf_pose = datum['pose']
        fps = int(tf_pose["fps"].numpy())
        pose_body = NumPyPoseBody(fps, tf_pose["data"].numpy(), tf_pose["conf"].numpy())
        pose = Pose(pose_header, pose_body)
        pose_relative_path = os.path.join(signed_language, f"{uid_raw}.pose")
        os.makedirs(os.path.join(directory_path, signed_language), exist_ok=True)
        with open(os.path.join(directory_path, pose_relative_path), "wb") as f:
            pose.write(f)

        yield {
            'path': pose_relative_path,
            'spoken_language': spoken_language,
            'signed_language': signed_language,
            'words': words,
            'glosses': "",
            'priority': "",
        }


def main(name: str, directory: str):
    index_path = os.path.join(directory, 'index.csv')
    os.makedirs(directory, exist_ok=True)
    init_index(index_path)

    data_loaders = {
        'signsuisse': load_signsuisse,
    }
    if name not in data_loaders:
        raise NotImplementedError(f"{name} is unknown.")

    data = data_loaders[name](directory)

    with open(index_path, 'a', encoding='utf-8', newline='') as file:
        writer = csv.writer(file)
        for row in tqdm(data):
            writer.writerow([row[key] for key in LEXICON_INDEX])

    print(f"Added entries to {index_path}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", choices=['signsuisse'], required=True)
    parser.add_argument("--directory", type=str, required=True)
    args = parser.parse_args()

    main(args.name, args.directory)