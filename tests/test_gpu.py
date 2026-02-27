import time
import torch
from pysentimiento import create_analyzer

print(f"CUDA Available: {torch.cuda.is_available()}")

start = time.time()
analyzer = create_analyzer(task="sentiment", lang="es")
print(f"Time to load model: {time.time() - start:.2f}s")
print(f"Analyzer Model Device: {analyzer.model.device}")

start = time.time()
res = analyzer.predict(["Me encantó el hotel", "El servicio fue terrible"])
print(f"Predict time (2 items): {time.time() - start:.2f}s")
print(res)
