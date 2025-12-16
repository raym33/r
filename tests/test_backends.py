"""Tests for LLM backends."""

import json
from unittest.mock import MagicMock, patch

import pytest

from r_cli.backends.base import LLMBackend, Message, Tool, ToolCall


class TestToolCall:
    """Tests for ToolCall dataclass."""

    def test_create_tool_call(self):
        tc = ToolCall(id="tc_1", name="get_weather", arguments={"city": "Madrid"})
        assert tc.id == "tc_1"
        assert tc.name == "get_weather"
        assert tc.arguments == {"city": "Madrid"}

    def test_tool_call_empty_arguments(self):
        tc = ToolCall(id="tc_2", name="get_time", arguments={})
        assert tc.arguments == {}


class TestMessage:
    """Tests for Message dataclass."""

    def test_user_message(self):
        msg = Message(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.tool_calls == []
        assert msg.tool_call_id is None

    def test_assistant_message(self):
        msg = Message(role="assistant", content="Hi there!")
        assert msg.role == "assistant"
        assert msg.content == "Hi there!"

    def test_system_message(self):
        msg = Message(role="system", content="You are a helpful assistant")
        assert msg.role == "system"

    def test_tool_message(self):
        msg = Message(
            role="tool",
            content="Result: 42",
            tool_call_id="tc_1",
            name="calculate",
        )
        assert msg.role == "tool"
        assert msg.tool_call_id == "tc_1"
        assert msg.name == "calculate"

    def test_message_with_tool_calls(self):
        tc1 = ToolCall(id="tc_1", name="func1", arguments={"a": 1})
        tc2 = ToolCall(id="tc_2", name="func2", arguments={"b": 2})
        msg = Message(role="assistant", content=None, tool_calls=[tc1, tc2])
        assert len(msg.tool_calls) == 2
        assert msg.content is None

    def test_to_dict_simple_message(self):
        msg = Message(role="user", content="Hello")
        d = msg.to_dict()
        assert d == {"role": "user", "content": "Hello"}

    def test_to_dict_with_tool_calls(self):
        tc = ToolCall(id="tc_1", name="test_func", arguments={"x": 10})
        msg = Message(role="assistant", content="Calling function", tool_calls=[tc])
        d = msg.to_dict()
        assert d["role"] == "assistant"
        assert d["content"] == "Calling function"
        assert "tool_calls" in d
        assert len(d["tool_calls"]) == 1
        assert d["tool_calls"][0]["id"] == "tc_1"
        assert d["tool_calls"][0]["type"] == "function"
        assert d["tool_calls"][0]["function"]["name"] == "test_func"
        assert json.loads(d["tool_calls"][0]["function"]["arguments"]) == {"x": 10}

    def test_to_dict_tool_response(self):
        msg = Message(
            role="tool",
            content="Success",
            tool_call_id="tc_1",
            name="my_tool",
        )
        d = msg.to_dict()
        assert d["role"] == "tool"
        assert d["content"] == "Success"
        assert d["tool_call_id"] == "tc_1"
        assert d["name"] == "my_tool"


class TestTool:
    """Tests for Tool dataclass."""

    def test_create_tool(self):
        def handler(x: int) -> str:
            return str(x * 2)

        tool = Tool(
            name="double",
            description="Doubles a number",
            parameters={
                "type": "object",
                "properties": {"x": {"type": "integer"}},
                "required": ["x"],
            },
            handler=handler,
        )
        assert tool.name == "double"
        assert tool.description == "Doubles a number"
        assert callable(tool.handler)

    def test_tool_to_dict(self):
        tool = Tool(
            name="greet",
            description="Greets a person",
            parameters={
                "type": "object",
                "properties": {"name": {"type": "string"}},
            },
            handler=lambda name: f"Hello, {name}!",
        )
        d = tool.to_dict()
        assert d["type"] == "function"
        assert d["function"]["name"] == "greet"
        assert d["function"]["description"] == "Greets a person"
        assert "properties" in d["function"]["parameters"]

    def test_tool_handler_execution(self):
        def add(a: int, b: int) -> str:
            return str(a + b)

        tool = Tool(
            name="add",
            description="Adds two numbers",
            parameters={},
            handler=add,
        )
        result = tool.handler(a=5, b=3)
        assert result == "8"


class MockBackend(LLMBackend):
    """Mock backend for testing."""

    name = "mock"
    supports_tools = True
    supports_streaming = True

    def __init__(self, model: str = "mock-model", **kwargs):
        super().__init__(model, **kwargs)
        self._responses = []
        self._response_index = 0

    def set_responses(self, responses: list[Message]):
        self._responses = responses
        self._response_index = 0

    def is_available(self) -> bool:
        return True

    def list_models(self) -> list[str]:
        return ["mock-model-1", "mock-model-2"]

    def chat(self, message, tools=None, temperature=0.7, max_tokens=4096):
        if message:
            self.messages.append(Message(role="user", content=message))

        if self._responses and self._response_index < len(self._responses):
            response = self._responses[self._response_index]
            self._response_index += 1
        else:
            response = Message(role="assistant", content="Mock response")

        self.messages.append(response)
        return response


class TestLLMBackend:
    """Tests for LLMBackend base class."""

    def test_init(self):
        backend = MockBackend(model="test-model", temperature=0.5)
        assert backend.model == "test-model"
        assert backend.config["temperature"] == 0.5
        assert backend.messages == []

    def test_set_system_prompt(self):
        backend = MockBackend()
        backend.set_system_prompt("You are helpful")
        assert len(backend.messages) == 1
        assert backend.messages[0].role == "system"
        assert backend.messages[0].content == "You are helpful"

    def test_set_system_prompt_replaces_existing(self):
        backend = MockBackend()
        backend.set_system_prompt("First prompt")
        backend.set_system_prompt("Second prompt")
        system_msgs = [m for m in backend.messages if m.role == "system"]
        assert len(system_msgs) == 1
        assert system_msgs[0].content == "Second prompt"

    def test_add_message(self):
        backend = MockBackend()
        backend.add_message("user", "Hello")
        backend.add_message("assistant", "Hi!")
        assert len(backend.messages) == 2
        assert backend.messages[0].content == "Hello"
        assert backend.messages[1].content == "Hi!"

    def test_clear_history(self):
        backend = MockBackend()
        backend.set_system_prompt("System")
        backend.add_message("user", "Hello")
        backend.add_message("assistant", "Hi")
        backend.clear_history()
        assert len(backend.messages) == 1
        assert backend.messages[0].role == "system"

    def test_clear_history_no_system(self):
        backend = MockBackend()
        backend.add_message("user", "Hello")
        backend.clear_history()
        assert len(backend.messages) == 0

    def test_is_available(self):
        backend = MockBackend()
        assert backend.is_available() is True

    def test_list_models(self):
        backend = MockBackend()
        models = backend.list_models()
        assert "mock-model-1" in models
        assert "mock-model-2" in models

    def test_chat(self):
        backend = MockBackend()
        response = backend.chat("Hello")
        assert response.role == "assistant"
        assert len(backend.messages) == 2  # user + assistant

    def test_chat_stream_default(self):
        backend = MockBackend()
        backend.set_responses([Message(role="assistant", content="Streamed response")])
        chunks = list(backend.chat_stream("Hello"))
        assert len(chunks) == 1
        assert chunks[0] == "Streamed response"

    def test_execute_tools(self):
        backend = MockBackend()

        def greet(name: str) -> str:
            return f"Hello, {name}!"

        tools = [
            Tool(
                name="greet",
                description="Greet",
                parameters={},
                handler=greet,
            )
        ]

        tool_calls = [ToolCall(id="tc_1", name="greet", arguments={"name": "Alice"})]

        results = backend.execute_tools(tool_calls, tools)
        assert len(results) == 1
        assert results[0].content == "Hello, Alice!"
        assert results[0].tool_call_id == "tc_1"

    def test_execute_tools_not_found(self):
        backend = MockBackend()
        tools = []
        tool_calls = [ToolCall(id="tc_1", name="unknown", arguments={})]

        results = backend.execute_tools(tool_calls, tools)
        assert "Tool no encontrada" in results[0].content

    def test_execute_tools_error(self):
        backend = MockBackend()

        def failing_tool() -> str:
            raise ValueError("Something went wrong")

        tools = [Tool(name="fail", description="Fails", parameters={}, handler=failing_tool)]
        tool_calls = [ToolCall(id="tc_1", name="fail", arguments={})]

        results = backend.execute_tools(tool_calls, tools)
        assert "Error ejecutando" in results[0].content

    def test_chat_with_tools(self):
        backend = MockBackend()

        def calculator(expr: str) -> str:
            return str(eval(expr))

        tools = [
            Tool(
                name="calc",
                description="Calculate",
                parameters={},
                handler=calculator,
            )
        ]

        # First response: tool call
        # Second response: final answer
        backend.set_responses([
            Message(
                role="assistant",
                content=None,
                tool_calls=[ToolCall(id="tc_1", name="calc", arguments={"expr": "2+2"})],
            ),
            Message(role="assistant", content="The answer is 4"),
        ])

        result = backend.chat_with_tools("What is 2+2?", tools)
        assert "4" in result

    def test_chat_with_tools_max_iterations(self):
        backend = MockBackend()

        tools = [
            Tool(name="infinite", description="Always called", parameters={}, handler=lambda: "ok")
        ]

        # Always return tool calls
        backend.set_responses([
            Message(
                role="assistant",
                content=None,
                tool_calls=[ToolCall(id=f"tc_{i}", name="infinite", arguments={})],
            )
            for i in range(15)
        ])

        result = backend.chat_with_tools("Test", tools, max_iterations=3)
        assert "límite de iteraciones" in result


class TestOpenAICompatBackend:
    """Tests for OpenAI-compatible backend."""

    def test_init_with_base_url(self):
        from r_cli.backends.openai_compat import OpenAICompatBackend

        backend = OpenAICompatBackend(
            model="gpt-4",
            base_url="http://localhost:1234/v1",
            api_key="test-key",
        )
        assert backend.model == "gpt-4"
        assert backend.base_url == "http://localhost:1234/v1"

    def test_name_and_capabilities(self):
        from r_cli.backends.openai_compat import OpenAICompatBackend

        backend = OpenAICompatBackend(model="test")
        assert backend.name == "openai-compatible"
        assert backend.supports_tools is True
        assert backend.supports_streaming is True


class TestOllamaBackend:
    """Tests for Ollama backend."""

    @pytest.fixture
    def mock_requests(self):
        with patch("r_cli.backends.ollama.requests") as mock:
            yield mock

    def test_list_models(self, mock_requests):
        from r_cli.backends.ollama import OllamaBackend

        mock_requests.get.return_value.json.return_value = {
            "models": [
                {"name": "llama2"},
                {"name": "codellama"},
            ]
        }
        mock_requests.get.return_value.status_code = 200

        backend = OllamaBackend(model="llama2")
        models = backend.list_models()

        assert "llama2" in models
        assert "codellama" in models

    def test_is_available_true(self, mock_requests):
        from r_cli.backends.ollama import OllamaBackend

        mock_requests.get.return_value.status_code = 200

        backend = OllamaBackend(model="llama2")
        assert backend.is_available() is True

    def test_is_available_false(self, mock_requests):
        from r_cli.backends.ollama import OllamaBackend

        mock_requests.get.side_effect = Exception("Connection refused")

        backend = OllamaBackend(model="llama2")
        assert backend.is_available() is False
