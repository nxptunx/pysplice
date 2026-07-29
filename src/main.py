
import gi
import sys
import threading
import os
import requests
import time
import re
from concurrent.futures import ThreadPoolExecutor

try:
    gi.require_version('Gtk', '4.0')
    gi.require_version('Adw', '1')
    from gi.repository import Gtk, Adw, Gdk, GLib, Gio, GdkPixbuf
except (ValueError, ImportError) as e:
    print(f"Error: Could not find GTK4/Adwaita. Please install the necessary packages.\nOriginal error: {e}")
    sys.exit(1)

from .splice_api import search_samples, search_packs
from .splice_decoder import decode_splice_audio
from .config import config
from .audio_engine import engine

def get_safe_path(base_dir, pack_name, sample_name):
    safe_pack = re.sub(r'[<>:"|?*]', '_', pack_name).replace("/", "_").strip()
    parts = sample_name.split('/')
    safe_parts = [re.sub(r'[<>:"|?*]', '_', p).strip() for p in parts]
    
    if safe_parts and not safe_parts[-1].lower().endswith(".wav"):
        if safe_parts[-1].lower().endswith(".mp3"):
            safe_parts[-1] = safe_parts[-1][:-4]
        safe_parts[-1] += ".wav"
        
    return os.path.join(base_dir, safe_pack, *safe_parts)

class KeySelectionPopover(Gtk.Popover):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self.selected_key = None
        self.selected_chord = None
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        vbox.set_margin_top(12); vbox.set_margin_bottom(12); vbox.set_margin_start(12); vbox.set_margin_end(12)
        self.set_child(vbox)
        grid = Gtk.Grid(); grid.set_column_spacing(6); grid.set_row_spacing(6); vbox.append(grid)
        sharps = [("C#", "C♯"), ("D#", "D♯"), (None, ""), ("F#", "F♯"), ("G#", "G♯"), ("A#", "A♯")]
        naturals = [("C", "C"), ("D", "D"), ("E", "E"), ("F", "F"), ("G", "G"), ("A", "A"), ("B", "B")]
        self.key_buttons = {}
        for i, (val, label) in enumerate(sharps):
            if val:
                btn = Gtk.Button(label=label); btn.connect("clicked", self.on_key_clicked, val)
                grid.attach(btn, i, 0, 1, 1); self.key_buttons[val] = btn
        for i, (val, label) in enumerate(naturals):
            btn = Gtk.Button(label=label); btn.connect("clicked", self.on_key_clicked, val)
            grid.attach(btn, i, 1, 1, 1); self.key_buttons[val] = btn
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6); vbox.append(hbox)
        self.major_btn = Gtk.Button(label="Major", hexpand=True); self.major_btn.connect("clicked", self.on_chord_clicked, "major"); hbox.append(self.major_btn)
        self.minor_btn = Gtk.Button(label="Minor", hexpand=True); self.minor_btn.connect("clicked", self.on_chord_clicked, "minor"); hbox.append(self.minor_btn)
        clear_btn = Gtk.Button(label="Clear", has_frame=False); clear_btn.connect("clicked", self.on_clear_clicked); vbox.append(clear_btn)

    def on_key_clicked(self, btn, val):
        self.selected_key = None if self.selected_key == val else val
        self.update_ui(); self.callback(self.selected_key, self.selected_chord)

    def on_chord_clicked(self, btn, val):
        self.selected_chord = None if self.selected_chord == val else val
        self.update_ui(); self.callback(self.selected_key, self.selected_chord)

    def on_clear_clicked(self, btn):
        self.selected_key = self.selected_chord = None
        self.update_ui(); self.callback(None, None)

    def update_ui(self):
        for val, btn in self.key_buttons.items():
            if val == self.selected_key: btn.add_css_class("suggested-action")
            else: btn.remove_css_class("suggested-action")
        self.major_btn.add_css_class("suggested-action") if self.selected_chord == "major" else self.major_btn.remove_css_class("suggested-action")
        self.minor_btn.add_css_class("suggested-action") if self.selected_chord == "minor" else self.minor_btn.remove_css_class("suggested-action")

