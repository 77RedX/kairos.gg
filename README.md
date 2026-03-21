# 🎧 KaiROS — Vibe-Aware Discord Music Bot

> **Kinetic Audio Intelligent Recommendation & Orchestration System**

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Framework](https://img.shields.io/badge/discord.py-async-green)
![ML](https://img.shields.io/badge/ML-PyTorch%20%7C%20Librosa-orange)
![Database](https://img.shields.io/badge/DB-SQLite-lightgrey)
![Status](https://img.shields.io/badge/status-active-success)

---

## 🧠 What is KaiROS?

**KaiROS is not just a music bot. It’s an AI DJ.**

Unlike traditional bots that simply queue songs, KaiROS builds a **Neural Memory** of every track it plays.  
It understands music through **emotion**, mapping songs across:

- 🎯 **Valence** → Positivity / Mood  
- ⚡ **Arousal** → Energy / Intensity  

This allows KaiROS to **blend your favorites with intelligent discoveries**, creating a seamless listening experience.

---

## 🚀 Key Features

### 🧠 ML Emotion Analysis
- Custom PyTorch + Librosa pipeline.
- Extracts definitive **Valence & Arousal coordinates** from audio features.
- Builds a persistent, localized emotional dataset.

### 🎛️ Weighted Autoplay Mixer
- Probabilistic recommendation engine balancing:
  - 🔍 **Exploration** → YouTube's related track discovery.
  - 📚 **Exploitation** → Internal memory matches via **Squared Euclidean Distance**.
- Adjustable weighting allows tuning the discovery-to-familiarity ratio.

### 🛡️ Self-Healing Voice Engine
- Dynamic polling auto-recovers from Discord WebSocket drops (Error 1006).
- Seamlessly re-establishes voice connections.
- Automatically reinserts the interrupted track at the front of the queue.

### 🌐 Smart Metadata Extraction
- Hybrid pipeline using Regex-based title sanitization.
- High-accuracy statistical N-gram language detection via **lingua-py** (tuned with a custom 0.15 confidence threshold for short titles).
- Supports multilingual tagging: `en`, `hi`, `ja`, etc.

### ⚡ Zero-Blocking Architecture
- Audio analysis and file cleanup offloaded to background asyncio workers (`InferenceQueue` and `LazyDeleter`).
- Ensures pristine, lag-free music playback.

---

## 🎵 Commands

### 🎧 Music Control

| Command | Description |
|--------|-------------|
| `/play [url/query]` | Download and add a track to the queue |
| `/skip` | Instantly skip the current track |
| `/stop` | Halt playback, clear queue, and trigger garbage collection |
| `/queue` | Show an interactive, paginated queue UI |

### 🧠 Intelligent Vibe System

| Command | Description |
|--------|-------------|
| `/start` | Open Vibe Selector UI (Hype, Chill, Intense, Melancholic) |
| `/recommend` | Get 5 matches based on current Vibe, Language, Artist, and Year |
| `/brain` | View database statistics and Global Vibe Average |

---

## 🏗️ Tech Stack

```txt
Language        → Python 3.10+
Framework       → discord.py
Audio Fetching  → yt-dlp
Playback        → FFmpeg (Opus encoding)
Machine Learning→ PyTorch + Librosa
NLP             → lingua-py
Database        → SQLite3

---

## 🔗 How to Use KaiROS

```txt
- You don’t need to host your own instance to experience the Vibe-Engine. Join the official development and testing hub:

- Join the Discord Server: Join KaiROS Official (Ensure you use a permanent invite link!)

- Invite the Bot: Once inside, use the /invite command or click the Bot's profile to add it to your own server.

- Start the Vibe: Use /start in any authorized channel to begin building your server's unique musical profile.