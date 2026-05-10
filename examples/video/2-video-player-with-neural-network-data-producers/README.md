# Video player on a random video + various neural networks DataProducers

## Usage

```bash
python main.py video.mp4 [--yolo_weight_path model_yolo.ckpt] [--vre_config_path vre_cfg.yaml]
```
## Supported neural networks
- [YOLO](../../../roboimpl/data_producers/object_detection/yolo/yolo_data_producer.py)
    - Any `.pt` file like `yolo11n.pt` (i.e. from [here](https://huggingface.co/Ultralytics/YOLO11/tree/main)) or even [FastSAM-s.pt](https://github.com/ultralytics/assets/releases/download/v8.4.0/FastSAM-s.pt).
- [VRE Repository](../../../roboimpl/data_producers/vre/vre_data_producers.py)
    - Any representation from [VRE Repository](https://gitlab.com/video-representations-extractor/video-representations-extractor/-/blob/master/vre_repository/__init__.py). If you `pip install video-representations-extractor` it should auto-download any weights file from the repository upon usage. We provide a few configs here.

## Controls:
- `ESC` - closes the window
- `SPACE` - pauses or plays the video
- `->` - skips on second ahead
- `<-` - goes one second behind
- `.` - skips one frame ahead
- `,` - skips on frame behind

## Webcam example via ffmpeg + robochan:

```bash
ffmpeg -i https://w3.webcamromania.ro/busteni/index.m3u8 -f rawvideo -pix_fmt rgb24 - | CUDA_VISIBLE_DEVICES=0 VRE_VIDEO_LOGLEVEL=2 ROBOCHAN_LOGLEVEL=2 ROBOIMPL_LOGLEVEL=2 ./main.py - --yolo_weights_path yolo11s.pt --yolo_threshold 0.1 --frame_resolution 800 1280 --fps 30
```
