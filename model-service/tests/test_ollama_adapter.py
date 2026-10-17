import httpx
import pytest

from app.adapters.ollama_adapter import OllamaAdapter


def adapter_with_response(body):
    adapter = OllamaAdapter("gemma4:e2b")
    adapter._http.close()
    adapter._http = httpx.Client(base_url="http://localhost", transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json=body)))
    return adapter


def test_unfinished_or_empty_model_output_is_not_accepted():
    for body in ({"done": False, "message": {"content": "yarım"}},
                 {"done": True, "message": {"content": " "}}):
        adapter = adapter_with_response(body)
        with pytest.raises(RuntimeError):
            adapter.generate([{"role": "user", "content": "Merhaba"}], 20, None)
        adapter._http.close()


def test_real_output_keeps_token_counts_and_duration():
    adapter = adapter_with_response({"done": True, "message": {"content": " Merhaba! "},
                                     "eval_count": 4, "prompt_eval_count": 8, "eval_duration": 1_500_000_000})
    result = adapter.generate([{"role": "user", "content": "Merhaba"}], 20, None)
    assert result == {"text": "Merhaba!", "new_tokens": 4, "input_tokens": 8, "seconds": 1.5}
    adapter._http.close()


def test_audio_is_rejected_instead_of_silently_dropped():
    adapter = adapter_with_response({})
    with pytest.raises(ValueError, match="yazılı"):
        adapter.generate([{"role": "user", "content": [{"type": "audio", "audio": "test.wav"}]}], 20, None)
    adapter._http.close()
