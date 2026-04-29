import spacy
import pandas as pd

nlp = spacy.load("en_core_web_sm")
print("Environment is ready!")
print(f"Pandas version: {pd.__version__}")