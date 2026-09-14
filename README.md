# KaiROS

**Kinetic Audio Intelligent Recommendation & Orchestration System**

A Discord music bot that builds a persistent emotional memory of every song it plays. It uses a custom CNN+BiLSTM model to map tracks onto a Valence/Arousal coordinate plane, then uses those coordinates to find what to play next.

Most bots take requests. KaiROS learns taste.

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://python.org)
[![discord.py](https://img.shields.io/badge/discord.py-async-5865F2?logo=discord&logoColor=white)](https://discordpy.readthedocs.io)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.0+-EE4C2C?logo=pytorch&logoColor=white)](https://pytorch.org)
[![SQLite](https://img.shields.io/badge/SQLite-WAL_mode-003B57?logo=sqlite&logoColor=white)](https://sqlite.org)

---

## How It Works

Every track that finishes playing goes through a background pipeline:

1. **FFmpeg** extracts a 30-second audio window (starting at the 15s mark to skip intros)
2. **Librosa** computes a 128-band Mel spectrogram + 12-band Chromagram → 140-dimensional feature vector per frame
3. A **2D CNN → BiLSTM** model (3 conv blocks, 2-layer bidirectional LSTM, 384 hidden dim) predicts per-frame Valence and Arousal
4. The time-averaged V/A coordinates, plus detected language, artist, year, and duration are stored in SQLite

When autoplay needs a next track, it pulls from two sources:

- **KaiROS Memory** — Nearest-neighbor lookup in V/A space, weighted with bonuses for matching language (−0.05 distance), same artist (−0.15), and same era within 3 years (−0.02)
- **YouTube Discovery** — Pulls from YouTube Mix playlists seeded by the current track, filtered for bad words (remix, cover, reaction, etc.)

A dynamic weight blends the two: `kairos_weight = min(0.7, track_count / 1500)`. Small database → more YouTube discovery. Large database → more memory-driven recommendations. Each track is chosen probabilistically using this weight.

---

## The Emotion Model

```
Input: [B, T, 140]  (128 mel + 12 chroma per frame)
  ↓
3× Conv2d blocks (32→64→128 channels, GELU, BatchNorm, MaxPool on frequency axis)
  ↓
Reshape to [B, T, C*F']
  ↓
2-layer BiLSTM (384 hidden, dropout 0.3)
  ↓
LayerNorm → Linear(768→384) → GELU → Linear(384→2)
  ↓
Output: [B, T, 2]  →  mean over T  →  (Valence, Arousal)
```

The model runs in `bfloat16` on CUDA, `float32` on CPU. Weights ship as `autoplay/best_model.pt` (~46MB).

The four quadrants map to vibes:

| Quadrant | Valence | Arousal | Vibe |
|---|---|---|---|
| Q1 | > 0 | > 0 | ☀️ Happy & Energetic |
| Q2 | > 0 | ≤ 0 | 🍃 Peaceful & Chill |
| Q3 | ≤ 0 | > 0 | 🔥 Intense & Aggressive |
| Q4 | ≤ 0 | ≤ 0 | 🌧️ Melancholic & Dark |

---

## Commands

### Playback

| Command | What it does |
|---|---|
| `/play <url or search>` | Queue a track by URL or YouTube search |
| `/search <query>` | Browse top 15 results in a dropdown, pick one to queue |
| `/skip` | Skip the current track |
| `/stop` | Stop playback and clear the queue |
| `/pause` / `/resume` | Pause and resume |
| `/nowplaying` | Show the current track with its V/A coordinates and vibe quadrant |
| `/loop` | Cycle through: Off → Track repeat → Queue repeat → Off |

### Queue Management

| Command | What it does |
|---|---|
| `/queue` | Paginated queue view with navigation buttons |
| `/shuffle` | Randomize the user queue |
| `/remove <pos>` | Remove a track by position |
| `/move <from> <to>` | Reorder a track |
| `/clear` | Wipe the queue without stopping the current track |

### Intelligence

| Command | What it does |
|---|---|
| `/start` | Opens a 4-button Vibe Selector (Hype, Chill, Intense, Melancholic) — pulls a random matching track from the database and starts playback |
| `/recommend` | Returns 5 nearest-neighbor tracks based on the current song's V/A, language, artist, and era — each with a match score |
| `/brain` | Shows how many tracks KaiROS has learned and the server's global average vibe |

### Utility

| Command | What it does |
|---|---|
| `/join` / `/leave` | Voice channel management |
| `/ping` | Latency check |
| `/info` | Bot info with paginated details |

---

## Architecture

```
main.py                 ← Bot entry point, slash commands, voice state handling
├── queuemgr/
│   ├── qmgr.py         ← QueueManager: per-guild queues, download, playback orchestration
│   ├── queue_state.py   ← QueueState: per-guild user/auto queues, history, loop mode
│   ├── playback.py      ← yt-dlp download with retry logic and pre-info fast path
│   ├── autoplay_mgr.py  ← fill_autoplay(): the weighted mixer (DB + YouTube)
│   ├── processor.py     ← InferenceQueue: background worker for emotion analysis
│   └── lazydel.py       ← LazyDeleter: batched file cleanup with threshold GC
├── autoplay/
│   ├── model.py         ← EmotionModel (CNN + BiLSTM)
│   ├── inference.py     ← EmotionAnalyzer: ffmpeg → librosa → PyTorch pipeline
│   ├── recommender.py   ← YouTube Mix playlist scraping + title normalization
│   └── config.py        ← Audio params (22050 Hz, 128 mels, 0.5s windows)
├── database/
│   └── database.py      ← SQLite with WAL mode: track logging, vibe queries, recommendations
├── utils/
│   ├── language_utils.py ← lingua-py language detection with regex title cleaning
│   └── ydl_config.py    ← Centralized yt-dlp option presets
└── UI/
    ├── vibe_selector.py  ← 4-button vibe picker (discord.ui.View)
    ├── queue_view.py     ← Paginated queue display
    ├── info_view.py      ← Bot info with pagination
    ├── search_view.py    ← Search result dropdown
    └── recommend_view.py ← Recommendation results with play buttons
```

---

## Resilience

**Voice reconnection** — When Discord drops the WebSocket (error 1006), the bot detects the abnormal disconnect via `on_voice_state_update`, reconnects to the same channel, and keeps the queue intact. Only explicit `/stop` or `/leave` triggers a clean disconnect.

**Auto-disconnect** — If all humans leave the voice channel, the bot disconnects and cleans up.

**File GC** — Audio files are not deleted immediately after playback (FFmpeg may still hold locks). The `LazyDeleter` batches them and sweeps when a threshold is hit, retrying on `PermissionError`. On startup, orphaned files from crashed sessions are cleaned.

**Download retry** — `yt-dlp` downloads retry up to 3 times with exponential backoff. A fast path skips re-extraction when pre-info is available.

---

## Background Workers

All heavy processing is fully async and non-blocking:

- **InferenceQueue** — `asyncio.Queue`-backed worker. After a track finishes, it runs the emotion model in a thread executor, detects language, and writes to SQLite. Tracks already in the DB are skipped.
- **LazyDeleter** — Thread-based file sweeper. Accumulates finished audio files and bulk-deletes when the threshold (default 20) is reached.
- **Autoplay fill** — Runs `fill_autoplay()` in the background whenever the auto-queue drops below 15 tracks. YouTube Mix fetches run in an executor to avoid blocking the event loop.

---

## Running It

### Prerequisites

- Python 3.10+
- FFmpeg on PATH
- A Discord bot token

### Setup

```bash
git clone https://github.com/your-username/kairos.gg.git
cd kairos.gg
pip install -r requirements.txt
```

Create a `.env` file:

```
DISCORD_TOKEN=your_bot_token_here
```

### Start

```bash
# Linux (uses /dev/shm for audio files — faster I/O)
./run.sh

# Windows (uses downloads/ folder)
run.bat

# Linux with tmux session management
./tmux.sh
```

Or directly:

```bash
python main.py
```

### Try it live

Don't want to self-host? Use the public instance:

- **Discord server**: [Join KaiROS Official](https://discord.gg/ZztmZ5JFCQ)
- **Add to your server**: [Invite link](https://discord.com/oauth2/authorize?client_id=1466508202471592057&permissions=37080256&integration_type=0&scope=bot+applications.commands)

Run `/start` in any authorized channel to begin.

---

## Tech Stack

| Component | Technology |
|---|---|
| Runtime | Python 3.10+ (asyncio) |
| Discord | discord.py 2.3+ |
| Audio fetch | yt-dlp |
| Audio playback | FFmpeg (Opus) |
| ML inference | PyTorch 2.0+ |
| Feature extraction | Librosa (mel + chroma) |
| Language detection | lingua-py (n-gram, 0.15 confidence threshold) |
| Database | SQLite3 (WAL mode, indexed on V/A) |
| Hosting | Linux (/dev/shm) or Windows |
