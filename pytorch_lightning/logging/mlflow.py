"""
Log using `mlflow <https://mlflow.org>'_

.. code-block:: python

    from pytorch_lightning.logging import MLFlowLogger
    mlf_logger = MLFlowLogger(
        experiment_name="default",
        tracking_uri="file:/."
    )
    trainer = Trainer(logger=mlf_logger)


Use the logger anywhere in you LightningModule as follows:

.. code-block:: python

    def train_step(...):
        # example
        self.logger.experiment.whatever_ml_flow_supports(...)

    def any_lightning_module_function_or_hook(...):
        self.logger.experiment.whatever_ml_flow_supports(...)

"""

from logging import getLogger
from time import time

try:
    import mlflow
except ImportError:
    raise ImportError('Missing mlflow package.')

from .base import LightningLoggerBase, rank_zero_only

logger = getLogger(__name__)


class MLFlowLogger(LightningLoggerBase):
    def __init__(self, experiment_name, tracking_uri=None, tags=None):
        super().__init__()
        self.experiment = mlflow.tracking.MlflowClient(tracking_uri)
        self.experiment_name = experiment_name
        self._run_id = None
        self.tags = tags

    @property
    def run_id(self):
        if self._run_id is not None:
            return self._run_id

        experiment = self.experiment.get_experiment_by_name(self.experiment_name)
        if experiment is None:
            logger.warning(
                f"Experiment with name f{self.experiment_name} not found. Creating it."
            )
            self.experiment.create_experiment(self.experiment_name)
            experiment = self.experiment.get_experiment_by_name(self.experiment_name)

        run = self.experiment.create_run(experiment.experiment_id, tags=self.tags)
        self._run_id = run.info.run_id
        return self._run_id

    @rank_zero_only
    def log_hyperparams(self, params):
        for k, v in vars(params).items():
            self.experiment.log_param(self.run_id, k, v)

    @rank_zero_only
    def log_metrics(self, metrics, step_idx=None):
        timestamp_ms = int(time() * 1000)
        for k, v in metrics.items():
            if isinstance(v, str):
                logger.warning(
                    f"Discarding metric with string value {k}={v}"
                )
                continue
            self.experiment.log_metric(self.run_id, k, v, timestamp_ms, step_idx)

    def save(self):
        pass

    @rank_zero_only
    def finalize(self, status="FINISHED"):
        if status == 'success':
            status = 'FINISHED'
        self.experiment.set_terminated(self.run_id, status)

    @property
    def name(self):
        return self.experiment_name

    @property
    def version(self):
        return self._run_id
