#from stuff.run_transnetv2 import TransNetV2
from transnetv2 import TransNetV2

model = TransNetV2()
video_frames, single_frame_predictions, all_frame_predictions = \
    model.predict_video("datasets/videos/batch_2/K17_V001.mp4")

result = model.predictions_to_scenes(single_frame_predictions)

print(result)