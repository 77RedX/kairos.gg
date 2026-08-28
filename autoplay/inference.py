import torch
import librosa
import numpy as np
import logging
import subprocess
import json

# Import your model and configs from your ML folder
from .model import EmotionModel
from .config import SAMPLE_RATE, HOP_SIZE, N_MELS, START_TIME, WINDOW_SIZE

logger = logging.getLogger(__name__)

class EmotionAnalyzer:
    def __init__(self, model_path="autoplay/best_model.pt"):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = EmotionModel().to(self.device)
        
        # Load the weights
        try:
            state_dict = torch.load(model_path, map_location=self.device)
            # If you saved the whole dictionary (epoch, state, etc.), extract just the model_state
            if "model_state" in state_dict:
                self.model.load_state_dict(state_dict["model_state"])
            else:
                self.model.load_state_dict(state_dict)
                
            self.model.eval()
            logger.info("✅ EmotionAnalyzer loaded successfully.")
        except Exception as e:
            logger.error(f"❌ Failed to load model: {e}")

    def analyze_audio(self, file_path):
        """Extracts features and returns average Valence and Arousal."""
        try:
            # 1. Get duration using ffprobe
            ffprobe_cmd = [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "json", file_path
            ]
            probe_result = subprocess.run(ffprobe_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if probe_result.returncode != 0:
                raise Exception(f"ffprobe error: {probe_result.stderr}")
            
            probe_data = json.loads(probe_result.stdout)
            duration = float(probe_data["format"]["duration"])
            
            # Calculate offset and duration to load
            offset = min(START_TIME, max(0.0, duration - 30.0))
            
            # 2. Extract audio using ffmpeg directly to NumPy array
            ffmpeg_cmd = [
                "ffmpeg",
                "-ss", str(offset),
                "-i", file_path,
                "-t", "30.0",
                "-f", "f32le",
                "-acodec", "pcm_f32le",
                "-ac", "1",
                "-ar", str(SAMPLE_RATE),
                "pipe:1"
            ]
            ffmpeg_result = subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if ffmpeg_result.returncode != 0:
                raise Exception(f"ffmpeg error: {ffmpeg_result.stderr.decode('utf-8', errors='ignore')}")
            
            y = np.frombuffer(ffmpeg_result.stdout, dtype=np.float32)
            sr = SAMPLE_RATE

            # Calculate exact window and hop sizes from training
            n_fft = int(WINDOW_SIZE * sr)
            hop_length = int(HOP_SIZE * sr)

            # 2. Extract Mel Spectrogram (EXACTLY like training)
            mel = librosa.feature.melspectrogram(
                y=y, 
                sr=sr, 
                n_fft=n_fft, 
                hop_length=hop_length, 
                n_mels=N_MELS
            )
            # CRITICAL FIX: Removed ref=np.max and added the + 1e-6 offset
            mel_db = librosa.power_to_db(mel + 1e-6)

            # 3. Extract Chroma (EXACTLY like training)
            chroma = librosa.feature.chroma_stft(
                y=y, 
                sr=sr, 
                n_fft=n_fft, 
                hop_length=hop_length
            )

            # Make sure they are the same length (just like chroma_mels.py)
            T = min(mel_db.shape[1], chroma.shape[1])
            mel_db = mel_db[:, :T]
            chroma = chroma[:, :T]

            # 4. Combine and Transpose
            features = np.concatenate([mel_db, chroma], axis=0).T  # Shape: [T, 140]

            # 5. Convert to PyTorch Tensor
            # We use bfloat16 if on CUDA, otherwise float32
            dtype = torch.bfloat16 if self.device.type == "cuda" else torch.float32
            X = torch.tensor(features, dtype=dtype).unsqueeze(0).to(self.device) # [1, T, 140]

            # 6. Run Inference
            with torch.no_grad():
                with torch.amp.autocast("cuda", dtype=dtype):
                    out, _ = self.model(X) # out shape: [1, T, 2]

            # 7. Calculate stats across the time dimension (dim=1)
            # out shape: [1, T, 2]
            predictions = out.squeeze(0).cpu().float().numpy() # Shape: [T, 2]
            
            avg_va = np.mean(predictions, axis=0) # [mean_v, mean_a]
            std_va = np.std(predictions, axis=0)  # [std_v, std_a]
            
            return {
                "v_avg": float(avg_va[0]),
                "a_avg": float(avg_va[1]),
                "v_std": float(std_va[0]),
                "a_std": float(std_va[1])
            }

        except Exception as e:
            logger.error(f"Error analyzing {file_path}: {e}")
            return None