class BPMPopover(Gtk.Popover):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self.mode = "exact"
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        vbox.set_margin_top(12); vbox.set_margin_bottom(12); vbox.set_margin_start(12); vbox.set_margin_end(12)
        self.set_child(vbox)
        self.exact_radio = Gtk.CheckButton(label="Exact")
        self.range_radio = Gtk.CheckButton(label="Range"); self.range_radio.set_group(self.exact_radio)
        self.exact_radio.set_active(True); self.exact_radio.connect("toggled", self.on_mode_changed)
        mode_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12); mode_box.append(self.exact_radio); mode_box.append(self.range_radio); vbox.append(mode_box)
        self.stack = Gtk.Stack(); vbox.append(self.stack)
        self.exact_entry = Gtk.Entry(placeholder_text="BPM"); self.exact_entry.connect("changed", self.on_changed); self.stack.add_named(self.exact_entry, "exact")
        range_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.min_entry = Gtk.Entry(placeholder_text="Min", width_chars=5); self.max_entry = Gtk.Entry(placeholder_text="Max", width_chars=5)
        self.min_entry.connect("changed", self.on_changed); self.max_entry.connect("changed", self.on_changed)
        range_box.append(self.min_entry); range_box.append(Gtk.Label(label="to")); range_box.append(self.max_entry)
        self.stack.add_named(range_box, "range")

    def on_mode_changed(self, btn):
        self.mode = "exact" if self.exact_radio.get_active() else "range"
        self.stack.set_visible_child_name(self.mode); self.on_changed()

    def on_changed(self, *args):
        if self.mode == "exact": self.callback(self.mode, self.exact_entry.get_text(), None, None)
        else: self.callback(self.mode, None, self.min_entry.get_text(), self.max_entry.get_text())

