
import os
import miniaudio
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst
import threading

class AudioEngine:
    def __init__(self):
        Gst.init(None)
        self.playbin = Gst.ElementFactory.make("playbin", "player")
        self.playing = False
        
        bus = self.playbin.get_bus()
        bus.add_signal_watch()
        bus.connect("message::eos", self._on_eos)
        bus.connect("message::error", self._on_error)

    def _on_eos(self, bus, msg):
        self.stop()

    def _on_error(self, bus, msg):
        err, debug = msg.parse_error()
        print(f"Error: {err.message}")
        self.stop()

    def play_data(self, data: bytes):

        # in a GTK app, u might want to use a memory buffer or a temporary file to play raw audio. for simplicity, we are just going to write to a temporary file for GStreamer.
        self.stop()
        
        import tempfile
        self.temp_file = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        self.temp_file.write(data)
        self.temp_file.close()
        
        uri = "file://" + os.path.abspath(self.temp_file.name)
        self.playbin.set_property("uri", uri)
        self.playbin.set_state(Gst.State.PLAYING)
        self.playing = True

    def stop(self):
        if self.playing:
            self.playbin.set_state(Gst.State.NULL)
            self.playing = False
            if hasattr(self, 'temp_file') and os.path.exists(self.temp_file.name):
                try:
                    os.unlink(self.temp_file.name)
                except:
                    pass

    def convert_to_wav(self, mp3_data: bytes, output_path: str):
        decoded = miniaudio.decode(mp3_data)
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        miniaudio.wav_write_file(output_path, decoded)

engine = AudioEngine()

# i was half asleep when writing this so it might be shitty,it should still work tho
