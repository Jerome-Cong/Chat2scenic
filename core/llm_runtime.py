"""Resolve an explicit local model profile without changing native defaults."""
def create_chat_model(model_name=None, model_provider=None, think_mode=None):
    from langchain.chat_models import init_chat_model
    from core.config import get_settings
    settings=get_settings()
    override=settings.LLM_PROFILE_OVERRIDE
    name=settings.LLM_MODEL_NAME if override else (model_name or settings.LLM_MODEL_NAME)
    provider=settings.LLM_PROVIDER if override else (model_provider or settings.LLM_PROVIDER)
    options={"model_provider":provider}
    if provider=="ollama":
        options["base_url"]=settings.OLLAMA_URL
    elif provider=="google_genai":
        if not settings.GOOGLE_API_KEY:raise ValueError("Google model credential is not configured")
        options["api_key"]=settings.GOOGLE_API_KEY
        if think_mode is not None:options["include_thoughts"]=think_mode
    elif provider=="openai":
        if not settings.OPENAI_API_KEY:raise ValueError("OpenAI-compatible model credential is not configured")
        options["api_key"]=settings.OPENAI_API_KEY
        if settings.OPENAI_BASE_URL:options["base_url"]=settings.OPENAI_BASE_URL
    else:
        raise ValueError("Unsupported configured model provider: "+provider)
    if override:
        options.update(temperature=settings.LLM_TEMPERATURE,max_tokens=settings.LLM_MAX_TOKENS,timeout=settings.LLM_TIMEOUT_SECONDS,max_retries=settings.LLM_MAX_RETRIES)
        if provider=="openai":options["top_p"]=settings.LLM_TOP_P
    return init_chat_model(name,**options)