class SampleRow(Gtk.Box):
    def __init__(self, sample, playback_manager):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.sample = sample; self.pm = playback_manager; self.decoded_data = None
        self.set_margin_start(12); self.set_margin_end(12); self.set_margin_top(4); self.set_margin_bottom(4)
        self.cover_img = Gtk.Image(); self.cover_img.set_pixel_size(32); self.cover_img.add_css_class("pack-cover"); self.append(self.cover_img); self.load_cover()
        self.play_btn = Gtk.Button.new_from_icon_name("media-playback-start-symbolic")
        self.play_btn.add_css_class("circular"); self.play_btn.connect("clicked", self.on_play_clicked); self.append(self.play_btn)
        info_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True); self.append(info_vbox)
        name_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6); info_vbox.append(name_box)
        name_label = Gtk.Label(label=sample['name'], xalign=0, ellipsize=3); name_box.append(name_label)
        type_label = Gtk.Label(label=f"({sample.get('asset_category_slug', 'sample')})"); type_label.add_css_class("dim-label"); name_box.append(type_label)
        tag_box = Gtk.FlowBox(); tag_box.set_selection_mode(Gtk.SelectionMode.NONE); tag_box.set_max_children_per_line(10); info_vbox.append(tag_box)
        for tag in sample.get('tags', [])[:5]:
            label = Gtk.Label(label=tag['label'], margin_start=6, margin_end=6)
            frame = Gtk.Frame(child=label); frame.add_css_class("tag-chip"); tag_box.append(frame)
        meta_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12); self.append(meta_hbox)
        if sample.get('key'): meta_hbox.append(Gtk.Label(label=f"Key: {sample['key']} {(sample.get('chord_type') or '').capitalize()}"))
        if sample.get('bpm'): meta_hbox.append(Gtk.Label(label=f"{sample['bpm']} BPM"))
        if sample.get('duration'): meta_hbox.append(Gtk.Label(label=f"{(sample['duration']/1000):.1f}s"))
        self.dl_btn = Gtk.Button(icon_name="folder-download-symbolic")
        self.dl_btn.set_valign(Gtk.Align.CENTER); self.dl_btn.connect("clicked", self.on_manual_download); self.append(self.dl_btn)
        self.drag_source = Gtk.DragSource(); self.drag_source.connect("prepare", self.on_drag_prepare); self.add_controller(self.drag_source)

    def load_cover(self):
        parents = self.sample.get('parents', {}).get('items', [])
        cover_url = next((f['url'] for f in parents[0].get('files', []) if f['asset_file_type_slug'] == 'cover_image'), None) if parents else None
        if not cover_url: return
        def worker():
            try:
                resp = requests.get(cover_url, timeout=5); loader = GdkPixbuf.PixbufLoader(); loader.write(resp.content); loader.close()
                pixbuf = loader.get_pixbuf()
                GLib.idle_add(lambda: self.cover_img.set_from_pixbuf(pixbuf.scale_simple(32, 32, GdkPixbuf.InterpType.BILINEAR)))
            except: pass
        threading.Thread(target=worker, daemon=True).start()

    def on_play_clicked(self, btn):
        if self.pm.current_row == self and engine.playing: engine.stop(); self.set_playing_ui(False); return
        self.pm.stop_current(); self.pm.current_row = self
        def play():
            data = self.ensure_decoded()
            if data: GLib.idle_add(self.set_playing_ui, True); engine.play_data(data)
        threading.Thread(target=play, daemon=True).start()

    def set_playing_ui(self, playing):
        self.play_btn.set_icon_name("media-playback-stop-symbolic" if playing else "media-playback-start-symbolic")

    def ensure_decoded(self):
        if self.decoded_data: return self.decoded_data
        preview_file = next((f for f in self.sample['files'] if f['asset_file_type_slug'] == 'preview_mp3'), None)
        if preview_file:
            try:
                r = requests.get(preview_file['url'], timeout=10)
                decoded = bytes(decode_splice_audio(r.content))
                self.decoded_data = decoded; return self.decoded_data
            except Exception as e:
                print(f"Error decoding: {e}"); return None
        return None

    def on_manual_download(self, btn):
        parents = self.sample.get('parents', {}).get('items', [])
        pack_name = parents[0].get('name', 'Unknown Pack') if parents else "Unknown Pack"
        dialog = Gtk.FileDialog(initial_name=f"{self.sample['name'].split('/')[-1]}.wav")
        dialog.save(None, None, self.do_manual_save, pack_name)

    def do_manual_save(self, dialog, result, pack_name):
        try:
            file = dialog.save_finish(result); path = file.get_path()
            def worker():
                data = self.ensure_decoded()
                if data: engine.convert_to_wav(data, path)
            threading.Thread(target=worker, daemon=True).start()
        except: pass

    def on_drag_prepare(self, source, x, y):
        data = self.ensure_decoded()
        if not data: return None
        parents = self.sample.get('parents', {}).get('items', [])
        pack_name = parents[0].get('name', 'Unknown Pack') if parents else "Unknown Pack"
        full_path = get_safe_path(config.get()['sampleDir'], pack_name, self.sample['name'])
        engine.convert_to_wav(data, full_path)
        return Gdk.ContentProvider.new_for_value(Gio.File.new_for_path(full_path))

