"""video_actions.py - defines all the supported actions of an video player from our generic ones to the video's"""
from pathlib import Path
from robochan import Action
from roboimpl.utils import logger, image_write
from .video_player_env import VideoPlayerEnv

VIDEO_ACTION_NAMES = ["DISCONNECT", "PLAY_PAUSE", "GO_FORWARD", "GO_BACK", "TAKE_SCREENSHOT"]

def video_actions_fn(video_player: VideoPlayerEnv, actions: list[Action], write_path: Path | None = None) -> bool:
    """the actions callback from generic actions to video-specific ones"""
    write_path = write_path or Path.cwd()
    for action in actions:
        logger.debug(f"Action: {action}")
        if action.name == "DISCONNECT":
            video_player.close()
        if action.name == "PLAY_PAUSE":
            video_player.is_paused = not video_player.is_paused
        if action.name == "GO_FORWARD":
            video_player.increment_frame(int(action.parameters[0])) # n frames
        if action.name == "GO_BACK":
            video_player.increment_frame(-int(action.parameters[0])) # n frames
        if action.name == "TAKE_SCREENSHOT":
            image_write(video_player.get_state()["rgb"], pth := f"{write_path}/frame.png")
            logger.debug(f"Stored screenshot at '{pth}'")
    return True
