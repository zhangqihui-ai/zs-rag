from app.services.chat_service import should_skip_knowledge_retrieval


def test_skip_capability_and_greeting_queries() -> None:
    assert should_skip_knowledge_retrieval("你能做什么？")
    assert should_skip_knowledge_retrieval("你好")
    assert should_skip_knowledge_retrieval("你是谁")
    assert should_skip_knowledge_retrieval("What can you do?")


def test_do_not_skip_domain_questions() -> None:
    assert not should_skip_knowledge_retrieval("故意杀人怎么判刑")
    assert not should_skip_knowledge_retrieval("新生儿医保怎么办")
    assert not should_skip_knowledge_retrieval("帮我查一下刑法第234条")
