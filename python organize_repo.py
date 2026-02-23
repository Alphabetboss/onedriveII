from __future__ import annotations
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# --------- mapping: old_name -> new_relative_path ---------
FILE_MAP = {
    # core
    "app.py": "app.py",
    "README.md": "README.md",
    "LICENSE": "LICENSE",
    "requirements.txt": "requirements.txt",
    "sample_payload.json": "data/sample_payload.json",
    "schedule.json": "scheduler/schedule.json",
    "irrigation_log.csv": "data/irrigation_log.csv",
    "data.yaml": "ml/data.yaml",
    "dataset.zip": "ml/dataset.zip",
    "debug_overlay.jpg": "vision/debug_overlay.jpg",
    "debug_report.json": "vision/debug_report.json",
    "test_media.zip": "data/test_media.zip",

    # api
    "irrigation_api.py": "api/irrigation_api.py",
    "health_api.py": "api/health_api.py",
    "teach_api.py": "api/teach_api.py",
    "train_api.py": "api/train_api.py",
    "rag_server.py": "api/rag_server.py",
    "flask_camera_api.py": "api/flask_camera_api.py",
    "flask_yolo_camera_api.py": "api/flask_yolo_camera_api.py",

    # engine / brain
    "ai_brain.py": "engine/ai_brain.py",
    "answer_engine.py": "engine/answer_engine.py",
    "water_adjuster.py": "engine/water_adjuster.py",
    "perdictive_tuner.py": "engine/predictive_tuner.py",
    "post_hydration_test.py": "engine/post_hydration_test.py",

    # hydration
    "hydration_engine.py": "hydration/hydration_engine.py",
    "lawn_health_scoring.txt": "hydration/lawn_health_scoring.txt",

    # vision
    "health_detector.py": "vision/health_detector.py",
    "health_evaluator.py": "vision/health_evaluator.py",
    "green_detector.py": "vision/green_detector.py",
    "capture_and_detect.py": "vision/capture_and_detect.py",
    "yolov8_infer_example.py": "vision/yolov8_infer_example.py",

    # scheduler
    "schedule_manager.py": "scheduler/schedule_manager.py",
    "sprinkler_scheduler.py": "scheduler/sprinkler_scheduler.py",

    # controller / irrigation control
    "control.py": "controller/control.py",
    "relay_controller.py": "controller/relay_controller.py",
    "os_run_zone.py": "controller/os_run_zone.py",
    "pi_garden_retrofit.py": "controller/pi_garden_retrofit.py",
    "springfield_adapter.py": "controller/springfield_adapter.py",
    "gpio_driver.py": "controller/gpio_driver.py",
    "gpio_pulse.py": "controller/gpio_pulse.py",
    "ii_pins.py": "controller/ii_pins.py",
    "ii_config.py": "controller/ii_config.py",

    # hardware / low-level
    "mocgpiocon.py": "hardware/mocgpiocon.py",
    "rf_upload.py": "hardware/rf_upload.py",
    "relay_controller.pi": "hardware/relay_controller.pi",

    # dashboard / UI
    "dashboard.py": "dashboard/dashboard.py",
    "ingenious_irrigation_dashboard.py": "dashboard/ingenious_irrigation_dashboard.py",
    "chat_voice.html": "dashboard/chat_voice.html",

    # assistant / LLM / voice
    "astra_offline.py": "assistant/astra_offline.py",
    "llm_client.py": "assistant/llm_client.py",
    "voice_trainer.py": "assistant/voice_trainer.py",
    "test_voice_trigger.py": "assistant/test_voice_trigger.py",
    "mic_test.py": "assistant/mic_test.py",

    # utils
    "autofix.py": "utils/autofix.py",
    "check_and_fix.py": "utils/check_and_fix.py",
    "organize_project.py": "utils/organize_project.py",
    "find_dups.py": "utils/find_dups.py",
    "make_report.py": "utils/make_report.py",
    "get_model_names.py": "utils/get_model_names.py",
    "weather_override.py": "utils/weather_override.py",
    "notify.py": "utils/notify.py",
    "garden_utils.py": "utils/garden_utils.py",

    # ml / models
    "active_learning_pipeline.py": "ml/active_learning_pipeline.py",
    "download_dataset.py": "ml/download_dataset.py",
    "download_model.py": "ml/download_model.py",
    "yolov8n.onnx": "ml/yolov8n.onnx",
    "yolov8n.pt": "ml/yolov8n.pt",
    "yolov8m.pt": "ml/yolov8m.pt",

    # legacy / experiments
    "ingenious_irrigation_ai.py": "legacy/ingenious_irrigation_ai.py",
    "ingenious_irrigation_ai_logged.cpython-310.pyc": "legacy/ingenious_irrigation_ai_logged.cpython-310.pyc",
    "simdrypat.py": "legacy/simdrypat.py",
    "test_script.py": "legacy/test_script.py",
    "test_onnx_model.py": "legacy/test_onnx_model.py",
    "routes_tech.py": "legacy/routes_tech.py",

    # deployment / powershell
    "ingenious_dashboard_launcher.ps1": "deployment/ingenious_dashboard_launcher.ps1",
    "Connect-Pi.ps1": "deployment/Connect-Pi.ps1",
    "Deploy-ToPi.ps1": "deployment/Deploy-ToPi.ps1",
    "Wire-AdvancedModules.ps1": "deployment/Wire-AdvancedModules.ps1",
    "run_ingenious_helper.ps1": "deployment/run_ingenious_helper.ps1",
    "check_ii_scripts.ps1": "deployment/check_ii_scripts.ps1",
    "check_ii_scripts (2).ps1": "deployment/check_ii_scripts (2).ps1",
    "scripts.zip": "deployment/scripts.zip",

    # misc
    "GPIO_Control_Code.txt": "data/GPIO_Control_Code.txt",
    "Zone control adapter": "legacy/Zone control adapter",
}


def ensure_dirs():
    dirs = {
        "api",
        "engine",
        "hydration",
        "vision",
        "scheduler",
        "controller",
        "hardware",
        "dashboard",
        "assistant",
        "utils",
        "ml",
        "data",
        "legacy",
        "deployment",
    }
    for d in dirs:
        (ROOT / d).mkdir(parents=True, exist_ok=True)


def remove_pyc():
    for path in ROOT.rglob("*.cpython-310.pyc"):
        print(f"Removing {path}")
        try:
            path.unlink()
        except Exception as e:
            print(f"  ! Failed to remove {path}: {e}")


def move_files():
    for src_name, dest_rel in FILE_MAP.items():
        src = ROOT / src_name
        dest = ROOT / dest_rel
        if not src.exists():
            # silent skip if missing
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        print(f"Moving {src_name} -> {dest_rel}")
        try:
            shutil.move(str(src), str(dest))
        except Exception as e:
            print(f"  ! Failed to move {src_name}: {e}")


def main():
    ensure_dirs()
    remove_pyc()
    move_files()
    print("\nDone. Repo reorganized.")


if __name__ == "__main__":
    main()
