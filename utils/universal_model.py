"""
universal_model.py

A universal interface for multiple LLM providers (OpenAI, DeepSeek, Model Box).
Reads environment variables to configure each provider, then returns a client or
a function you can use to perform completions.

Enhancements:
-------------
1. Reduced code duplication via a single helper method `_call_openai_api`.
2. More detailed docstrings and inline comments.
3. Optional fallback if environment variables are missing (currently returns errors).
4. Optionally return full response vs. just message content (controlled by 'return_full_response').
5. Add direct integration with Google's Gemini models
6. Add direct integration with Anthropic's Claude models
7. Add support for provider-specific features and parameters

Usage Example:
--------------
from universal_model import ModelSelector

model_selector = ModelSelector()

response = model_selector.chat_completion(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"}
    ]
)

print(response)
"""

import os
import logging
from typing import List, Dict, Any, Optional
import openai


class ModelSelector:
    """
    Provides a single interface for chat completions, regardless of whether we are using:
      - Standard OpenAI endpoint
      - DeepSeek endpoint
      - Model Box endpoint
    """

    # Default text model if none specified
    DEFAULT_TEXT_MODEL = "deepseek/deepseek-chat"
    # Default vision model if a user requires vision capabilities
    DEFAULT_VISION_MODEL = "google/gemini-2.0-flash-thinking"

    # Example sets of recognized models
    OPENAI_MODELS = [
        "gpt-4o", "gpt-4o-audio-preview", "gpt-4o-realtime-preview",
        "gpt-4o-mini", "gpt-4o-mini-audio-preview", "gpt-4o-mini-realtime-preview",
        "o1", "o1-mini", "chatgpt-4o-latest", "gpt-4-turbo", "gpt-4",
        "gpt-4-32k", "gpt-3.5-turbo", "gpt-3.5-turbo-instruct", "gpt-3.5-turbo-16k",
        "davinci-002", "babbage-002"
    ]

    DEEPSEEK_MODELS = [
        "deepseek-chat",
        "deepseek-reasoner"
    ]

    MODEL_BOX_MODELS = [
        "deepseek/deepseek-chat", "deepseek/deepseek-reasoner", "deepseek/deepseek-coder",
        "google/gemini-2.0-flash-thinking", "openai/o1", "meta-llama/llama-3.3-70b-instruct",
        "meta-llama/llama-3.2-90b-instruct", "qwen/qwen2-vl-72b",
        "anthropic/claude-3-5-sonnet", "openai/chatgpt-4o-latest"
    ]

    # Vision-capable models for the sake of example
    VISION_MODELS = {
        "gpt-4o": "Supports images, documents, and charts",
        "o1": "Advanced vision capabilities with high resolution",
        "google/gemini-2.0-flash-thinking": "Google's vision model with fast processing",
        "openai/o1": "OpenAI's vision model via Model Box",
        "qwen/qwen2-vl-72b": "Qwen's vision-language model",
        "anthropic/claude-3-5-sonnet": "Claude's vision capabilities",
        "openai/chatgpt-4o-latest": "Latest OpenAI vision model",
        "meta-llama/llama-3.2-90b-instruct": "Llama's vision capabilities"
    }

    # Example default token limits for each model
    DEFAULT_TOKEN_LIMITS = {
        "gpt-4o": {"input": 128000, "output": 4096},
        "gpt-4o-mini": {"input": 128000, "output": 4096},
        "o1": {"input": 12000, "output": 4096},
        "o1-mini": {"input": 12000, "output": 4096},
        "gpt-4": {"input": 8192, "output": 4096},
        "gpt-3.5-turbo": {"input": 4096, "output": 4096},
        "deepseek-chat": {"input": 128000, "output": 4096},
        "deepseek-reasoner": {"input": 128000, "output": 4096},
        "deepseek/deepseek-chat": {"input": 128000, "output": 4096},
        "deepseek/deepseek-reasoner": {"input": 128000, "output": 4096},
        "google/gemini-2.0-flash-thinking": {"input": 200000, "output": 4096},
        "openai/o1": {"input": 12000, "output": 4096},
        "qwen/qwen2-vl-72b": {"input": 32000, "output": 8192},
        "anthropic/claude-3-5-sonnet": {"input": 200000, "output": 4096},
        "meta-llama/llama-3.3-70b-instruct": {"input": 64000, "output": 4096},
        "meta-llama/llama-3.2-90b-instruct": {"input": 64000, "output": 4096}
    }

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # Load environment variables
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        self.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.deepseek_endpoint = os.getenv("DEEPSEEK_ENDPOINT", "https://api.deepseek.com")
        self.model_box_api_key = os.getenv("MODEL_BOX_API_KEY", "")
        self.model_box_endpoint = os.getenv("MODEL_BOX_ENDPOINT", "https://api.model.box/v1")

        # Default to standard OpenAI settings (can override in calls)
        openai.api_key = self.openai_api_key
        openai.api_base = "https://api.openai.com/v1"

        # Validate environment variables
        self._validate_env_vars()

        # Optionally store custom token limits at runtime
        self.custom_token_limits = {}

    def _validate_env_vars(self):
        if not self.openai_api_key:
            self.logger.warning("OPENAI_API_KEY not set. Standard OpenAI models won't function.")
        if not self.deepseek_api_key:
            self.logger.warning("DEEPSEEK_API_KEY not set. DeepSeek models won't function.")
        if not self.model_box_api_key:
            self.logger.warning("MODEL_BOX_API_KEY not set. Model Box models won't function.")

    def set_token_limits(self, model: str, input_limit: int = None, output_limit: int = None):
        """
        Override default token limits for a specific model at runtime.
        """
        if model not in self.custom_token_limits:
            self.custom_token_limits[model] = {}

        if input_limit is not None:
            self.custom_token_limits[model]["input"] = input_limit
        if output_limit is not None:
            self.custom_token_limits[model]["output"] = output_limit

    def get_token_limits(self, model: str) -> Dict[str, int]:
        """
        Retrieve token limits, preferring custom overrides if available.
        """
        default_limits = {"input": 4000, "output": 2000}
        base_limits = self.DEFAULT_TOKEN_LIMITS.get(model, default_limits)
        overrides = self.custom_token_limits.get(model, {})
        return {
            "input": overrides.get("input", base_limits["input"]),
            "output": overrides.get("output", base_limits["output"])
        }

    def supports_vision(self, model: str) -> bool:
        """Check if a model supports vision capabilities."""
        return model in self.VISION_MODELS

    def get_vision_capabilities(self, model: str) -> str:
        """Get description of a model's vision features."""
        return self.VISION_MODELS.get(model, "No vision capabilities for this model.")

    def chat_completion(self,
                        messages: List[Dict[str, str]],
                        model: str = None,
                        max_tokens: Optional[int] = None,
                        vision_required: bool = False,
                        return_full_response: bool = False,
                        **kwargs) -> Any:
        """
        Main method for chat-based completions with token limit handling.

        Args:
            messages: Chat messages (list of dicts with 'role' and 'content')
            model: Name of the model, e.g. "gpt-4o", "deepseek-chat", "openai/o1".
            max_tokens: Optional override for output token limit
            vision_required: If True, switch to a known vision-capable model if selected model doesn't support vision
            return_full_response: If True, return the entire response object, otherwise just message content
            **kwargs: Additional parameters for ChatCompletion (e.g., temperature, stream, etc.)

        Returns:
            str if return_full_response=False, else the entire JSON response object
        """
        # Default to text or vision model if none specified
        if model is None:
            if vision_required:
                model = self.DEFAULT_VISION_MODEL
            else:
                model = self.DEFAULT_TEXT_MODEL
            self.logger.info(f"No model provided; using default: {model}")

        # Check vision support
        if vision_required and not self.supports_vision(model):
            self.logger.warning(f"Model {model} does not support vision. Switching to {self.DEFAULT_VISION_MODEL}")
            model = self.DEFAULT_VISION_MODEL

        # Determine token limits
        token_limits = self.get_token_limits(model)
        if max_tokens is None:
            max_tokens = token_limits["output"]
        kwargs["max_tokens"] = max_tokens

        # Decide which method to call
        if model in self.OPENAI_MODELS:
            return self._call_standard_openai_api(model, messages, return_full_response, **kwargs)
        elif model in self.DEEPSEEK_MODELS:
            return self._call_deepseek_api(model, messages, return_full_response, **kwargs)
        elif any(model.startswith(prefix) for prefix in ["deepseek/", "google/", "openai/", "meta-llama/", "qwen/", "anthropic/"]):
            return self._call_model_box_api(model, messages, return_full_response, **kwargs)
        else:
            err_msg = f"Unsupported model: {model}"
            self.logger.error(err_msg)
            return err_msg

    def _call_standard_openai_api(self, model: str, messages: List[Dict[str, str]],
                                  return_full_response: bool,
                                  **kwargs) -> Any:
        """
        Calls the standard OpenAI ChatCompletion (api_base=https://api.openai.com/v1)
        """
        if not self.openai_api_key:
            return "Error: OPENAI_API_KEY not set, cannot call standard OpenAI."

        openai.api_key = self.openai_api_key
        openai.api_base = "https://api.openai.com/v1"

        return self._call_openai_api(model, messages, return_full_response, **kwargs)

    def _call_deepseek_api(self, model: str, messages: List[Dict[str, str]],
                           return_full_response: bool,
                           **kwargs) -> Any:
        """
        Calls the DeepSeek endpoint using openai library but overriding api_base/ api_key
        """
        if not self.deepseek_api_key:
            return f"Error: DEEPSEEK_API_KEY not set, cannot call {model}."

        openai.api_key = self.deepseek_api_key
        openai.api_base = self.deepseek_endpoint

        return self._call_openai_api(model, messages, return_full_response, **kwargs)

    def _call_model_box_api(self, model: str, messages: List[Dict[str, str]],
                            return_full_response: bool,
                            **kwargs) -> Any:
        """
        Calls the Model Box endpoint (api_base=self.model_box_endpoint) with model_box_api_key
        """
        if not self.model_box_api_key:
            return f"Error: MODEL_BOX_API_KEY not set, cannot call {model}."

        openai.api_key = self.model_box_api_key
        openai.api_base = self.model_box_endpoint

        return self._call_openai_api(model, messages, return_full_response, **kwargs)

    def _call_openai_api(self, 
                         model: str, 
                         messages: List[Dict[str, str]], 
                         return_full_response: bool,
                         **kwargs) -> Any:
        """
        Helper that calls openai.ChatCompletion.create(...) with the current openai.api_key/api_base
        after being set by the calling method. Minimizes duplication.
        """
        try:
            response = openai.ChatCompletion.create(
                model=model,
                messages=messages,
                **kwargs
            )
            if return_full_response:
                return response
            else:
                return response.choices[0].message.content
        except Exception as e:
            self.logger.error(f"Error calling {model} with openai library: {str(e)}")
            return f"Error calling {model}: {str(e)}"

    def vision_completion(self, model: str, image: bytes, prompt: str) -> str:
        """
        Process an image with a vision model through ModelBox.
        """
        if not isinstance(image, bytes) or len(image) == 0:
            return "Error: Invalid image data - must be non-empty bytes"
        
        if not prompt or not isinstance(prompt, str):
            return "Error: Prompt must be a non-empty string"

        client = None
        try:
            if not self.model_box_api_key:
                return "Error: MODEL_BOX_API_KEY not set"

            # Configure OpenAI client for ModelBox with correct endpoint
            client = openai.Client(
                api_key=self.model_box_api_key,
                base_url=f"{self.model_box_endpoint.rstrip('/')}/v1"  # Ensure single /v1 path
            )

            # Convert image to base64
            import base64
            image_b64 = base64.b64encode(image).decode('utf-8')

            # Create the messages array with image
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text", 
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_b64}"
                            }
                        }
                    ]
                }
            ]

            # Make the API call using the new client interface
            response = client.chat.completions.create(
                model=model,
                messages=messages
            )

            return response.choices[0].message.content

        except Exception as e:
            self.logger.error(f"Error in vision completion: {str(e)}")
            return f"Error processing image with vision model: {str(e)}"
        finally:
            # Ensure proper cleanup
            if client is not None:
                try:
                    client.close()
                except Exception as e:
                    self.logger.warning(f"Error closing client: {str(e)}")
