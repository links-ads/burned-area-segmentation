from typing import Any, Callable

import torch
from torch import nn
from torchmetrics import F1Score, JaccardIndex

from baseg.losses import SoftBCEWithLogitsLoss
from baseg.modules.base import BaseModule


class MultiTaskModule(BaseModule):
    def __init__(
        self,
        config: dict,
        tiler: Callable[..., Any] | None = None,
        predict_callback: Callable[..., Any] | None = None,
    ):
        super().__init__(config, tiler, predict_callback)
        self.criterion_decode = SoftBCEWithLogitsLoss(ignore_index=255)
        self.criterion_auxiliary = nn.CrossEntropyLoss(ignore_index=255)
        num_classes = config["auxiliary_head"]["num_classes"]
        self.train_metrics_aux = nn.ModuleDict(
            {
                "train_f1_aux": F1Score(task="multiclass", ignore_index=255, num_classes=num_classes),
                "train_iou_aux": JaccardIndex(task="multiclass", ignore_index=255, num_classes=num_classes),
            }
        )
        self.val_metrics_aux = nn.ModuleDict(
            {
                "val_f1_aux": F1Score(task="multiclass", ignore_index=255, num_classes=num_classes),
                "val_iou_aux": JaccardIndex(task="multiclass", ignore_index=255, num_classes=num_classes),
            }
        )
        self.test_metrics_aux = nn.ModuleDict(
            {
                "test_f1_aux": F1Score(task="multiclass", ignore_index=255, num_classes=num_classes),
                "test_iou_aux": JaccardIndex(task="multiclass", ignore_index=255, num_classes=num_classes),
            }
        )

    def training_step(self, batch: Any, batch_idx: int):
        x = batch["S2L2A"]
        y_del = batch["DEL"]
        y_lc = batch["ESA_LC"]
        decode_out, auxiliary_out = self.model(x)
        loss_decode = self.criterion_decode(decode_out.squeeze(1), y_del.float())
        loss_auxiliary = self.criterion_auxiliary(auxiliary_out, y_lc.long())
        loss = loss_decode + loss_auxiliary

        self.log("train_loss_del", loss_decode, on_step=True, on_epoch=True, prog_bar=True, logger=True)
        self.log("train_loss_aux", loss_auxiliary, on_step=True, on_epoch=True, prog_bar=True, logger=True)
        self.log("train_loss", loss, on_step=True, on_epoch=True, prog_bar=True, logger=True)
        # compute delineation metrics
        for metric_name, metric in self.train_metrics.items():
            metric(decode_out.squeeze(1), y_del.float())
            self.log(metric_name, metric, on_epoch=True, prog_bar=True)
        # compute auxiliary metrics
        for metric_name, metric in self.train_metrics_aux.items():
            metric(auxiliary_out, y_lc.long())
            self.log(metric_name, metric, on_epoch=True, prog_bar=True)
        return loss

    def validation_step(self, batch: Any, batch_idx: int):
        x = batch["S2L2A"]
        y_del = batch["DEL"]
        y_lc = batch["ESA_LC"]
        decode_out, auxiliary_out = self.model(x)
        loss_decode = self.criterion_decode(decode_out.squeeze(1), y_del.float())
        loss_auxiliary = self.criterion_auxiliary(auxiliary_out, y_lc.long())
        loss = loss_decode + loss_auxiliary

        self.log("val_loss_del", loss_decode, on_step=True, on_epoch=True, prog_bar=True, logger=True)
        self.log("val_loss_aux", loss_auxiliary, on_step=True, on_epoch=True, prog_bar=True, logger=True)
        self.log("val_loss", loss, on_step=True, on_epoch=True, prog_bar=True, logger=True)
        # compute delineation metrics
        for metric_name, metric in self.val_metrics.items():
            metric(decode_out.squeeze(1), y_del.float())
            self.log(metric_name, metric, on_epoch=True, prog_bar=True)
        # compute auxiliary metrics
        for metric_name, metric in self.val_metrics_aux.items():
            metric(auxiliary_out, y_lc.long())
            self.log(metric_name, metric, on_epoch=True, prog_bar=True)
        return loss

    def test_step(self, batch: Any, batch_idx: int):
        x = batch["S2L2A"]
        y_del = batch["DEL"]
        y_lc = batch["ESA_LC"]
        decode_out, auxiliary_out = self.model(x)
        loss_decode = self.criterion_decode(decode_out.squeeze(1), y_del.float())
        loss_auxiliary = self.criterion_auxiliary(auxiliary_out, y_lc.long())
        loss = loss_decode + loss_auxiliary

        self.log("test_loss_del", loss_decode, on_step=True, on_epoch=True, prog_bar=True, logger=True)
        self.log("test_loss_aux", loss_auxiliary, on_step=True, on_epoch=True, prog_bar=True, logger=True)
        self.log("test_loss", loss, on_step=True, on_epoch=True, prog_bar=True, logger=True)
        # compute delineation metrics
        for metric_name, metric in self.test_metrics.items():
            metric(decode_out.squeeze(1), y_del.float())
            self.log(metric_name, metric, on_epoch=True, prog_bar=True)
        # compute auxiliary metrics
        for metric_name, metric in self.test_metrics_aux.items():
            metric(auxiliary_out, y_lc.long())
            self.log(metric_name, metric, on_epoch=True, prog_bar=True)
        return loss

    def predict_step(self, batch: Any, batch_idx: int, dataloader_idx: int = 0) -> Any:
        full_image = batch["S2L2A"]

        def callback(batch: Any):
            del_out, _ = self.model(batch)  # [b, 1, h, w]
            return del_out.squeeze(1)  # [b, h, w]

        full_pred = self.tiler(full_image[0], callback=callback)
        batch["pred"] = torch.sigmoid(full_pred)
        return batch

    def on_predict_batch_end(self, outputs: Any | None, batch: Any, batch_idx: int, dataloader_idx: int) -> None:
        self.predict_callback(batch)