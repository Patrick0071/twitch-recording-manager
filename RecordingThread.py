import threading
import subprocess


class RecordingThread(threading.Thread):
    def __init__(self, streamer_name, filename, full_path, thread_finished_callback):
        threading.Thread.__init__(self)
        self.stop_event = threading.Event()
        self.streamer_name = streamer_name
        self.filename = filename
        self.full_path = full_path
        self.thread_finished_callback = thread_finished_callback

    def run(self):
        print(f"starting {self.streamer_name}")
        process = self.start_recording(self.streamer_name, self.full_path)
        # wait while stop is not set AND the process is running
        while not self.stop_event.is_set() and process.poll() is None:
            self.stop_event.wait(1)
        if self.stop_event.is_set():  # if we need to stop, terminate the process
            process.terminate()
        while process.poll is None:  # wait for process to end
            self.stop_event.wait(1)
        print(f"{self.streamer_name} stopping")
        self.thread_finished_callback(self.streamer_name, self.filename, self.full_path)

    @staticmethod
    def start_recording(streamer_name: str, full_path: str):
        params = ["streamlink", "-o", full_path, f"https://www.twitch.tv/{streamer_name}", "best",
                  "--twitch-disable-hosting", "--twitch-disable-ads"]
        return subprocess.Popen(params)
