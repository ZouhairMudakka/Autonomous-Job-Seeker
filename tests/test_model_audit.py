"""Model provider regressions using fake SDK clients only; no API calls."""
import asyncio
import json
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from modules.ai_module import AIModule
from utils.model_selector import ModelSelector as CompatibilitySelector
from utils.universal_model import ModelSelector
import utils.universal_model as universal


class FakeStream:
    def __init__(self, chunks, client):
        self.chunks = iter(chunks)
        self.client = client
        self.closed = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        assert not self.client.closed
        try:
            return next(self.chunks)
        except StopIteration:
            raise StopAsyncIteration

    async def close(self):
        self.closed = True


@pytest.fixture
def fake_sdk(monkeypatch):
    clients = []

    class Client:
        def __init__(self, **kwargs):
            self.config = kwargs
            self.closed = False
            self.requests = []
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))
            clients.append(self)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            self.closed = True

        async def create(self, **kwargs):
            self.requests.append(kwargs)
            await asyncio.sleep(0)
            if kwargs.get('stream'):
                self.stream = FakeStream([
                    SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content='Hello'))]),
                    SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=' world'))]),
                    SimpleNamespace(choices=[], usage=SimpleNamespace(total_tokens=7)),
                ], self)
                return self.stream
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=kwargs['model']))],
                                   usage=None)

    monkeypatch.setattr(universal.openai, 'AsyncOpenAI', Client)
    monkeypatch.setenv('OPENAI_API_KEY', 'test-openai')
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'test-deepseek')
    monkeypatch.setenv('MODEL_BOX_API_KEY', 'test-modelbox')
    monkeypatch.delenv('MODEL_BOX_ENDPOINT', raising=False)
    monkeypatch.delenv('DEEPSEEK_ENDPOINT', raising=False)
    return clients


@pytest.mark.asyncio
async def test_concurrent_providers_keep_credentials_and_endpoints_separate(fake_sdk, monkeypatch):
    monkeypatch.setattr(universal.openai, 'api_key', 'global-unchanged')
    selector = ModelSelector()
    models = ['gpt-4o-mini', 'deepseek-chat', 'google/gemini-2.0-flash-thinking']
    results = await asyncio.gather(*(selector.chat_completion([{'role': 'user', 'content': 'hi'}], model=model)
                                     for model in models))
    assert results == models
    assert [client.config['api_key'] for client in fake_sdk] == ['test-openai', 'test-deepseek', 'test-modelbox']
    assert [client.config['base_url'] for client in fake_sdk] == [
        'https://api.openai.com/v1', 'https://api.deepseek.com', 'https://api.model.box/v1']
    assert all(client.closed for client in fake_sdk)
    assert universal.openai.api_key == 'global-unchanged'
    assert fake_sdk[0].requests[0]['max_tokens'] == 4096


