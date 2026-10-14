"""Offline profile tests; sentinels are not credentials."""
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock,patch

MODULE=Path(__file__).resolve().parents[1]/'core/llm_runtime.py'
class ModelProfileTests(unittest.TestCase):
    def invoke(self,override,**kwargs):
        settings=types.SimpleNamespace(LLM_PROFILE_OVERRIDE=override,LLM_MODEL_NAME='configured-model',LLM_PROVIDER='openai',OPENAI_API_KEY='synthetic-openai-value',GOOGLE_API_KEY='synthetic-google-value',OPENAI_BASE_URL='http://127.0.0.1:9/v1',OLLAMA_URL='http://127.0.0.1:11434',LLM_TEMPERATURE=0.0,LLM_MAX_TOKENS=4096,LLM_TIMEOUT_SECONDS=60.0,LLM_MAX_RETRIES=2,LLM_TOP_P=0.9)
        factory=Mock();config=types.ModuleType('core.config');config.get_settings=lambda:settings
        chat=types.ModuleType('langchain.chat_models');chat.init_chat_model=factory
        spec=importlib.util.spec_from_file_location('model_profile_runtime',MODULE);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with patch.dict(sys.modules,{'core.config':config,'langchain.chat_models':chat}):module.create_chat_model(**kwargs)
        return factory.call_args
    def test_explicit_profile_replaces_hardcoded_gemini_for_local_experiment(self):
        call=self.invoke(True,model_name='gemini-2.5-flash',model_provider='google_genai',think_mode=True)
        self.assertEqual(call.args,('configured-model',));self.assertEqual(call.kwargs['model_provider'],'openai');self.assertEqual(call.kwargs['base_url'],'http://127.0.0.1:9/v1');self.assertEqual(call.kwargs['api_key'],'synthetic-openai-value');self.assertNotIn('include_thoughts',call.kwargs)
        self.assertEqual(call.kwargs['timeout'],60.0);self.assertEqual(call.kwargs['max_retries'],2);self.assertEqual(call.kwargs['temperature'],0.0)
    def test_native_gemini_arguments_are_preserved_without_override(self):
        call=self.invoke(False,model_name='gemini-2.5-flash',model_provider='google_genai',think_mode=True)
        self.assertEqual(call.args,('gemini-2.5-flash',));self.assertEqual(call.kwargs,{'model_provider':'google_genai','api_key':'synthetic-google-value','include_thoughts':True})
    def test_native_regulation_agent_does_not_gain_thinking_options(self):
        call=self.invoke(False,model_name='gemini-2.5-flash',model_provider='google_genai')
        self.assertNotIn('include_thoughts',call.kwargs)
if __name__=='__main__':unittest.main()
