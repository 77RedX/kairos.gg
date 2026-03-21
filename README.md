Here is the finalized, polished README.md for your GitHub repository. It accurately reflects all the advanced architectural upgrades, bug fixes, and machine learning integrations we've built into the system.

You can copy and paste this directly into your repo!

🎧 KaiROS: Vibe-Aware Discord Music Bot
KaiROS (Kinetic Audio Intelligent Recommendation & Orchestration System) is a high-performance, machine-learning-powered Discord music bot.

Unlike standard bots that simply play URLs in a queue, KaiROS acts as an AI DJ. It builds a local "Neural Memory" of every song it plays, analyzing the audio to map its emotional "Vibe" across Valence (Positivity) and Arousal (Energy). It uses this database to seamlessly blend your known favorites with intelligent YouTube discoveries.

🚀 Key Features
🧠 ML Emotion Analysis: Processes downloaded audio through a custom PyTorch & Librosa pipeline to extract definitive Valence and Arousal coordinates for every track.

🎛️ Weighted Autoplay Mixer: A probabilistic recommendation engine that balances "Exploration" (YouTube's related tracks) and "Exploitation" (KaiROS's internal database matches via Squared Euclidean Distance).

🛡️ Self-Healing Voice Engine: Features a dynamic polling and crash-recovery system. If Discord forcefully drops the WebSocket connection (Error 1006), KaiROS auto-reconnects and pushes the interrupted track back to the front of the queue seamlessly.

🌐 Smart Metadata Extraction: A hybrid pipeline utilizing regex-based title sanitization and high-accuracy statistical N-gram language detection (lingua-py) to automatically tag tracks by language (en, ja, hi, etc.) without relying solely on YouTube's tags.

⚡ Zero-Blocking Architecture: Audio analysis and file cleanup are offloaded to background asyncio workers (InferenceQueue and LazyDeleter), ensuring pristine, lag-free music playback.

🛠️ Commands
🎵 Music Control
/play [url or search query] - Downloads and adds a track to the queue.

/skip - Instantly skips the current track.

/stop - Halts playback, clears the queue, and initiates smart garbage collection.

/queue - Displays an interactive, paginated UI of the upcoming tracks.

🧠 Intelligent Vibe Features
/start - Opens the Vibe Selector UI. Choose a mood (Hype, Chill, Intense, Melancholic) and KaiROS will instantly pull a random matching song from its neural memory.

/recommend - Analyzes the currently playing track and generates 5 highly accurate matches based on Vibe Distance, Language, Artist, and Release Year.

/brain - Displays current database statistics, including total tracked songs and the Global Vibe Average of your server.

🏗️ Technical Architecture
Language: Python 3.10+

Core Framework: discord.py

Audio Fetching: yt-dlp (Extracts metadata & audio streams)

Playback Engine: FFmpeg (Optimized for low-latency streaming)

Machine Learning: PyTorch, Librosa (Acoustic analysis)

NLP / Linguistics: lingua-py (Confidence-based language classification)

Database: SQLite3 (Fast, localized vector-distance querying)

The Data Flow
User requests a song. yt-dlp fetches the audio stream and metadata.

FFmpeg plays the audio in the voice channel.

Upon completion, the InferenceQueue processes the .webm file through PyTorch/Librosa.

Language is predicted via Lingua (with a 0.15 confidence threshold for short titles).

V/A coordinates, Language, Artist, and Release Year are saved to SQLite.

The LazyDeleter safely removes the audio file from the host machine to preserve storage.

🔗 How to Use KaiROS
You don’t need to host your own instance to experience the Vibe-Engine. You can join the official development and testing hub:

Join the Discord Server: [Join Official Discord](https://discord.gg/ZztmZ5JFCQ)

Invite the Bot: Once inside, you can use the /invite command or click the Bot's profile to add it to your own server.

Start the Vibe: Use /start in any authorized channel to begin building your server's unique musical profile.

The Data Lifecycle
Ingestion: A user requests a track. yt-dlp pulls the stream.

Streaming: FFmpeg pipes the audio to Discord's voice servers.

Inference: Upon track completion, the InferenceQueue triggers the PyTorch model to calculate emotional coordinates.

Classification: Title is cleaned via Regex and passed to Lingua for ISO language tagging.

Persistence: Coordinates and metadata are committed to the SQL database.

Cleanup: LazyDeleter performs scheduled garbage collection of temporary audio files to maintain disk health.

📈 Database Insights
Once the bot has analyzed enough music in your server, you can visualize the "Emotional DNA" of your community.

By querying the SQLite backend, KaiROS can generate reports on your server's most frequent musical quadrants (e.g., Is this a "Chill" server or an "Intense" server?). This data directly influences the Weighted Autoplay DJ, ensuring the bot learns and evolves alongside your tastes.