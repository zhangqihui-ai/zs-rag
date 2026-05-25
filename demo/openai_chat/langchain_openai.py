"""
OpenAI LLM Configuration
OpenAI 大语言模型配置模块

模块功能：
- 提供 OpenAI 大语言模型的创建和配置接口
- 支持流式对话
- 支持环境变量配置
- 提供默认配置参数

设计参考：
- 基于 LangChain 的 ChatOpenAI 实现
- 使用环境变量管理 API 密钥和 URL
- 提供灵活的模型参数配置

主要组件：
- create_llm: LLM 创建函数
- test_stream_chat: 流式对话测试函数

作者：TaskFlow Team
版本：1.0.0
"""

import os
from typing import Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage


def create_llm(
    model: str = "gpt-4o",
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    temperature: float = 0.7,
    streaming: bool = False,
    **kwargs
) -> ChatOpenAI:
    """
    创建 LLM 实例
    
    创建并配置一个 ChatOpenAI 实例。
    
    参数：
        model: 模型名称，默认 "gpt-4o"
        api_key: API 密钥（可选，默认从环境变量 OPENAI_API_KEY 读取）
        base_url: API 基础 URL（可选，默认从环境变量 OPENAI_BASE_URL 读取）
        temperature: 温度参数，默认 0.7
        streaming: 是否启用流式输出，默认 False
        **kwargs: 其他参数，传递给 ChatOpenAI
    
    返回：
        配置完成的 ChatOpenAI 实例
    
    示例：
        >>> llm = create_llm(model="gpt-4o", temperature=0.5)
        >>> llm = create_llm(api_key="your-key", base_url="https://api.example.com/v1")
    
    """
    return ChatOpenAI(
        model=model,
        api_key=api_key or os.getenv("OPENAI_API_KEY"),
        base_url=base_url or os.getenv("OPENAI_BASE_URL"),
        temperature=temperature,
        streaming=streaming,
        **kwargs
    )


def test_stream_chat() -> None:
    """
    流式对话测试
    
    测试 OpenAI 模型的流式对话功能。
    
    参数：
        messages: 消息列表，默认为测试消息
        model: 模型名称
        api_key: API 密钥
        base_url: API 基础 URL
        temperature: 温度参数
    
    示例：
        >>> test_stream_chat()
        >>> test_stream_chat(messages=[HumanMessage(content="你好")])
    
    """
    
    messages = [
        SystemMessage(content="你是一个有用的AI助手。"),
        HumanMessage(content="请简单介绍一下你自己。"),
    ]

    llm = create_llm(
        model='glm-5',
        api_key='sk-sp-eb5a4ad1e32248a7b0f5fc408fd6ffb9',
        base_url='https://coding.dashscope.aliyuncs.com/v1',
        temperature='0.7',
        streaming=True,
    )

    print("=" * 50)
    print("开始流式对话测试...")
    print("=" * 50)

    full_response = ""
    for chunk in llm.stream(messages):
        if hasattr(chunk, "content") and chunk.content:
            print(chunk.content, end="", flush=True)
            full_response += chunk.content

    print("\n" + "=" * 50)
    print(f"完整回复长度: {len(full_response)} 字符")
    print("=" * 50)

    return full_response


if __name__ == "__main__":
    test_stream_chat()
