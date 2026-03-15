import subprocess
import time
from typing import Annotated, Literal, Optional
import shutil

from mcp.server.fastmcp import FastMCP

from pydantic import Field

import re
from .path_utils import safe_path, PROJECT_ROOT
import logging

logging.basicConfig(level=logging.WARNING)

mcp = FastMCP()


@mcp.tool()
async def run_commands(
        commands: Annotated[list[str], Field(description="要执行的命令列表")],
        rel_path: Annotated[str, Field(description="相对于项目根目录的路径，默认为根目录。")] = "",
        timeout: Annotated[int, Field(description="超时时间（秒）,默认10秒")] = 10):
    """在指定目录下执行多条命令"""
    p = safe_path(rel_path)

    if not p.exists() or not p.is_dir():
        raise ValueError("目录不存在")

    cmd = " && ".join(commands)

    process = subprocess.Popen(
        cmd,
        shell=True,
        cwd=p,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    start = time.time()
    output = []

    while True:
        line = process.stdout.readline()

        if line:
            print(line.strip())  # 实时打印
            output.append(line)

        if process.poll() is not None:
            break

        if time.time() - start > timeout:
            process.kill()
            return {
                "success": False,
                "stdout": "".join(output),
                "stderr": "Command timeout"
            }

    return {
        "stdout": "".join(output),
        "stderr": ""
    }


@mcp.tool()
def tree_dir(
        rel_path: Annotated[str, Field(description="相对于项目根目录的路径，默认为根目录。")] = ""
):
    """递归列出目录下所有文件和目录路径。"""

    p = safe_path(rel_path)

    return ",".join(
        str(x.relative_to(PROJECT_ROOT))
        for x in p.rglob("*")
    )


@mcp.tool()
def list_dir(rel_path: Annotated[str, Field(description="相对于项目根目录的路径，默认为根目录。")] = ""):
    """列出指定目录下的文件和子目录。"""
    p = safe_path(rel_path)
    return ",".join([x.name for x in p.iterdir()])


@mcp.tool()
def list_files(rel_path: Annotated[str, Field(description="相对于项目根目录的路径，默认为根目录。")] = "",
               pattern: Annotated[str, Field(description="文件匹配模式,如 *.py、*.txt，默认匹配所有文件。")] = "*"):
    """递归列出或查找指定目录下的所有文件。"""
    p = safe_path(rel_path)
    return ",".join([str(x.relative_to(PROJECT_ROOT)) for x in p.rglob(pattern) if x.is_file()])


@mcp.tool()
def patch_file(
        src: Annotated[str, Field(description="文件路径(相对于项目根目录)")],
        pattern: Annotated[str, Field(description="匹配模式")],
        content: Annotated[str, Field(description="要插入的内容")],
        position: Annotated[
            Literal["after", "before", "replace"],
            Field(description="插入位置")
        ] = "after"
):
    """通过正则表达式定位文件中的唯一匹配位置，并进行局部修改。
    匹配规则：
    - 允许 ^ 和 $ 匹配每一行的开头和结尾
    - 允许 `.` 匹配换行符，从而支持跨多行匹配
    逻辑：
    1. 若 pattern 未匹配到任何内容，则不执行修改。
    2. 若 pattern 匹配到多处，则不进行任何操作并返回错误。
    3. 若 pattern 仅匹配到一处，则根据 position 在匹配位置进行插入或替换。
    """
    p = safe_path(src)

    if not p.exists():
        return f"错误：文件 {p} 不存在"

    text = p.read_text(encoding="utf-8")

    # 使用正则查找所有匹配项
    # MULTILINE → 解决 “每一行”
    # DOTALL(S) → 解决 “跨多行”
    matches = list(re.finditer(pattern, text, re.MULTILINE | re.S))
    count = len(matches)

    # 场景 1：匹配不到 -> 全部重写（覆盖）
    if count == 0:
        return f"未匹配到 {pattern}, 未执行任何操作。"

    # 场景 2：匹配过多 -> 返回错误，防止歧义
    if count > 1:
        return f"错误：匹配到 {count} 处结果，请提供更精确的定位符。"

    # 场景 3：正好匹配到一个 -> 执行插入
    match = matches[0]
    start, end = match.span()

    if position == "after":
        # 在匹配内容后面换行插入
        new_text = text[:end] + f"{content}" + text[end:]
    elif position == "before":
        # 在匹配内容前面换行插入
        new_text = text[:start] + f"{content}" + text[start:]
    else:  # replace
        new_text = text[:start] + content + text[end:]

    p.write_text(new_text, encoding="utf-8")
    return f"已成功在定位点 {position} 插入内容。"


@mcp.tool()
def file_operation(
        action: Annotated[
            Literal["read", "write", "append", "delete", "copy", "move"],
            Field(description="操作类型")
        ],
        src: Annotated[
            str,
            Field(description="源路径(相对于项目根目录),默认为根目录")
        ] = "",
        dst: Annotated[
            Optional[str],
            Field(description="目标路径(复制/移动时需要)")
        ] = None,
        content: Annotated[
            Optional[str],
            Field(description="写入或追加的文本内容")
        ] = None
):
    """
    统一文件系统操作工具。支持 读取文件 (read)、覆盖写入文件 (write)、文件结尾追加写入 (append)、删除文件或目录 (delete)、复制文件或目录 (copy) 以及
    移动或重命名文件或目录 (move)。 所有路径均为相对于项目根目录的路径，其中 src 表示源路径，dst 表示目标路径（用于复制或移动操作），content
    用于写入或追加的文本内容。该工具会在需要时自动创建目标目录，并确保操作在项目根目录范围内执行。
    """
    src = src.replace(" ", "")
    if dst:
        dst = dst.replace(" ", "")
    p = safe_path(src)

    # READ
    if action == "read":
        if not p.exists():
            return f"文件不存在: {src}"
        return p.read_text(encoding="utf-8")

    # WRITE
    if action == "write":
        if content is None:
            return "write 操作需要 content"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"已写入文件: {src}"

    # APPEND
    if action == "append":
        if content is None:
            return "append 操作需要 content"
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write(content)
        return f"已追加写入: {src}"

    # DELETE
    if action == "delete":
        if not p.exists():
            return f"路径不存在: {src}"

        if p.is_file():
            p.unlink()
            return f"已删除文件: {src}"

        if p.is_dir():
            shutil.rmtree(p)
            return f"已删除目录: {src}"

    # COPY
    if action == "copy":
        if not dst:
            return "copy 操作需要 dst"
        if not p.exists():
            return f"文件不存在: {src}"
        dst_p = safe_path(dst)
        dst_p.parent.mkdir(parents=True, exist_ok=True)

        if p.is_file():
            shutil.copy2(p, dst_p)
        else:
            shutil.copytree(p, dst_p)

        return f"已复制: {src} -> {dst}"

    # MOVE
    if action == "move":
        if not dst:
            return "move 操作需要 dst"
        if not p.exists():
            return f"文件不存在: {src}"
        dst_p = safe_path(dst)
        dst_p.parent.mkdir(parents=True, exist_ok=True)

        shutil.move(p, dst_p)
        return f"已移动: {src} -> {dst}"

    return f"不支持的操作: {action}"


def main() -> None:
    mcp.run()
