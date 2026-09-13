import threading
import subprocess
import os


class RecordingThread(threading.Thread):
    def __init__(self, streamer_name, filename, full_path, twitch_oauth_token, thread_finished_callback):
        threading.Thread.__init__(self)
        self.stop_event = threading.Event()
        self.streamer_name = streamer_name
        self.filename = filename
        self.full_path = full_path          # definitieve .mkv
        self.raw_path = full_path + ".ts"   # ruwe dump van streamlink
        self.twitch_oauth_token = twitch_oauth_token
        self.thread_finished_callback = thread_finished_callback

    def run(self):
        print(f"starting {self.streamer_name}")
        process = self.start_recording(self.streamer_name, self.raw_path, self.twitch_oauth_token)

        # wacht tot stop gezet is OF het proces zelf stopt (stream offline)
        while not self.stop_event.is_set() and process.poll() is None:
            self.stop_event.wait(1)

        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                print(f"{self.streamer_name}: streamlink reageert niet, kill")
                process.kill()
                process.wait()

        print(f"{self.streamer_name} stopping")
        self.remux()
        self.thread_finished_callback(self.streamer_name, self.filename, self.full_path)

    def remux(self):
        """Bouwt container, index en timestamps opnieuw op.
        Geen re-encode: -c copy. Lost gestapelde moov-atoms en
        start-offsets op waar VLC/Jellyfin over struikelen."""
        if not os.path.exists(self.raw_path) or os.path.getsize(self.raw_path) == 0:
            print(f"{self.streamer_name}: geen (bruikbare) opname gevonden op {self.raw_path}")
            return

        params = [
            "ffmpeg", "-hide_banner", "-loglevel", "warning", "-y",
            "-fflags", "+genpts+igndts",
            "-i", self.raw_path,
            "-map", "0",
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            "-f", "matroska",
            self.full_path,
        ]
        print(f"{self.streamer_name}: remuxen naar {self.full_path}")
        result = subprocess.run(params)

        if result.returncode != 0:
            print(f"{self.streamer_name}: remux mislukt (exit {result.returncode}), ruwe opname blijft staan")
            return

        if not self.verify(self.full_path):
            print(f"{self.streamer_name}: verificatie mislukt, ruwe opname blijft staan")
            return

        os.remove(self.raw_path)
        print(f"{self.streamer_name}: klaar")

    @staticmethod
    def verify(path: str):
        """Controleert of het resultaat een leesbare matroska met duration is."""
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "error",
                 "-show_entries", "format=format_name,duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", path],
                capture_output=True, text=True, timeout=120,
            )
        except subprocess.TimeoutExpired:
            return False
        if result.returncode != 0:
            return False
        output = result.stdout.split()
        if len(output) < 2 or "matroska" not in output[0]:
            return False
        try:
            return float(output[1]) > 0
        except ValueError:
            return False

    @staticmethod
    def start_recording(streamer_name: str, raw_path: str, twitch_oauth_token: str):
        params = [
            "streamlink",
            "-o", raw_path,
            f"https://www.twitch.tv/{streamer_name}",
            "1080p60,1080p,720p60,480p30",
            "--twitch-disable-ads",
            "--stream-segment-attempts", "5",
            "--stream-segment-timeout", "15",
        ]
        if twitch_oauth_token != "":
            params.extend([f"--twitch-api-header=Authorization=OAuth {twitch_oauth_token}"])
        return subprocess.Popen(params)
