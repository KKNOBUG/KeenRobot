# -*- coding: utf-8 -*-
"""
@Author  : weixianzhe
@Project : KeenRobot
@Module  : claude_generator.py
@DateTime: 2026/6/11
"""
import asyncio
import os
from dataclasses import replace

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKClient,
    HookMatcher,
    ResultMessage,
)

from applications.weixianzhe.services.agent_hooks import guard_bash_rm
from configure import PROJECT_CONFIG


class ClaudeTestCaseGenerator:
    async def generate(self, source_path: str, output_dir: str = "") -> str:
        prompt = (
            f"请读取 {source_path} 中的所有docx文档，按照 skill 的要求生成测试案例。"
            f"所有输出产物保存到 {output_dir} 目录。"
        )

        base_options = ClaudeAgentOptions(
            max_turns=400,
            skills=["test-case-generator"],
            system_prompt=(
                f"[输出目录] 本次任务的所有输出产物必须保存到：{output_dir}\n"
                "[自动化模式] 这是后台自动执行任务，没有用户可回答你的问题。\n"
                "遇到需要用户确认的步骤时（如系统类型匹配确认），请跳过确认、自动使用默认策略或最高匹配策略继续执行。\n"
                "不要询问用户任何问题，用 '默认策略' 或自动选择第一个可用选项继续。"
            ),
            allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
            setting_sources=["project"],
            hooks={
                "PreToolUse": [
                    HookMatcher(matcher="Bash", hooks=[guard_bash_rm])
                ]
            },
            disallowed_tools=["AskUserQuestion"],
            cwd=os.getcwd(),
        )

        models = PROJECT_CONFIG.TEST_CASE_MODEL_POOL.split(";")
        timeout = PROJECT_CONFIG.TEST_CASE_MODEL_TIMEOUT
        last_error = ""

        for model in models:
            options = replace(base_options, model=model)
            try:
                result_text = await asyncio.wait_for(
                    self._run_session(options, prompt),
                    timeout=timeout,
                )
                return result_text

            except asyncio.TimeoutError:
                last_error = f"模型 {model} 执行超时（{timeout}秒）"
                continue
            except Exception as exc:
                last_error = f"模型 {model} 执行失败: {exc}"
                continue

        raise RuntimeError(f"所有模型均失败，最后错误：{last_error}")

    async def _run_session(
        self, options: ClaudeAgentOptions, prompt: str
    ) -> str:
        client = ClaudeSDKClient(options=options)
        try:
            await client.connect(prompt=prompt)
            result_text = ""
            async for message in client.receive_response():
                if isinstance(message, ResultMessage):
                    result_text = message.result or ""
            if not result_text:
                raise RuntimeError("Claude Agent SDK returned empty result")
            return result_text
        finally:
            await client.disconnect()
