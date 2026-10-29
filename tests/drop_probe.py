"""Executa a regressão fatal fora do processo do unittest."""
import json
from pathlib import Path
import sys
import tkinter as tk

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import App
from verify_drop import exercise_drop

root = tk.Tk()
app = App(root)
result = exercise_drop(root, app)
root.destroy()
print(json.dumps(result))
