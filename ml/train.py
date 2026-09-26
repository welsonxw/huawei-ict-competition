"""Train ResNet9 on a folder-per-class dataset (e.g. chilli leaves from Mendeley Data).

    data/chilli/
      anthracnose/ *.jpg
      cercospora_leaf_spot/
      healthy/
      leaf_curl/
      nutrient_deficiency/

Usage:
    python -m ml.train --data data/chilli --epochs 15 --out ml/weights/chilli_resnet9.pth --version v1

Writes the checkpoint ({state_dict, labels, version}) and appends accuracy to
ml/weights/metrics.json, which the "Model v1 -> v2" panel reads. Add --extra
data/exports/training-set/<crop> to include expert-confirmed scans exported by the app
(scripts/export_training_set.py or GET /api/export/training-set).
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import ConcatDataset, DataLoader, random_split
from torchvision.datasets import ImageFolder

from ml.models.resnet9 import ResNet9
from ml.transforms import inference_transform, train_transform


def evaluate(model, loader, device):
    model.eval()
    correct = total = 0
    with torch.no_grad():
        for x, y in loader:
            pred = model(x.to(device)).argmax(1).cpu()
            correct += (pred == y).sum().item()
            total += y.numel()
    return correct / max(total, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--extra", help="optional extra folder-per-class dataset (same class names)")
    ap.add_argument("--crop", default="chilli")
    ap.add_argument("--epochs", type=int, default=15)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--lr", type=float, default=0.01)
    ap.add_argument("--val-split", type=float, default=0.2)
    ap.add_argument("--out", default="ml/weights/chilli_resnet9.pth")
    ap.add_argument("--version", default="v1")
    ap.add_argument("--metrics", default="ml/weights/metrics.json")
    args = ap.parse_args()

    base = ImageFolder(args.data)
    labels = base.classes
    n_val = int(len(base) * args.val_split)
    gen = torch.Generator().manual_seed(42)
    train_idx, val_idx = random_split(range(len(base)), [len(base) - n_val, n_val], generator=gen)
    train_ds = torch.utils.data.Subset(ImageFolder(args.data, transform=train_transform), list(train_idx))
    val_ds = torch.utils.data.Subset(ImageFolder(args.data, transform=inference_transform), list(val_idx))
    if args.extra:
        extra = ImageFolder(args.extra, transform=train_transform)
        if extra.classes != labels:
            raise SystemExit(f"--extra classes {extra.classes} differ from {labels}")
        train_ds = ConcatDataset([train_ds, extra])

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = ResNet9(3, len(labels)).to(device)
    train_dl = DataLoader(train_ds, batch_size=args.batch, shuffle=True, num_workers=2)
    val_dl = DataLoader(val_ds, batch_size=args.batch, num_workers=2)
    opt = torch.optim.Adam(model.parameters(), lr=args.lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, args.lr, epochs=args.epochs, steps_per_epoch=len(train_dl))
    loss_fn = nn.CrossEntropyLoss()

    best = 0.0
    for epoch in range(args.epochs):
        model.train()
        for x, y in train_dl:
            opt.zero_grad()
            loss = loss_fn(model(x.to(device)), y.to(device))
            loss.backward()
            nn.utils.clip_grad_value_(model.parameters(), 0.1)
            opt.step()
            sched.step()
        acc = evaluate(model, val_dl, device)
        print(f"epoch {epoch + 1}/{args.epochs} val_acc={acc:.4f}")
        if acc >= best:
            best = acc
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            torch.save({"state_dict": model.state_dict(), "labels": labels, "version": f"{args.crop}-resnet9-{args.version}"}, args.out)

    metrics_path = Path(args.metrics)
    metrics = json.loads(metrics_path.read_text()) if metrics_path.exists() else {"runs": []}
    metrics["runs"].append({
        "crop": args.crop, "version": args.version, "val_accuracy": round(best, 4),
        "train_size": len(train_ds), "val_size": len(val_ds), "classes": labels,
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })
    metrics_path.write_text(json.dumps(metrics, indent=2))
    print(f"best val_acc={best:.4f}; wrote {args.out} and {metrics_path}")


if __name__ == "__main__":
    main()
