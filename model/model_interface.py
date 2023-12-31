import inspect
import torch
import importlib
from torch.nn import functional as F
import torch.optim.lr_scheduler as lrs

import pytorch_lightning as pl


class MInterface(pl.LightningModule):
    def __init__(self, model, loss='l2', lr=1.0 * 1e-3, **kargs):
        """
        model: str or model object
        loss: str or configure yourselves
        """
        super().__init__()
        self.save_hyperparameters(ignore=["model"])
        self.model = self.load_model() if isinstance(model, str) else model
        self.configure_loss(loss)

    def forward(self, X, edge_index, edge_weight):
        if edge_weight:
            return self.model(X, edge_index, edge_weight)
        else:
            return self.model(X, edge_index)

    def training_step(self, batch, batch_idx):
        snapshot = batch
        out = self(snapshot.x, snapshot.edge_index, snapshot.edge_attr)
        loss = self.loss_function(out, snapshot.y)

        self.log('MSE loss', loss, on_step=True, on_epoch=True, prog_bar=True)
        return loss

    def validation_step(self, batch, batch_idx):
        snapshot = batch
        out = self(snapshot.x, snapshot.edge_index, snapshot.edge_attr)
        loss = self.loss_function(out, snapshot.y)

        correct_num = sum(label_digit == out_digit).cpu().item()

        self.log('val_loss', loss, on_step=False, on_epoch=True, prog_bar=True)
        self.log('val_acc', correct_num / len(out_digit),
                 on_step=False, on_epoch=True, prog_bar=True)

        return correct_num, len(out_digit)

    def test_step(self, batch, batch_idx):
        # Here we just reuse the validation_step for testing
        return self.validation_step(batch, batch_idx)

    def on_validation_epoch_end(self):
        # Make the Progress Bar leave there
        self.print('')

    def configure_optimizers(self):
        if hasattr(self.hparams, 'weight_decay'):
            weight_decay = self.hparams.weight_decay
        else:
            weight_decay = 0
        optimizer = torch.optim.Adam(
            self.parameters(), lr=self.hparams.lr, weight_decay=weight_decay)

        if not hasattr(self.hparams, 'weight_decay'):
            return optimizer
        else:
            if self.hparams.lr_scheduler == 'step':
                scheduler = lrs.StepLR(optimizer,
                                       step_size=self.hparams.lr_decay_steps,
                                       gamma=self.hparams.lr_decay_rate)
            elif self.hparams.lr_scheduler == 'cosine':
                scheduler = lrs.CosineAnnealingLR(optimizer,
                                                  T_max=self.hparams.lr_decay_steps,
                                                  eta_min=self.hparams.lr_decay_min_lr)
            else:
                raise ValueError('Invalid lr_scheduler type!')
            return [optimizer], [scheduler]

    def configure_loss(self, loss):
        if loss == 'mse':
            self.loss_function = F.mse_loss
        elif loss == 'l1':
            self.loss_function = F.l1_loss
        else:
            raise ValueError("Invalid Loss Type!")

