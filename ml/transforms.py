import torchvision.transforms as T

IMAGE_SIZE = 256

# The published AgriTech weights were trained on raw [0, 1] tensors (no ImageNet normalisation).
inference_transform = T.Compose([T.Resize((IMAGE_SIZE, IMAGE_SIZE)), T.ToTensor()])

train_transform = T.Compose(
    [
        T.RandomResizedCrop(IMAGE_SIZE, scale=(0.7, 1.0)),
        T.RandomHorizontalFlip(),
        T.RandomRotation(15),
        T.ColorJitter(0.2, 0.2, 0.2),
        T.ToTensor(),
    ]
)
