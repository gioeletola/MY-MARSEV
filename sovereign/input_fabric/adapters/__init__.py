"""Input adapters — one per supported modality."""
from sovereign.input_fabric.adapters.audio_adapter import AudioAdapter
from sovereign.input_fabric.adapters.csv_adapter import CsvAdapter
from sovereign.input_fabric.adapters.image_adapter import ImageAdapter
from sovereign.input_fabric.adapters.json_adapter import JsonAdapter
from sovereign.input_fabric.adapters.pdf_adapter import PdfAdapter
from sovereign.input_fabric.adapters.text_adapter import TextAdapter

__all__ = [
    "TextAdapter", "JsonAdapter", "CsvAdapter",
    "PdfAdapter", "ImageAdapter", "AudioAdapter",
]
