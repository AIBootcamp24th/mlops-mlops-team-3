import os

TOTAL_PAGES = 250

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DATA_PATH = os.path.join(BASE_DIR, "src/data/raw/movies.csv")
RESULT_DIR = os.path.join(BASE_DIR, "src/data/result")

INPUT_DIM = 4
EPOCHS = 300
LR = 0.001
BATCH_SIZE = 32
