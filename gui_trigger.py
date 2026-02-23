import tkinter as tk
from camera.camera_feed import capture_frame
from analysis.grass_health import analyze_frame


def analyze():
    frame = capture_frame()
    result = analyze_frame(frame)
    print(f"âœ… Analysis result: {result}")


def save_snapshot():
    frame = capture_frame()
    # Save logic here (e.g., cv2.imwrite)
    print("ðŸ’¾ Snapshot saved.")


def refresh_feed():
    print("ðŸ”„ Feed refreshed.")  # Or reload camera stream if applicable


# GUI setup
root = tk.Tk()
root.title("Ingenious Irrigation Control")
root.geometry("300x200")

# Buttons
btn_analyze = tk.Button(root, text="ðŸ” Analyze", command=analyze, width=20)
btn_snapshot = tk.Button(root, text="ðŸ’¾ Save Snapshot",
                         command=save_snapshot, width=20)
btn_refresh = tk.Button(root, text="ðŸ”„ Refresh Feed",
                        command=refresh_feed, width=20)

# Layout
btn_analyze.pack(pady=10)
btn_snapshot.pack(pady=10)
btn_refresh.pack(pady=10)

root.mainloop()