class PackRow(Gtk.Box):
    def __init__(self, pack, app):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.pack = pack; self.app = app
        self.set_margin_start(12); self.set_margin_end(12); self.set_margin_top(8); self.set_margin_bottom(8)
        self.cover_img = Gtk.Image(); self.cover_img.set_pixel_size(64); self.cover_img.add_css_class("pack-cover"); self.append(self.cover_img); self.load_cover()
        info_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True); self.append(info_vbox)
        name_label = Gtk.Label(label=pack['name'], xalign=0, ellipsize=3); name_label.add_css_class("heading"); info_vbox.append(name_label)
        meta = f"{pack.get('main_genre') or 'Unknown Genre'}"
        counts = pack.get('child_asset_counts', [])
        samples_count = next((c['count'] for c in counts if c['type'] == 'sample'), 0)
        meta += f" • {samples_count} samples"
        meta_label = Gtk.Label(label=meta, xalign=0); meta_label.add_css_class("dim-label"); info_vbox.append(meta_label)
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6, valign=Gtk.Align.CENTER)
        view_btn = Gtk.Button(label="View Samples"); view_btn.connect("clicked", self.on_view_clicked); btn_box.append(view_btn)
        dl_btn = Gtk.Button(icon_name="folder-download-symbolic"); dl_btn.add_css_class("suggested-action"); dl_btn.connect("clicked", self.on_download_clicked); btn_box.append(dl_btn)
        self.append(btn_box)

    def load_cover(self):
        cover_url = next((f['url'] for f in self.pack.get('files', []) if f['asset_file_type_slug'] == 'cover_image'), None)
        if not cover_url: return
        def worker():
            try:
                resp = requests.get(cover_url, timeout=5); loader = GdkPixbuf.PixbufLoader(); loader.write(resp.content); loader.close()
                pixbuf = loader.get_pixbuf()
                GLib.idle_add(lambda: self.cover_img.set_from_pixbuf(pixbuf.scale_simple(64, 64, GdkPixbuf.InterpType.BILINEAR)))
            except: pass
        threading.Thread(target=worker, daemon=True).start()

    def on_view_clicked(self, btn): self.app.view_pack_samples(self.pack)
    def on_download_clicked(self, btn): self.app.bulk_download_pack(self.pack)

class PlaybackManager:
    def __init__(self): self.current_row = None
    def stop_current(self):
        if self.current_row: self.current_row.set_playing_ui(False)
        engine.stop()

class pyspliceApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.github.nxptunx.pysplice")
        self.pm = PlaybackManager(); self.search_timer = None; self.search_mode = "samples"
        self.current_filters = {"key": None, "chord_type": None, "bpm": None, "min_bpm": None, "max_bpm": None, "type": "any", "sort": "relevance", "tags": []}
        self.decode_semaphore = threading.Semaphore(4)

    def do_activate(self):
        self.win = Adw.ApplicationWindow(application=self, title="pysplice", default_width=1000, default_height=800)
        self.main_stack = Gtk.Stack(); self.win.set_content(self.main_stack)
        search_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL); self.main_stack.add_named(search_vbox, "search")
        header = Adw.HeaderBar(); search_vbox.append(header)
        self.mode_toggle = Gtk.ToggleButton(label="Packs"); self.mode_toggle.connect("toggled", self.on_mode_toggled); header.pack_start(self.mode_toggle)
        self.search_entry = Gtk.SearchEntry(placeholder_text="Search...", hexpand=True); self.search_entry.connect("search-changed", self.trigger_search); header.set_title_widget(self.search_entry)
        self.loading_spinner = Gtk.Spinner(); header.pack_start(self.loading_spinner)
        settings_btn = Gtk.Button.new_from_icon_name("emblem-system-symbolic"); settings_btn.connect("clicked", self.show_preferences); header.pack_end(settings_btn)
        self.f_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6, margin_top=6, margin_bottom=6, margin_start=12, margin_end=12); search_vbox.append(self.f_hbox)
        self.sort_combo = Gtk.DropDown.new_from_strings(["Most relevant", "Most popular", "Most recent", "Random"]); self.sort_combo.connect("notify::selected", self.trigger_search); self.f_hbox.append(self.sort_combo)
        self.sample_filters = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.key_btn = Gtk.MenuButton(label="Key", popover=KeySelectionPopover(self.on_key_selected)); self.sample_filters.append(self.key_btn)
        self.bpm_btn = Gtk.MenuButton(label="BPM", popover=BPMPopover(self.on_bpm_selected)); self.sample_filters.append(self.bpm_btn)
        self.type_combo = Gtk.DropDown.new_from_strings(["Any", "One-Shots", "Loops"]); self.type_combo.connect("notify::selected", self.trigger_search); self.sample_filters.append(self.type_combo)
        self.f_hbox.append(self.sample_filters)
        scrolled = Gtk.ScrolledWindow(vexpand=True); search_vbox.append(scrolled)
        self.results_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE); scrolled.set_child(self.results_list)
        self.pack_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL); self.main_stack.add_named(self.pack_vbox, "pack_view")
        pack_header = Adw.HeaderBar(); self.pack_vbox.append(pack_header)
        back_btn = Gtk.Button.new_from_icon_name("go-previous-symbolic"); back_btn.connect("clicked", lambda _: self.main_stack.set_visible_child_name("search")); pack_header.pack_start(back_btn)
        self.pack_title = Gtk.Label(label="", hexpand=True, ellipsize=3); pack_header.set_title_widget(self.pack_title)
        self.pack_dl_btn = Gtk.Button(label="Download All", icon_name="folder-download-symbolic"); self.pack_dl_btn.add_css_class("suggested-action"); pack_header.pack_end(self.pack_dl_btn)
        pack_scrolled = Gtk.ScrolledWindow(vexpand=True); self.pack_vbox.append(pack_scrolled)
        self.pack_samples_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE); pack_scrolled.set_child(self.pack_samples_list)
        provider = Gtk.CssProvider(); provider.load_from_data(b".heading { font-weight: bold; font-size: 1.1em; } .dim-label { opacity: 0.6; font-size: 0.8em; } .tag-chip { border-radius: 12px; background: alpha(@theme_fg_color, 0.1); border: none; font-size: 0.8em; } .pack-cover { border-radius: 4px; }")
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.win.present()

    def on_mode_toggled(self, btn):
        self.search_mode = "packs" if btn.get_active() else "samples"
        self.sample_filters.set_visible(not btn.get_active()); self.trigger_search()

    def on_key_selected(self, key, chord):
        self.current_filters["key"] = key; self.current_filters["chord_type"] = chord
        self.key_btn.set_label(f"{key or ''} {(chord or '').capitalize()}".strip() or "Key"); self.trigger_search()

    def on_bpm_selected(self, mode, exact, min_b, max_b):
        self.current_filters.update({"bpm": exact, "min_bpm": int(min_b) if min_b else None, "max_bpm": int(max_b) if max_b else None})
        self.bpm_btn.set_label(f"{exact} BPM" if mode == "exact" and exact else f"{min_b}-{max_b} BPM" if mode == "range" and min_b and max_b else "BPM"); self.trigger_search()

    def trigger_search(self, *args):
        if self.search_timer: GLib.source_remove(self.search_timer)
        self.search_timer = GLib.timeout_add(300, self.do_search)

    def do_search(self):
        self.search_timer = None; query = self.search_entry.get_text()
        sort_val = ["relevance", "popularity", "recency", "random"][self.sort_combo.get_selected()]
        self.loading_spinner.start()
        def run():
            try:
                if self.search_mode == "samples":
                    r = search_samples(query, sort=sort_val, sample_type=["any", "oneshot", "loop"][self.type_combo.get_selected()], **{k: v for k, v in self.current_filters.items() if k not in ["type", "sort"]})
                    items = r.get("data", {}).get("assetsSearch", {}).get("items", [])
                    GLib.idle_add(self.update_results, items, "sample")
                else:
                    r = search_packs(query, sort=sort_val)
                    items = r.get("data", {}).get("assetsSearch", {}).get("items", [])
                    GLib.idle_add(self.update_results, items, "pack")
            except Exception as e: print(f"Search error: {e}"); GLib.idle_add(self.loading_spinner.stop)
        threading.Thread(target=run, daemon=True).start(); return False

    def update_results(self, items, mode):
        while row := self.results_list.get_first_child(): self.results_list.remove(row)
        for item in items: self.results_list.append(SampleRow(item, self.pm) if mode == "sample" else PackRow(item, self))
        self.loading_spinner.stop(); return False

    def view_pack_samples(self, pack):
        self.pack_title.set_label(pack['name']); self.main_stack.set_visible_child_name("pack_view")
        try: self.pack_dl_btn.disconnect_by_func(self.bulk_download_pack)
        except: pass
        self.pack_dl_btn.connect("clicked", lambda _: self.bulk_download_pack(pack))
        while row := self.pack_samples_list.get_first_child(): self.pack_samples_list.remove(row)
        def run():
            try:
                r = search_samples("", parent_uuid=pack['uuid']); items = r.get("data", {}).get("assetsSearch", {}).get("items", [])
                GLib.idle_add(lambda: [self.pack_samples_list.append(SampleRow(item, self.pm)) for item in items])
            except Exception as e: print(f"Pack view error: {e}")
        threading.Thread(target=run, daemon=True).start()

    def bulk_download_pack(self, pack):
        def worker():
            print(f"[BULK] Fetching metadata for pack: {pack['name']}")
            page, all_samples = 1, []
            while True:
                r = search_samples("", page=page, parent_uuid=pack['uuid'])
                items = r.get("data", {}).get("assetsSearch", {}).get("items", [])
                if not items: break
                all_samples.extend(items); page += 1
                pm = r.get("data", {}).get("assetsSearch", {}).get("pagination_metadata", {})
                if page > pm.get("totalPages", 1): break
            
            total = len(all_samples); base_dir = config.get()['sampleDir']; pack_name = pack['name']
            print(f"[BULK] Downloading {total} files (4-way parallel)...")
            
            def process_sample(sample):
                preview_file = next((f for f in sample.get('files', []) if f['asset_file_type_slug'] == 'preview_mp3'), None)
                if not preview_file: return
                final_path = get_safe_path(base_dir, pack_name, sample['name'])
                if os.path.exists(final_path): return
                
                with self.decode_semaphore:
                    try:
                        r = requests.get(preview_file['url'], timeout=15, stream=True)
                        tmp_path = final_path + ".tmp"
                        os.makedirs(os.path.dirname(final_path), exist_ok=True)
                        with open(tmp_path, "wb") as f:
                            for chunk in r.iter_content(chunk_size=16384): f.write(chunk)
                            f.flush(); os.fsync(f.fileno())
                        
                        with open(tmp_path, "rb") as f: raw_data = f.read()
                        decoded = bytes(decode_splice_audio(raw_data))
                        engine.convert_to_wav(decoded, final_path)
                        os.remove(tmp_path)
                        print(f"  [BULK] Saved: {final_path}")
                    except Exception as e: print(f"  [BULK ERROR] {sample['name']}: {e}")

            with ThreadPoolExecutor(max_workers=4) as executor:
                list(executor.map(process_sample, all_samples))
            print(f"[BULK] Finished pack: {pack['name']}")
            GLib.idle_add(lambda: Adw.AlertDialog.new("Success", f"Processed {total} files from {pack['name']}").choose(self.win, None, None))
        threading.Thread(target=worker, daemon=True).start()

    def show_preferences(self, btn):
        prefs = Adw.PreferencesWindow(transient_for=self.win)
        row = Adw.ActionRow(title="Sample Directory", subtitle=config.get()['sampleDir'])
        browse_btn = Gtk.Button.new_from_icon_name("folder-open-symbolic")
        browse_btn.set_valign(Gtk.Align.CENTER)
        browse_btn.connect("clicked", lambda _: Gtk.FileDialog().select_folder(self.win, None, self.on_folder_selected, row))
        row.add_suffix(browse_btn); page = Adw.PreferencesPage(); group = Adw.PreferencesGroup(); group.add(row); page.add(group); prefs.add(page); prefs.present()

    def on_folder_selected(self, dialog, result, row):
        try:
            folder = dialog.select_folder_finish(result)
            if folder: path = folder.get_path(); config.mutate(sampleDir=path); row.set_subtitle(path)
        except: pass

def main(): return pyspliceApp().run(sys.argv)
if __name__ == "__main__": main()
