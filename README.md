# pysplice
A modern and fast GTK4 application for browsing and downloading samples from Splice. pysplice allows you to search for samples and packs, preview them instantly, and download them directly to your local library.
# this is a very WIP project,you can still try it as you want tho

## Features

- **Native UI**: Built with GTK4
- **Fast Search**: Browse through millions of samples and packs using Splice's GraphQL API.
- **Advanced Filtering**: Filter by Key, BPM, Category (One-Shots/Loops), and sort by Relevance, Popularity, or Recency.
- **Instant Preview**: Listen to samples directly in the app with a built-in audio engine.
- **High-Quality Downloads**: Automatically decodes and converts Splice's preview format to high-quality WAV files.
- **Bulk Download**: Download entire packs with a single click (4-way parallel downloading).

## Prerequisites

Before running pysplice, ensure you have the following system dependencies installed:

### Fedora
```bash
sudo dnf install python3-gobject gtk4 libadwaita
```

### Ubuntu/Debian
```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1
```

### Arch Linux
```bash
sudo pacman -S python-gobject gtk4 libadwaita
```

## Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/nxptunx/pysplice.git
   cd pysplice
   ```

2. **Create a virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

To start the application, run:

```bash
python run.py
```

### Configuration

pysplice stores its configuration and downloaded samples in the following locations:
- **Config**: `~/.config/pysplice/config.json`
- **Default Sample Directory**: `~/Samples` (Adjustable in the application settings)

## Development

The project structure is organized as follows:

- `src/main.py`: Main application logic and UI definitions.
- `src/audio_engine.py`: Audio playback and WAV conversion using `miniaudio`.
- `src/splice_api.py`: Splice GraphQL API integration.
- `src/splice_decoder.py`: Custom decoding logic for Splice audio assets.
- `src/config.py`: User configuration management.

## License

This project is licensed under the GNU GPL v3 License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with [PyGObject](https://pygobject.readthedocs.io/) and [Libadwaita](https://gnome.pages.gitlab.gnome.org/libadwaita/).
- Audio powered by [miniaudio](https://github.com/irmen/pyminiaudio).
- Inspired by and really thanks to [Splicedd by ascpixi](https://github.com/ascpixi/splicedd), this project wouldnt exist without their code



