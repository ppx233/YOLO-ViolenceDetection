# coding:utf-8
from ultralytics import YOLO

# 加载模型
model = YOLO("yolov8x.pt")  # 加载预训练模型
# Use the model
if __name__ == '__main__':
    # Use the model
    results = model.train(data='datasets/fight/data.yaml',
                          epochs=100, batch=16, imgsz=1280, device='cuda', cache=True, workers=4)  # 训练模型
