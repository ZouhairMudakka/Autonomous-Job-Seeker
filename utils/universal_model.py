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
from datetime import datetime
from storage.logs_manager import LogsManager


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

    def __init__(self, logs_manager: LogsManager):
        """Initialize ModelSelector with a LogsManager instance for async logging."""
        self.logs_manager = logs_manager

        # Load environment variables
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        self.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.deepseek_endpoint = os.getenv("DEEPSEEK_ENDPOINT", "https://api.deepseek.com")
        self.model_box_api_key = os.getenv("MODEL_BOX_API_KEY", "")
        self.model_box_endpoint = os.getenv("MODEL_BOX_ENDPOINT", "https://api.model.box/v1")

        # Default to standard OpenAI settings (can override in calls)
        openai.api_key = self.openai_api_key
        openai.api_base = "https://api.openai.com/v1"

        # Optionally store custom token limits at runtime
        self.custom_token_limits = {}

        # GUI Chat Integration settings
        self.chat_system_prompt = """You are a helpful AI assistant integrated into a job search automation system. 
You can help users with their job search, provide advice, and answer questions about the automation process.
You have access to various features including CV parsing, job matching, and application automation.
You can explain how these features work and help users make the most of them."""

        self.chat_max_history = 50  # Maximum number of messages to keep in history
        self.chat_max_context = 10  # Maximum number of messages to include in context window

    async def initialize(self):
        """Async initialization that should be called after creating the ModelSelector instance."""
        await self.logs_manager.info("Initializing ModelSelector...")
        await self._validate_env_vars()
        await self.logs_manager.info("ModelSelector initialization complete.")

    async def _validate_env_vars(self):
        """Validate that required environment variables are set."""
        if not self.openai_api_key:
            await self.logs_manager.warning("OPENAI_API_KEY not set. Standard OpenAI models won't function.")
        if not self.deepseek_api_key:
            await self.logs_manager.warning("DEEPSEEK_API_KEY not set. DeepSeek models won't function.")
        if not self.model_box_api_key:
            await self.logs_manager.warning("MODEL_BOX_API_KEY not set. Model Box models won't function.")

    async def set_token_limits(self, model: str, input_limit: int = None, output_limit: int = None):
        """
        Override default token limits for a specific model at runtime.
        """
        if model not in self.custom_token_limits:
            self.custom_token_limits[model] = {}
            await self.logs_manager.debug(f"Creating new token limit entry for model: {model}")

        old_limits = self.custom_token_limits.get(model, {})
        if input_limit is not None:
            self.custom_token_limits[model]["input"] = input_limit
            await self.logs_manager.info(f"Updated input token limit for {model}: {input_limit} (was: {old_limits.get('input', 'not set')})")
        if output_limit is not None:
            self.custom_token_limits[model]["output"] = output_limit
            await self.logs_manager.info(f"Updated output token limit for {model}: {output_limit} (was: {old_limits.get('output', 'not set')})")

    async def get_token_limits(self, model: str) -> Dict[str, int]:
        """
        Retrieve token limits, preferring custom overrides if available.
        """
        default_limits = {"input": 4000, "output": 2000}
        base_limits = self.DEFAULT_TOKEN_LIMITS.get(model, default_limits)
        overrides = self.custom_token_limits.get(model, {})
        
        result = {
            "input": overrides.get("input", base_limits["input"]),
            "output": overrides.get("output", base_limits["output"])
        }
        
        if model not in self.DEFAULT_TOKEN_LIMITS:
            await self.logs_manager.warning(f"Using default token limits for unknown model: {model}")
        if overrides:
            await self.logs_manager.debug(f"Using custom token limits for {model}: {result}")
        else:
            await self.logs_manager.debug(f"Using base token limits for {model}: {result}")
            
        return result

    async def supports_vision(self, model: str) -> bool:
        """Check if a model supports vision capabilities."""
        supports = model in self.VISION_MODELS
        if supports:
            await self.logs_manager.debug(f"Model {model} supports vision: {self.VISION_MODELS[model]}")
        else:
            await self.logs_manager.debug(f"Model {model} does not support vision capabilities")
        return supports

    async def get_vision_capabilities(self, model: str) -> str:
        """Get description of a model's vision features."""
        capabilities = self.VISION_MODELS.get(model, "No vision capabilities for this model.")
        if model in self.VISION_MODELS:
            await self.logs_manager.debug(f"Retrieved vision capabilities for {model}: {capabilities}")
        else:
            await self.logs_manager.debug(f"No vision capabilities found for model: {model}")
        return capabilities

    async def chat_completion(self,
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
            await self.logs_manager.info(f"No model provided; using default: {model}")

        # Check vision support
        if vision_required and not await self.supports_vision(model):
            await self.logs_manager.warning(f"Model {model} does not support vision. Switching to {self.DEFAULT_VISION_MODEL}")
            model = self.DEFAULT_VISION_MODEL

        # Determine token limits
        token_limits = self.get_token_limits(model)
        if max_tokens is None:
            max_tokens = token_limits["output"]
        kwargs["max_tokens"] = max_tokens

        await self.logs_manager.debug(f"Starting chat completion with model: {model}")

        # Decide which method to call
        try:
            if model in self.OPENAI_MODELS:
                return await self._call_standard_openai_api(model, messages, return_full_response, **kwargs)
            elif model in self.DEEPSEEK_MODELS:
                return await self._call_deepseek_api(model, messages, return_full_response, **kwargs)
            elif any(model.startswith(prefix) for prefix in ["deepseek/", "google/", "openai/", "meta-llama/", "qwen/", "anthropic/"]):
                return await self._call_model_box_api(model, messages, return_full_response, **kwargs)
            else:
                err_msg = f"Unsupported model: {model}"
                await self.logs_manager.error(err_msg)
                return err_msg
        except Exception as e:
            error_msg = f"Error in chat completion: {str(e)}"
            await self.logs_manager.error(error_msg)
            return error_msg

    async def _call_standard_openai_api(self, model: str, messages: List[Dict[str, str]],
                                  return_full_response: bool,
                                  **kwargs) -> Any:
        """
        Calls the standard OpenAI ChatCompletion (api_base=https://api.openai.com/v1)
        """
        if not self.openai_api_key:
            error_msg = "Error: OPENAI_API_KEY not set, cannot call standard OpenAI."
            await self.logs_manager.error(error_msg)
            return error_msg

        await self.logs_manager.debug("Setting up standard OpenAI API configuration")
        openai.api_key = self.openai_api_key
        openai.api_base = "https://api.openai.com/v1"

        return await self._call_openai_api(model, messages, return_full_response, **kwargs)

    async def _call_deepseek_api(self, model: str, messages: List[Dict[str, str]],
                           return_full_response: bool,
                           **kwargs) -> Any:
        """
        Calls the DeepSeek endpoint using openai library but overriding api_base/ api_key
        """
        if not self.deepseek_api_key:
            error_msg = f"Error: DEEPSEEK_API_KEY not set, cannot call {model}."
            await self.logs_manager.error(error_msg)
            return error_msg

        await self.logs_manager.debug("Setting up DeepSeek API configuration")
        openai.api_key = self.deepseek_api_key
        openai.api_base = self.deepseek_endpoint

        return await self._call_openai_api(model, messages, return_full_response, **kwargs)

    async def _call_model_box_api(self, model: str, messages: List[Dict[str, str]],
                            return_full_response: bool,
                            **kwargs) -> Any:
        """
        Calls the Model Box endpoint (api_base=self.model_box_endpoint) with model_box_api_key
        """
        if not self.model_box_api_key:
            error_msg = f"Error: MODEL_BOX_API_KEY not set, cannot call {model}."
            await self.logs_manager.error(error_msg)
            return error_msg

        await self.logs_manager.debug("Setting up Model Box API configuration")
        openai.api_key = self.model_box_api_key
        openai.api_base = self.model_box_endpoint

        return await self._call_openai_api(model, messages, return_full_response, **kwargs)

    async def _call_openai_api(self, 
                         model: str, 
                         messages: List[Dict[str, str]], 
                         return_full_response: bool,
                         **kwargs) -> Any:
        """
        Helper that calls openai.ChatCompletion.create(...) with the current openai.api_key/api_base
        after being set by the calling method. Minimizes duplication.
        """
        try:
            await self.logs_manager.debug(f"Making API call to model: {model}")
            await self.logs_manager.debug(f"Request parameters: model={model}, return_full_response={return_full_response}, kwargs={kwargs}")
            
            # Log message count and structure (without content for privacy)
            msg_structure = [{"role": m["role"]} for m in messages]
            await self.logs_manager.debug(f"Sending {len(messages)} messages with structure: {msg_structure}")
            
            start_time = datetime.now()
            response = openai.ChatCompletion.create(
                model=model,
                messages=messages,
                **kwargs
            )
            duration = (datetime.now() - start_time).total_seconds()
            
            # Log response metadata
            token_usage = getattr(response, 'usage', None)
            if token_usage:
                await self.logs_manager.info(
                    f"API call successful - Model: {model}, "
                    f"Duration: {duration:.2f}s, "
                    f"Tokens: {token_usage.total_tokens} "
                    f"(prompt: {token_usage.prompt_tokens}, "
                    f"completion: {token_usage.completion_tokens})"
                )
            else:
                await self.logs_manager.info(f"API call successful - Model: {model}, Duration: {duration:.2f}s")
            
            if return_full_response:
                return response
            else:
                content = response.choices[0].message.content
                await self.logs_manager.debug(f"Returning content of length: {len(content)} characters")
                return content
                
        except openai.error.RateLimitError as e:
            error_msg = f"Rate limit exceeded for {model}: {str(e)}"
            await self.logs_manager.error(error_msg)
            await self.logs_manager.warning("Consider implementing rate limiting or switching to a different model")
            return error_msg
            
        except openai.error.InvalidRequestError as e:
            error_msg = f"Invalid request to {model}: {str(e)}"
            await self.logs_manager.error(error_msg)
            await self.logs_manager.debug(f"Request details that caused error - model: {model}, kwargs: {kwargs}")
            return error_msg
            
        except openai.error.AuthenticationError as e:
            error_msg = f"Authentication failed for {model}: {str(e)}"
            await self.logs_manager.error(error_msg)
            await self.logs_manager.warning("Check if API key is valid and has required permissions")
            return error_msg
            
        except Exception as e:
            error_msg = f"Unexpected error calling {model}: {str(e)}"
            await self.logs_manager.error(error_msg)
            await self.logs_manager.error(f"Full error details: {type(e).__name__}: {str(e)}")
            return error_msg

    async def vision_completion(self, model: str, image: bytes, prompt: str) -> str:
        """
        Process an image with a vision model through ModelBox.
        """
        if not isinstance(image, bytes) or len(image) == 0:
            error_msg = "Error: Invalid image data - must be non-empty bytes"
            await self.logs_manager.error(error_msg)
            return error_msg
        
        if not prompt or not isinstance(prompt, str):
            error_msg = "Error: Prompt must be a non-empty string"
            await self.logs_manager.error(error_msg)
            return error_msg

        client = None
        try:
            if not self.model_box_api_key:
                error_msg = "Error: MODEL_BOX_API_KEY not set"
                await self.logs_manager.error(error_msg)
                return error_msg

            await self.logs_manager.info(f"Starting vision completion with model: {model}")

            # Configure OpenAI client for ModelBox with correct endpoint
            client = openai.Client(
                api_key=self.model_box_api_key,
                base_url=f"{self.model_box_endpoint.rstrip('/')}/v1"  # Ensure single /v1 path
            )

            # Convert image to base64
            import base64
            image_b64 = base64.b64encode(image).decode('utf-8')

            await self.logs_manager.debug("Image encoded, preparing API call")

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
            await self.logs_manager.debug("Making vision API call")
            response = client.chat.completions.create(
                model=model,
                messages=messages
            )
            await self.logs_manager.info("Vision completion successful")

            return response.choices[0].message.content

        except Exception as e:
            error_msg = f"Error in vision completion: {str(e)}"
            await self.logs_manager.error(error_msg)
            return error_msg
        finally:
            # Ensure proper cleanup
            if client is not None:
                try:
                    client.close()
                    await self.logs_manager.debug("Vision API client closed")
                except Exception as e:
                    await self.logs_manager.warning(f"Error closing client: {str(e)}")

    async def format_chat_messages(self, messages: List[Dict[str, Any]], include_system_prompt: bool = True) -> List[Dict[str, str]]:
        """
        Format chat messages for the model, optionally including the system prompt.
        Specifically designed for GUI chat integration.
        """
        await self.logs_manager.debug(f"Formatting {len(messages)} messages for chat")
        formatted_messages = []
        
        if include_system_prompt:
            formatted_messages.append({
                "role": "system",
                "content": self.chat_system_prompt
            })
            await self.logs_manager.debug("Added system prompt to messages")
            
        # Add the most recent messages within context window
        context_messages = messages[-self.chat_max_context:]
        formatted_messages.extend(context_messages)
        
        if len(messages) > self.chat_max_context:
            await self.logs_manager.debug(f"Truncated {len(messages) - self.chat_max_context} older messages to fit context window")
        
        await self.logs_manager.debug(f"Final message count: {len(formatted_messages)} (including system prompt: {include_system_prompt})")
        return formatted_messages

    async def get_chat_response(self,
                         messages: List[Dict[str, Any]],
                         model: str = None,
                         temperature: float = 0.7,
                         max_tokens: int = None,
                         **kwargs) -> Dict[str, Any]:
        """
        Get a response for the GUI chat interface.
        Returns a dictionary with the response and metadata.
        """
        try:
            # Use default model if none specified
            if model is None:
                model = self.DEFAULT_TEXT_MODEL
                await self.logs_manager.info(f"Using default model for chat: {model}")

            await self.logs_manager.debug("Formatting chat messages with system prompt")
            # Format messages with system prompt
            formatted_messages = await self.format_chat_messages(messages)
            
            # Get token limits for the model
            token_limits = self.get_token_limits(model)
            if max_tokens is None:
                max_tokens = token_limits["output"]

            await self.logs_manager.debug(f"Getting chat response with model {model}")
            # Get response from model
            response = await self.chat_completion(
                messages=formatted_messages,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                return_full_response=True,
                **kwargs
            )

            # Extract and format the result
            result = {
                "content": response.choices[0].message.content,
                "model": model,
                "timestamp": datetime.now().isoformat(),
                "metadata": {
                    "token_count": response.usage.total_tokens if hasattr(response, 'usage') else None,
                    "model_name": model,
                    "temperature": temperature,
                    "max_tokens": max_tokens
                }
            }

            await self.logs_manager.debug(f"Chat response received, tokens used: {result['metadata']['token_count']}")
            return result

        except Exception as e:
            error_msg = f"Error in get_chat_response: {str(e)}"
            await self.logs_manager.error(error_msg)
            return {
                "content": f"Error: {str(e)}",
                "model": model,
                "timestamp": datetime.now().isoformat(),
                "metadata": {
                    "error": str(e),
                    "model_name": model
                }
            }

    def update_chat_system_prompt(self, new_prompt: str):
        """Update the system prompt used in chat conversations."""
        self.chat_system_prompt = new_prompt

    def set_chat_context_window(self, max_history: int = None, max_context: int = None):
        """Update the chat context window settings."""
        if max_history is not None:
            self.chat_max_history = max_history
        if max_context is not None:
            self.chat_max_context = max_context

    async def stream_chat_response(self,
                                 messages: List[Dict[str, Any]],
                                 model: str = None,
                                 temperature: float = 0.7,
                                 max_tokens: int = None,
                                 chunk_callback=None,
                                 **kwargs) -> Dict[str, Any]:
        """
        Stream a response for the GUI chat interface.
        Calls chunk_callback with each chunk of the response as it arrives.
        Returns the complete response with metadata when done.
        """
        try:
            # Use default model if none specified
            if model is None:
                model = self.DEFAULT_TEXT_MODEL
                await self.logs_manager.info(f"Using default model for streaming chat: {model}")

            await self.logs_manager.debug("Formatting messages with system prompt for streaming")
            # Format messages with system prompt
            formatted_messages = await self.format_chat_messages(messages)
            
            # Get token limits for the model
            token_limits = await self.get_token_limits(model)
            if max_tokens is None:
                max_tokens = token_limits["output"]
                await self.logs_manager.debug(f"Using default max_tokens from model limits: {max_tokens}")

            # Start streaming response
            full_content = ""
            start_time = datetime.now()
            chunk_count = 0
            total_chars = 0
            
            await self.logs_manager.info(f"Starting streaming response from model {model} with temperature={temperature}")
            
            # Set up streaming parameters
            kwargs['stream'] = True
            await self.logs_manager.debug(f"Stream parameters: {kwargs}")
            
            response_stream = await self.chat_completion(
                messages=formatted_messages,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                return_full_response=True,
                **kwargs
            )

            # Process the stream
            await self.logs_manager.debug("Beginning to process response stream")
            last_progress_log = start_time
            
            async for chunk in response_stream:
                if hasattr(chunk.choices[0], 'delta') and hasattr(chunk.choices[0].delta, 'content'):
                    content = chunk.choices[0].delta.content
                    if content:
                        chunk_count += 1
                        total_chars += len(content)
                        full_content += content
                        
                        # Log progress every 2 seconds
                        current_time = datetime.now()
                        if (current_time - last_progress_log).total_seconds() >= 2:
                            await self.logs_manager.debug(
                                f"Streaming progress - Chunks: {chunk_count}, "
                                f"Characters: {total_chars}, "
                                f"Duration: {(current_time - start_time).total_seconds():.1f}s"
                            )
                            last_progress_log = current_time
                        
                        if chunk_callback:
                            await chunk_callback(content)

            # Prepare final result with metadata
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            result = {
                "content": full_content,
                "model": model,
                "timestamp": end_time.isoformat(),
                "metadata": {
                    "model_name": model,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "response_time": duration,
                    "total_chunks": chunk_count,
                    "total_characters": total_chars,
                    "characters_per_second": total_chars / duration if duration > 0 else 0
                }
            }

            await self.logs_manager.info(
                f"Streaming complete - "
                f"Duration: {duration:.1f}s, "
                f"Chunks: {chunk_count}, "
                f"Characters: {total_chars}, "
                f"Speed: {result['metadata']['characters_per_second']:.1f} chars/sec"
            )
            return result

        except Exception as e:
            error_msg = f"Error in stream_chat_response: {str(e)}"
            await self.logs_manager.error(error_msg)
            await self.logs_manager.error(f"Full error details: {type(e).__name__}: {str(e)}")
            
            error_result = {
                "content": f"Error: {str(e)}",
                "model": model,
                "timestamp": datetime.now().isoformat(),
                "metadata": {
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "model_name": model
                }
            }
            
            if chunk_callback:
                try:
                    await chunk_callback(error_result["content"])
                except Exception as callback_error:
                    await self.logs_manager.error(f"Error in chunk callback: {str(callback_error)}")
                    
            return error_result

    def export_chat_history(self, history: List[Dict[str, Any]], format: str = "txt") -> bytes:
        """
        Export chat history in various formats.
        Supported formats: txt, json, markdown, html
        """
        try:
            if format == "txt":
                content = ""
                for msg in history:
                    timestamp = msg.get("timestamp", "").split("T")[1][:8]  # Extract time HH:MM:SS
                    role = msg.get("role", "unknown")
                    text = msg.get("content", "")
                    content += f"[{timestamp}] {role.upper()}: {text}\n\n"
                return content.encode('utf-8')

            elif format == "json":
                import json
                return json.dumps(history, indent=2).encode('utf-8')

            elif format == "markdown":
                content = "# Chat History\n\n"
                for msg in history:
                    timestamp = msg.get("timestamp", "").split("T")[1][:8]
                    role = msg.get("role", "unknown")
                    text = msg.get("content", "")
                    content += f"### {role.upper()} ({timestamp})\n\n{text}\n\n---\n\n"
                return content.encode('utf-8')

            elif format == "html":
                content = """
                <!DOCTYPE html>
                <html>
                <head>
                    <style>
                        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
                        .message { margin: 10px 0; padding: 10px; border-radius: 5px; }
                        .user { background: #e3f2fd; }
                        .assistant { background: #f5f5f5; }
                        .timestamp { color: #666; font-size: 0.8em; }
                    </style>
                </head>
                <body>
                    <h1>Chat History</h1>
                """
                for msg in history:
                    timestamp = msg.get("timestamp", "").split("T")[1][:8]
                    role = msg.get("role", "unknown")
                    text = msg.get("content", "").replace("\n", "<br>")
                    content += f"""
                    <div class="message {role}">
                        <div class="timestamp">{timestamp}</div>
                        <div class="content"><strong>{role.upper()}:</strong> {text}</div>
                    </div>
                    """
                content += "</body></html>"
                return content.encode('utf-8')

            else:
                raise ValueError(f"Unsupported export format: {format}")

        except Exception as e:
            self.logger.error(f"Error exporting chat history: {str(e)}")
            return f"Error exporting chat history: {str(e)}".encode('utf-8')
