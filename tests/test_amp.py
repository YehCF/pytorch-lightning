import os

import pytest

import tests.utils as tutils
from pytorch_lightning import Trainer
from pytorch_lightning.testing import (
    LightningTestModel,
)
from pytorch_lightning.utilities.debugging import MisconfigurationException


def test_amp_single_gpu(tmpdir):
    """Make sure DDP + AMP work."""
    tutils.reset_seed()

    if not tutils.can_run_gpu_test():
        return

    hparams = tutils.get_hparams()
    model = LightningTestModel(hparams)

    trainer_options = dict(
        default_save_path=tmpdir,
        show_progress_bar=True,
        max_num_epochs=1,
        gpus=1,
        distributed_backend='ddp',
        use_amp=True
    )

    tutils.run_model_test(trainer_options, model)


def test_no_amp_single_gpu(tmpdir):
    """Make sure DDP + AMP work."""
    tutils.reset_seed()

    if not tutils.can_run_gpu_test():
        return

    hparams = tutils.get_hparams()
    model = LightningTestModel(hparams)

    trainer_options = dict(
        default_save_path=tmpdir,
        show_progress_bar=True,
        max_num_epochs=1,
        gpus=1,
        distributed_backend='dp',
        use_amp=True
    )

    with pytest.raises((MisconfigurationException, ModuleNotFoundError)):
        tutils.run_model_test(trainer_options, model)


def test_amp_gpu_ddp(tmpdir):
    """Make sure DDP + AMP work."""
    if not tutils.can_run_gpu_test():
        return

    tutils.reset_seed()
    tutils.set_random_master_port()

    hparams = tutils.get_hparams()
    model = LightningTestModel(hparams)

    trainer_options = dict(
        default_save_path=tmpdir,
        show_progress_bar=True,
        max_num_epochs=1,
        gpus=2,
        distributed_backend='ddp',
        use_amp=True
    )

    tutils.run_model_test(trainer_options, model)


def test_amp_gpu_ddp_slurm_managed(tmpdir):
    """Make sure DDP + AMP work."""
    if not tutils.can_run_gpu_test():
        return

    tutils.reset_seed()

    # simulate setting slurm flags
    tutils.set_random_master_port()
    os.environ['SLURM_LOCALID'] = str(0)

    hparams = tutils.get_hparams()
    model = LightningTestModel(hparams)

    trainer_options = dict(
        show_progress_bar=True,
        max_num_epochs=1,
        gpus=[0],
        distributed_backend='ddp',
        use_amp=True
    )

    # exp file to get meta
    logger = tutils.get_test_tube_logger(tmpdir, False)

    # exp file to get weights
    checkpoint = tutils.init_checkpoint_callback(logger)

    # add these to the trainer options
    trainer_options['checkpoint_callback'] = checkpoint
    trainer_options['logger'] = logger

    # fit model
    trainer = Trainer(**trainer_options)
    trainer.is_slurm_managing_tasks = True
    result = trainer.fit(model)

    # correct result and ok accuracy
    assert result == 1, 'amp + ddp model failed to complete'

    # test root model address
    assert trainer.resolve_root_node_address('abc') == 'abc'
    assert trainer.resolve_root_node_address('abc[23]') == 'abc23'
    assert trainer.resolve_root_node_address('abc[23-24]') == 'abc23'
    assert trainer.resolve_root_node_address('abc[23-24, 45-40, 40]') == 'abc23'

    # test model loading with a map_location
    pretrained_model = tutils.load_model(logger.experiment, trainer.checkpoint_callback.filepath)

    # test model preds
    for dataloader in trainer.get_test_dataloaders():
        tutils.run_prediction(dataloader, pretrained_model)

    if trainer.use_ddp:
        # on hpc this would work fine... but need to hack it for the purpose of the test
        trainer.model = pretrained_model
        trainer.optimizers, trainer.lr_schedulers = pretrained_model.configure_optimizers()

    # test HPC loading / saving
    trainer.hpc_save(tmpdir, logger)
    trainer.hpc_load(tmpdir, on_gpu=True)

    # test freeze on gpu
    model.freeze()
    model.unfreeze()


def test_cpu_model_with_amp(tmpdir):
    """Make sure model trains on CPU."""
    tutils.reset_seed()

    trainer_options = dict(
        default_save_path=tmpdir,
        show_progress_bar=False,
        logger=tutils.get_test_tube_logger(tmpdir),
        max_num_epochs=1,
        train_percent_check=0.4,
        val_percent_check=0.4,
        use_amp=True
    )

    model, hparams = tutils.get_model()

    with pytest.raises((MisconfigurationException, ModuleNotFoundError)):
        tutils.run_model_test(trainer_options, model, on_gpu=False)


def test_amp_gpu_dp(tmpdir):
    """Make sure DP + AMP work."""
    tutils.reset_seed()

    if not tutils.can_run_gpu_test():
        return

    model, hparams = tutils.get_model()
    trainer_options = dict(
        default_save_path=tmpdir,
        max_num_epochs=1,
        gpus='0, 1',  # test init with gpu string
        distributed_backend='dp',
        use_amp=True
    )
    with pytest.raises(MisconfigurationException):
        tutils.run_model_test(trainer_options, model, hparams)


if __name__ == '__main__':
    pytest.main([__file__])
