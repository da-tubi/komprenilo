#  Copyright 2021 Rikai Authors
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import logging
import os
import random
import string
import uuid
import warnings
import sklearn
from pathlib import Path
from urllib.parse import urlparse

warnings.filterwarnings("ignore", category=DeprecationWarning)  # noqa

# Third Party
import mlflow
import pytest
from mlflow.tracking import MlflowClient
from pyspark.sql import Row, SparkSession

import rikai
from liga.mlflow.registry import CONF_MLFLOW_TRACKING_URI
from rikai.spark.utils import get_default_jar_version, init_spark_session


@pytest.fixture(scope="session")
def mlflow_client_with_tracking_uri(tmp_path_factory) -> (MlflowClient, str):
    tmp_path = tmp_path_factory.mktemp("mlflow")
    tmp_path.mkdir(parents=True, exist_ok=True)
    tracking_uri = "sqlite:///" + str(tmp_path / "tracking.db")
    mlflow.set_tracking_uri(tracking_uri)

    return mlflow.tracking.MlflowClient(tracking_uri), tracking_uri


@pytest.fixture(scope="session")
def mlflow_client(mlflow_client_with_tracking_uri):
    return mlflow_client_with_tracking_uri[0]


@pytest.fixture(scope="session")
def mlflow_tracking_uri(mlflow_client_with_tracking_uri):
    return mlflow_client_with_tracking_uri[1]


@pytest.fixture(scope="module")
def spark(mlflow_tracking_uri: str, tmp_path_factory) -> SparkSession:
    print(f"mlflow tracking uri for spark: ${mlflow_tracking_uri}")
    warehouse_path = tmp_path_factory.mktemp("warehouse")
    rikai_version = get_default_jar_version(use_snapshot=True)

    return init_spark_session(
        dict(
            [
                ("spark.port.maxRetries", 128),
                ("spark.sql.warehouse.dir", str(warehouse_path)),
                (
                    "spark.rikai.sql.ml.registry.test.impl",
                    "ai.eto.rikai.sql.model.testing.TestRegistry",
                ),
                (
                    CONF_MLFLOW_TRACKING_URI,
                    mlflow_tracking_uri,
                ),
                (
                    "spark.rikai.sql.ml.catalog.impl",
                    "ai.eto.rikai.sql.model.SimpleCatalog",
                ),
            ]
        ),
        jar_type="local",
    )


@pytest.fixture
def asset_path() -> Path:
    return Path(__file__).parent / "assets"


@pytest.fixture(scope="session")
def resnet_model_uri(tmp_path_factory):
    from sklearn.datasets import load_diabetes

    X, y = load_diabetes(return_X_y=True)
    (X.shape, y.shape)
    import getpass

    import mlflow
    from liga.sklearn.mlflow import log_model
    from sklearn.linear_model import LinearRegression

    mlflow_tracking_uri = "sqlite:///mlruns.db"
    mlflow.set_tracking_uri(mlflow_tracking_uri)

    # train a model
    model = LinearRegression()
    with mlflow.start_run() as run:
        ####
        # Part 1: Train the model and register it on MLflow
        ####
        model.fit(X, y)

        registered_model_name = f"{getpass.getuser()}_sklearn_lr"
        log_model(model, registered_model_name)

    # Prepare model
    # tmp_path = tmp_path_factory.mktemp(str(uuid.uuid4()))
    # resnet = sklearn.models.detection.fasterrcnn_resnet50_fpn(
    #     pretrained=True,
    #     progress=False,
    # )
    # model_uri = tmp_path / "resnet.pth"
    # sklearn.save(resnet, model_uri)
    # return model_uri


@pytest.fixture
def s3_tmpdir() -> str:
    """Create a temporary S3 directory to test dataset.

    To enable s3 test, it requires both the AWS credentials,
    as well as `RIKAI_TEST_S3_URL` being set.
    """
    baseurl = os.environ.get("RIKAI_TEST_S3_URL", None)
    if baseurl is None:
        pytest.skip("Skipping test. RIKAI_TEST_S3_URL is not set")
    parsed = urlparse(baseurl)
    if parsed.scheme != "s3":
        raise ValueError("RIKAI_TEST_S3_URL must be a valid s3:// URL.")

    try:
        import boto3
        import botocore

        sts = boto3.client("sts")
        try:
            sts.get_caller_identity()
        except botocore.exceptions.ClientError:
            pytest.skip("AWS client can not be authenticated.")
    except ImportError:
        pytest.skip("Skip test, rikai[aws] (boto3) is not installed")

    temp_dir = (
        baseurl
        + "/"
        + "".join(random.choices(string.ascii_letters + string.digits, k=6))
    )
    yield temp_dir

    from pyarrow.fs import S3FileSystem

    s3fs = S3FileSystem()
    s3fs_path = urlparse(temp_dir)._replace(scheme="").geturl()
    try:
        s3fs.rm(s3fs_path, recursive=True)
    except Exception:
        logging.warn("Could not delete directory: %s", s3fs_path)


@pytest.fixture
def gcs_tmpdir() -> str:
    """Create a temporary Google Cloud Storage (GCS) directory to test dataset.

    To enable GCS test, it requires both the GCS credentials,
    as well as `RIKAI_TEST_GCS_URL` being set.

    Examples
    --------

    .. code-block:: bash

        $ export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
        $ export RIKAI_TEST_GCS_URL=gs://bucket
        $ pytest python/tests

    References
    ----------
    https://cloud.google.com/dataproc/docs/concepts/connectors/cloud-storage
    https://cloud.google.com/dataproc/docs/concepts/iam/iam
    """

    base_url = os.environ.get("RIKAI_TEST_GCS_URL", None)
    if base_url is None:
        pytest.skip("Skipping test. RIKAI_TEST_GCS_URL is not set")
    parsed = urlparse(base_url)
    if parsed.scheme != "gs":
        raise ValueError("RIKAI_TEST_GCS_URL must be a valid gs:// URL")

    fs = None
    try:
        import gcsfs

        fs = gcsfs.GCSFileSystem()
        try:
            fs.ls(parsed.netloc)
        except gcsfs.retry.HttpError as he:
            if he.code == 401:
                pytest.skip(
                    "Skipping test. Google Cloud Credentials are not set up."
                )
            else:
                raise
    except ImportError:
        pytest.skip("rikai[gcp] is not installed.")

    temp_dir = (
        base_url
        + "/"
        + "".join(random.choices(string.ascii_letters + string.digits, k=6))
    )
    yield temp_dir

    assert fs is not None, "gcsfs must be initialized by now."
    parsed = urlparse(temp_dir)
    gcsfs_path = parsed._replace(scheme="").geturl()  # Erase scheme
    try:
        # Best effort to clean temp data
        fs.rm(gcsfs_path, recursive=True)
    except Exception:
        logging.error("Could not delete directory: %s", gcsfs_path)
