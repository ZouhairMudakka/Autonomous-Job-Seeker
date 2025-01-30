"""
Model Selector for Vision and Language Models

Note: This is a simplified version of ModelSelector used only by test_dom_features.py
For production use, see utils/universal_model.py
"""

from utils.universal_model import ModelSelector as UniversalModelSelector

class ModelSelector(UniversalModelSelector):
    def __init__(self):
        super().__init__()
        # Inherit all model configurations from UniversalModelSelector
        # Including VISION_MODELS, DEFAULT_TOKEN_LIMITS, etc.

    def vision_completion(self, model: str, image: bytes, prompt: str) -> str:
        """Simplified vision completion for testing purposes."""
        if not self.supports_vision(model):
            return f"Error: Model {model} does not support vision capabilities"
            
        # For testing, return a mock response
        return f"Vision analysis of image using {model}" 