@pytest.mark.asyncio
async def test_missing_key_is_an_error_not_model_content(fake_sdk, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY')
    with pytest.raises(ValueError, match='OPENAI_API_KEY'):
        await ModelSelector().chat_completion([], model='gpt-4o')
    assert fake_sdk == []


@pytest.mark.asyncio
async def test_vision_uses_selected_provider_and_one_version_path(fake_sdk):
    selector = CompatibilitySelector()
    image = b'\x89PNG\r\n\x1a\nimage'
    assert await selector.vision_completion('gpt-4o', image, 'Describe') == 'gpt-4o'
    assert fake_sdk[-1].config['api_key'] == 'test-openai'
    await selector.vision_completion('google/gemini-2.0-flash-thinking', image, 'Describe')
    assert fake_sdk[-1].config['base_url'] == 'https://api.model.box/v1'
    assert fake_sdk[-1].requests[0]['messages'][0]['content'][1]['image_url']['url'].startswith('data:image/png;base64,')


@pytest.mark.asyncio
async def test_vision_does_not_silently_switch_providers(fake_sdk):
    selector = ModelSelector()
    with pytest.raises(ValueError, match='Vision'):
        await selector.chat_completion([], model='deepseek-chat', vision_required=True)
    assert fake_sdk == []


@pytest.mark.asyncio
async def test_stream_handles_usage_only_chunk_and_closes_client(fake_sdk):
    chunks = []
    result = await ModelSelector().stream_chat_response(
        [{'role': 'user', 'content': 'hi', 'timestamp': datetime.now()}],
        model='gpt-4o', chunk_callback=chunks.append)
    assert result['content'] == 'Hello world'
    assert result['metadata']['token_count'] == 7
    assert chunks == ['Hello', ' world']
    assert fake_sdk[0].closed and fake_sdk[0].stream.closed
    assert 'timestamp' not in fake_sdk[0].requests[0]['messages'][-1]


@pytest.mark.asyncio
async def test_stream_callback_error_closes_resources_and_propagates(fake_sdk):
    async def callback(_chunk):
        raise RuntimeError('consumer failed')

    with pytest.raises(RuntimeError, match='consumer failed'):
        await ModelSelector().stream_chat_response([], model='gpt-4o', chunk_callback=callback)
    assert fake_sdk[0].closed and fake_sdk[0].stream.closed


@pytest.mark.asyncio
async def test_metadata_accepts_provider_without_usage(fake_sdk):
    result = await ModelSelector().get_chat_response([], model='gpt-4o')
    assert result['content'] == 'gpt-4o'
    assert result['metadata']['token_count'] is None


@pytest.mark.parametrize('format', ['txt', 'json', 'markdown', 'html'])
def test_export_handles_datetime_and_missing_timestamp(format):
    history = [{'role': 'user', 'content': '<script>alert(1)</script>', 'timestamp': datetime(2026, 1, 1)},
               {'role': 'assistant', 'content': 'hello'}]
    output = ModelSelector().export_chat_history(history, format).decode('utf-8')
    assert 'hello' in output
    if format == 'html':
        assert '<script>' not in output
        assert '&lt;script&gt;' in output
    if format == 'json':
        assert json.loads(output)[0]['timestamp'] == '2026-01-01T00:00:00'


@pytest.mark.asyncio
async def test_ai_module_awaits_response_and_keeps_ui_config_out_of_api():
    selector = ModelSelector()
    selector.chat_completion = AsyncMock(return_value='Reply')
    module = AIModule('gpt-4o', model_selector=selector, temperature=0.5, chat_settings={'typing_speed': 0})
    assert await module.process_message('Hello') == 'Reply'
    selector.chat_completion.assert_awaited_once()
    assert 'chat_settings' not in selector.chat_completion.call_args.kwargs
    assert isinstance(module.conversation_history[-1]['content'], str)
    assert len({item['id'] for item in module.conversation_history}) == 2
    assert 'Supports vision' in module.get_model_info()


@pytest.mark.asyncio
async def test_ai_completion_merges_override_parameters():
    selector = ModelSelector()
    selector.chat_completion = AsyncMock(return_value='Done')
    module = AIModule('gpt-4o', model_selector=selector, max_tokens=500, temperature=0.1)
    assert await module.get_completion('Do it', max_tokens=25, temperature=0.2) == 'Done'
    assert selector.chat_completion.call_args.kwargs['max_tokens'] == 25
    assert selector.chat_completion.call_args.kwargs['temperature'] == 0.2


@pytest.mark.asyncio
async def test_cancelled_chat_stream_hides_typing_indicator():
    selector = ModelSelector()
    entered = asyncio.Event()

    async def stream(**kwargs):
        entered.set()
        await asyncio.Event().wait()

    selector.stream_chat_response = stream
    module = AIModule('gpt-4o', model_selector=selector)
    events = []
    task = asyncio.create_task(module.process_message_stream('hello', events.append))
    await entered.wait()
    assert module.typing_indicator_visible
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not module.typing_indicator_visible
    assert events == ['typing_start', 'typing_end']


@pytest.mark.asyncio
async def test_internal_chat_errors_are_not_sent_as_system_instructions():
    selector = ModelSelector()
    selector.chat_completion = AsyncMock(side_effect=RuntimeError('provider unavailable'))
    module = AIModule('gpt-4o', model_selector=selector)
    with pytest.raises(Exception, match='provider unavailable'):
        await module.process_message('Hi')
    assert all(msg['content'] != 'provider unavailable' for msg in module._format_messages_for_model())
