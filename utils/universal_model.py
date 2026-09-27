"""Async chat/vision clients with credentials isolated by provider.

Model lists and token limits are local configuration defaults, not live catalogs.
"""

import base64
import inspect
import json
import logging
import os
import time
from datetime import datetime
from html import escape
from typing import Any, Dict, List, Optional

import openai


class _AsyncLogger:
    """Adapt standard logging when no application LogsManager was supplied."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def info(self, message):
        self.logger.info(message)

    async def debug(self, message):
        self.logger.debug(message)

    async def warning(self, message):
        self.logger.warning(message)

    async def error(self, message):
        self.logger.error(message)


class ModelSelector:
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
        "gpt-4o-mini": "Supports image inputs",
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

    def __init__(self, logs_manager=None):
        self.logs_manager = logs_manager if logs_manager is not None else _AsyncLogger()
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        self.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.deepseek_endpoint = os.getenv("DEEPSEEK_ENDPOINT", "https://api.deepseek.com")
        self.model_box_api_key = os.getenv("MODEL_BOX_API_KEY", "")
        self.model_box_endpoint = os.getenv("MODEL_BOX_ENDPOINT", "https://api.model.box/v1")
        self.custom_token_limits = {}
        self.chat_system_prompt = (
            "You are a helpful AI assistant for a job search automation system. "
            "Help with job search questions and explain the available features."
        )
        self.chat_max_history = 50
        self.chat_max_context = 10

    async def initialize(self):
        await self._validate_env_vars()

    async def _validate_env_vars(self):
        for name, key in (("OPENAI_API_KEY", self.openai_api_key),
                          ("DEEPSEEK_API_KEY", self.deepseek_api_key),
                          ("MODEL_BOX_API_KEY", self.model_box_api_key)):
            if not key:
                await self.logs_manager.warning(f"{name} is not set; this provider is unavailable")

    async def set_token_limits(self, model: str, input_limit=None, output_limit=None):
        for value in (input_limit, output_limit):
            if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value <= 0):
                raise ValueError("Token limits must be positive integers")
        limits = self.custom_token_limits.setdefault(model, {})
        if input_limit is not None:
            limits['input'] = input_limit
        if output_limit is not None:
            limits['output'] = output_limit

    def token_limits(self, model: str) -> Dict[str, int]:
        defaults = self.DEFAULT_TOKEN_LIMITS.get(model, {'input': 4000, 'output': 2000})
        return {**defaults, **self.custom_token_limits.get(model, {})}

    async def get_token_limits(self, model: str) -> Dict[str, int]:
        return self.token_limits(model)

    async def supports_vision(self, model: str) -> bool:
        return model in self.VISION_MODELS

    async def get_vision_capabilities(self, model: str) -> str:
        return self.VISION_MODELS.get(model, "No vision capabilities configured for this model")

    def _provider(self, model):
        if model in self.OPENAI_MODELS or model.startswith('gpt-'):
            return 'OPENAI_API_KEY', self.openai_api_key, 'https://api.openai.com/v1'
        if model in self.DEEPSEEK_MODELS:
            return 'DEEPSEEK_API_KEY', self.deepseek_api_key, self.deepseek_endpoint
        if model.startswith(('deepseek/', 'google/', 'openai/', 'meta-llama/', 'qwen/', 'anthropic/')):
            return 'MODEL_BOX_API_KEY', self.model_box_api_key, self.model_box_endpoint
        raise ValueError(f"Unsupported model: {model}")

    def _client(self, model):
        key_name, key, endpoint = self._provider(model)
        if not key:
            raise ValueError(f"{key_name} is not set")
        # A separate client avoids process-global API keys crossing provider calls.
        return openai.AsyncOpenAI(api_key=key, base_url=endpoint, timeout=60.0)

    async def chat_completion(self, messages: List[Dict[str, Any]], model: str = None,
                              max_tokens: Optional[int] = None, vision_required=False,
                              return_full_response=False, **kwargs) -> Any:
        model = model or (self.DEFAULT_VISION_MODEL if vision_required else self.DEFAULT_TEXT_MODEL)
        if vision_required and not await self.supports_vision(model):
            raise ValueError(f"Vision is not supported for model: {model}")
        limits = await self.get_token_limits(model)
        max_tokens = limits['output'] if max_tokens is None else max_tokens
        if not isinstance(max_tokens, int) or isinstance(max_tokens, bool) or max_tokens <= 0:
            raise ValueError("max_tokens must be a positive integer")
        kwargs.setdefault('max_completion_tokens' if model.startswith(('o1', 'gpt-5', 'gpt-6'))
                          else 'max_tokens', max_tokens)
        if kwargs.get('stream') and not return_full_response:
            raise ValueError("Streaming requires return_full_response=True or stream_chat_response")
        return await self._call_openai_api(model, messages, return_full_response, **kwargs)

    async def _call_standard_openai_api(self, model, messages, return_full_response, **kwargs):
        return await self._call_openai_api(model, messages, return_full_response, **kwargs)

    async def _call_deepseek_api(self, model, messages, return_full_response, **kwargs):
        return await self._call_openai_api(model, messages, return_full_response, **kwargs)

    async def _call_model_box_api(self, model, messages, return_full_response, **kwargs):
        return await self._call_openai_api(model, messages, return_full_response, **kwargs)

    async def _call_openai_api(self, model, messages, return_full_response, **kwargs):
        if kwargs.get('stream'):
            return self._stream_completion(model, messages, **kwargs)
        async with self._client(model) as client:
            response = await client.chat.completions.create(model=model, messages=messages, **kwargs)
        if return_full_response:
            return response
        if not response.choices:
            raise RuntimeError("Provider returned no completion choices")
        content = response.choices[0].message.content
        if not isinstance(content, str):
            raise RuntimeError("Provider returned no text content")
        return content

    async def _stream_completion(self, model, messages, **kwargs):
        async with self._client(model) as client:
            stream = await client.chat.completions.create(model=model, messages=messages, **kwargs)
            try:
                async for chunk in stream:
                    yield chunk
            finally:
                await stream.close()

    async def vision_completion(self, model: str, image: bytes, prompt: str) -> str:
        if not isinstance(image, bytes) or not image:
            raise ValueError("Image must be non-empty bytes")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("Prompt must be a non-empty string")
        if image.startswith(b'\x89PNG\r\n\x1a\n'):
            media_type = 'image/png'
        elif image.startswith(b'\xff\xd8\xff'):
            media_type = 'image/jpeg'
        elif image.startswith((b'GIF87a', b'GIF89a')):
            media_type = 'image/gif'
        elif image.startswith(b'RIFF') and image[8:12] == b'WEBP':
            media_type = 'image/webp'
        else:
            raise ValueError("Unsupported image format (expected PNG, JPEG, GIF or WebP)")
        encoded = base64.b64encode(image).decode('ascii')
        messages = [{'role': 'user', 'content': [
            {'type': 'text', 'text': prompt},
            {'type': 'image_url', 'image_url': {'url': f'data:{media_type};base64,{encoded}'}}
        ]}]
        return await self.chat_completion(messages, model=model, vision_required=True)

    async def format_chat_messages(self, messages, include_system_prompt=True):
        # UI metadata and prior internal error messages are not model instructions.
        valid = [message for message in messages if message.get('status') != 'error']
        context = valid[-self.chat_max_context:]
        formatted = [{key: value for key, value in msg.items()
                      if key in {'role', 'content', 'name', 'tool_calls', 'tool_call_id'}}
                     for msg in context]
        if include_system_prompt and not any(msg.get('role') in {'system', 'developer'} for msg in formatted):
            formatted.insert(0, {'role': 'system', 'content': self.chat_system_prompt})
        return formatted

    async def get_chat_response(self, messages, model=None, temperature=0.7, max_tokens=None, **kwargs):
        model = model or self.DEFAULT_TEXT_MODEL
        formatted = await self.format_chat_messages(messages)
        response = await self.chat_completion(formatted, model=model, max_tokens=max_tokens,
                                              temperature=temperature, return_full_response=True, **kwargs)
        if not response.choices or not isinstance(response.choices[0].message.content, str):
            raise RuntimeError("Provider returned no text content")
        usage = getattr(response, 'usage', None)
        return {'content': response.choices[0].message.content, 'model': model,
                'timestamp': datetime.now().isoformat(),
                'metadata': {'token_count': getattr(usage, 'total_tokens', None),
                             'model_name': model, 'temperature': temperature,
                             'max_tokens': max_tokens or (await self.get_token_limits(model))['output']}}

    def update_chat_system_prompt(self, new_prompt: str):
        self.chat_system_prompt = new_prompt

    def set_chat_context_window(self, max_history=None, max_context=None):
        for value in (max_history, max_context):
            if value is not None and (not isinstance(value, int) or value <= 0):
                raise ValueError("Chat window sizes must be positive integers")
        if max_history is not None:
            self.chat_max_history = max_history
        if max_context is not None:
            self.chat_max_context = max_context

    async def stream_chat_response(self, messages, model=None, temperature=0.7,
                                   max_tokens=None, chunk_callback=None, **kwargs):
        model = model or self.DEFAULT_TEXT_MODEL
        formatted = await self.format_chat_messages(messages)
        kwargs['stream'] = True
        stream = await self.chat_completion(formatted, model=model, max_tokens=max_tokens,
                                            temperature=temperature, return_full_response=True, **kwargs)
        chunks, tokens = [], None
        started = time.monotonic()
        try:
            async for chunk in stream:
                if getattr(chunk, 'usage', None) is not None:
                    tokens = chunk.usage.total_tokens
                if not chunk.choices:
                    continue  # Providers may send a usage-only final event.
                content = getattr(chunk.choices[0].delta, 'content', None)
                if content:
                    chunks.append(content)
                    if chunk_callback:
                        result = chunk_callback(content)
                        if inspect.isawaitable(result):
                            await result
        finally:
            await stream.aclose()
        content = ''.join(chunks)
        duration = time.monotonic() - started
        return {'content': content, 'model': model, 'timestamp': datetime.now().isoformat(),
                'metadata': {'model_name': model, 'token_count': tokens, 'temperature': temperature,
                             'max_tokens': max_tokens or (await self.get_token_limits(model))['output'],
                             'response_time': duration, 'total_chunks': len(chunks),
                             'total_characters': len(content),
                             'characters_per_second': len(content) / duration if duration else 0}}

    def export_chat_history(self, history, format='txt') -> bytes:
        if format == 'json':
            return json.dumps(history, indent=2, default=lambda value: value.isoformat()
                              if isinstance(value, datetime) else str(value)).encode('utf-8')
        if format not in {'txt', 'markdown', 'html'}:
            raise ValueError(f"Unsupported export format: {format}")
        parts = ['# Chat History\n'] if format == 'markdown' else []
        if format == 'html':
            parts = ['<!doctype html><html><head><meta charset="utf-8"></head><body><h1>Chat History</h1>']
        for message in history:
            stamp = message.get('timestamp', '')
            stamp = stamp.isoformat() if isinstance(stamp, datetime) else str(stamp)
            stamp = stamp.partition('T')[2][:8] if 'T' in stamp else stamp
            role, content = str(message.get('role', 'unknown')), str(message.get('content', ''))
            if format == 'html':
                parts.append(f'<p><small>{escape(stamp)}</small> <strong>{escape(role.upper())}</strong></p>'
                             f'<pre>{escape(content)}</pre>')
            elif format == 'markdown':
                parts.append(f'### {role.upper()} ({stamp})\n\n{content}\n')
            else:
                parts.append(f'[{stamp}] {role.upper()}: {content}\n')
        if format == 'html':
            parts.append('</body></html>')
        return '\n'.join(parts).encode('utf-8')
