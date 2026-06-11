# -*- coding: utf-8 -*-
"""
@Author  : zhoushengjie
@Project : KeenRobot
@Module  : case_recommendation_view.py
@DateTime: 2026/6/11
"""
import asyncio
import csv
import os
import shutil
import tarfile
from typing import List

import aiofiles
import pandas as pd
from fastapi import APIRouter, BackgroundTasks, File, Form, UploadFile

from applications.zhoushengjie.services.claude_recommend_generator import (
    ClaudeTestCaseRecommendGenerator,
)
from configure import LOGGER, PROJECT_CONFIG
from core.responses import FailureResponse, SuccessResponse

case_recommendation_router = APIRouter()

_WORKSPACE_DIR = PROJECT_CONFIG.WORKSPACE_DIR


async def _save_upload_file(upload_file: UploadFile, dest_path: str, chunk_size: int):
    async with aiofiles.open(dest_path, "wb") as f:
        while True:
            chunk = await upload_file.read(chunk_size)
            if not chunk:
                break
            await f.write(chunk)
        await upload_file.close()


async def _run_claude_generation(project_id: str):
    """调用 Claude SDK 生成推荐测试用例。"""
    try:
        generator = ClaudeTestCaseRecommendGenerator()
        await generator.generate(project_id)
        LOGGER.info(f"Claude 推荐生成完成: {project_id}")
    except Exception as exc:
        LOGGER.exception(f"Claude 推荐生成失败: {exc}")
        base_dir = os.path.join(_WORKSPACE_DIR, "case_recommendation", project_id)
        error_file = os.path.join(base_dir, "error.txt")
        try:
            with open(error_file, "w", encoding="utf-8") as f:
                f.write(str(exc))
        except Exception:
            pass


def _post_process(base_dir: str, file_mapping: dict, project_id: str = ""):
    try:
        xlsx_to_csv_mapping = {
            "atpmCases": "atpm_case.csv",
            "caseExcel": "user_case.csv",
        }
        for name, csv_name in xlsx_to_csv_mapping.items():
            xlsx_path = os.path.join(base_dir, file_mapping.get(name, ""))
            if xlsx_path and os.path.exists(xlsx_path):
                try:
                    df = pd.read_excel(xlsx_path)
                    csv_path = os.path.join(base_dir, csv_name)
                    df.to_csv(csv_path, index=False, encoding="utf-8")
                    os.remove(xlsx_path)
                    LOGGER.info(f"转换 {name} 完成: {csv_path}")
                except Exception as e:
                    LOGGER.exception(f"转换 {name} 失败: {str(e)}")

        tar_path = os.path.join(base_dir, file_mapping.get("fullPackage", ""))
        extract_dir = os.path.join(base_dir, "code_coverage_file")
        if tar_path and os.path.exists(tar_path) and tarfile.is_tarfile(tar_path):
            os.makedirs(extract_dir, exist_ok=True)
            with tarfile.open(tar_path, "r") as tar:
                tar.extractall(path=extract_dir)

            report_dir = os.path.join(extract_dir, "report")
            increment_dir = os.path.join(report_dir, "increment")
            full_dir = os.path.join(report_dir, "full")

            if os.path.isdir(increment_dir):
                shutil.rmtree(increment_dir)

            if os.path.isdir(full_dir):
                for item in os.listdir(full_dir):
                    src = os.path.join(full_dir, item)
                    dst = os.path.join(extract_dir, item)
                    if os.path.exists(dst):
                        if os.path.isdir(dst):
                            shutil.rmtree(dst)
                        else:
                            os.remove(dst)
                    shutil.move(src, dst)
                shutil.rmtree(full_dir)

            if os.path.isdir(report_dir) and not os.listdir(report_dir):
                shutil.rmtree(report_dir)

        # 解压完成后调用 Claude 生成推荐用例
        if project_id:
            asyncio.create_task(_run_claude_generation(project_id))

    except Exception as e:
        LOGGER.exception(f"后台处理失败: {str(e)}")


def _read_csv_to_list(csv_path: str, case_type: str, project_id: str) -> List[dict]:
    rows = []
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            item = {
                "projectAiCodeTestScriptId": project_id,
                "testCaseNumber": row.get("testCaseNumber", ""),
                "testCaseName": row.get("testCaseName", ""),
                "applicationModel": row.get("applicationModel", ""),
                "priority": row.get("priority", ""),
                "testCaseType": row.get("testCaseType", ""),
                "feedbackStatus": row.get("feedbackStatus", ""),
                "type": case_type,
            }
            rows.append(item)
    return rows


@case_recommendation_router.post("/uploadCaseFiles", summary="上传用例推荐文件")
async def upload_case_files(
    ts: BackgroundTasks,
    atpmCases: UploadFile = File(...),
    caseExcel: UploadFile = File(...),
    projectAiCodeTestScriptId: str = Form(...),
    diffJson: UploadFile = File(...),
    fullPackage: UploadFile = File(...),
):
    chunk_size = 1024 * 1024 * 10
    try:
        base_dir = os.path.join(_WORKSPACE_DIR, "case_recommendation", projectAiCodeTestScriptId)
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir)
        os.makedirs(base_dir, exist_ok=True)

        file_mapping = {
            "atpmCases": "atpm_case.xlsx",
            "caseExcel": "user_case.xlsx",
            "diffJson": "diffCodeFiles.json",
            "fullPackage": fullPackage.filename,
        }

        upload_files = {
            "atpmCases": atpmCases,
            "caseExcel": caseExcel,
            "diffJson": diffJson,
            "fullPackage": fullPackage,
        }

        saved_paths = {}
        for name, upload_file in upload_files.items():
            dest_path = os.path.join(base_dir, file_mapping[name])
            await _save_upload_file(upload_file, dest_path, chunk_size)
            saved_paths[name] = dest_path

        ts.add_task(_post_process, base_dir, saved_paths, projectAiCodeTestScriptId)

        return SuccessResponse(data={"projectAiCodeTestScriptId": projectAiCodeTestScriptId})
    except Exception as e:
        LOGGER.exception(str(e))
        return FailureResponse(message=f"上传失败：{str(e)}")


@case_recommendation_router.post("/getCaseRecommendationResult", summary="获取用例推荐结果")
async def get_case_recommendation_result(projectAiCodeTestScriptId: str = Form(...)):
    base_dir = os.path.join(_WORKSPACE_DIR, "case_recommendation", projectAiCodeTestScriptId)

    if not os.path.exists(base_dir):
        return FailureResponse(message="projectAiCodeTestScriptId不存在")

    error_file = os.path.join(base_dir, "error.txt")
    if os.path.exists(error_file):
        with open(error_file, "r", encoding="utf-8") as f:
            error_msg = f.read()
        return FailureResponse(message=error_msg or "处理过程中发生错误")

    ai_cases_path = os.path.join(base_dir, "ai_cases.csv")
    recommended_cases_path = os.path.join(base_dir, "recommended_cases.csv")

    result = []

    if os.path.exists(recommended_cases_path):
        result.extend(_read_csv_to_list(recommended_cases_path, "1", projectAiCodeTestScriptId))
    if os.path.exists(ai_cases_path):
        result.extend(_read_csv_to_list(ai_cases_path, "2", projectAiCodeTestScriptId))

    if not result:
        return SuccessResponse(data=[], message="正在生成中，请稍后")

    return SuccessResponse(data=result)
