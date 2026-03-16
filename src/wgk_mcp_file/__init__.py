import subprocess
from typing import Annotated, Literal, Optional
import shutil
from mcp.server.fastmcp import FastMCP
from pydantic import Field
from .path_utils import safe_path, PROJECT_ROOT
import logging

logging.basicConfig(level=logging.WARNING)
mcp = FastMCP()


@mcp.tool()
async def run_commands(
        command: Annotated[str, Field(description="要执行的命令,多个命令用 && 连接")],
        rel_path: Annotated[str, Field(description="相对于项目根目录的路径，默认为根目录。")] = ""):
    # timeout: Annotated[int, Field(description="超时时间（秒）,默认10秒")] = 10)
    """
    该工具用于执行Windows系统的cmd命令.
    特点：
    - 每次调用都是独立执行环境，不会记住之前的工作目录。
    - 必须通过 rel_path 指定要执行命令的目录。
    - 多个命令会按顺序执行。
    限制：
    - 不要执行长期运行的命令，例如：
      - npm run dev
      - python app.py
      - vite
      - docker run
      这些命令不会退出，会导致死循环。
  """
    p = safe_path(rel_path)

    if not p.exists() or not p.is_dir():
        return f"相对路径不存在: {rel_path}"
    # 禁止明显危险命令
    dangerous = ["rm", "del", "shutdown", "reboot", "mkfs", "format"]
    for cmd in command:
        for bad in dangerous:
            if cmd.lower().startswith(bad):
                return f"检测到危险命令: {cmd}, 拒绝执行"
    # 过滤掉以 cd 开头的命令
    # commands = [c for c in commands if not c.strip().startswith("cd ")]
    # cmd = " && ".join(commands)

    result = subprocess.run(
        command,
        shell=True,
        cwd=p,
        capture_output=True,
        stdin=subprocess.DEVNULL,  # 关键：禁用交互
        errors="ignore"
    )

    return {
        "stdout": result.stdout,
        "stderr": result.stderr
    }


@mcp.tool()
def search_file(
        pattern: Annotated[
            str, Field(description="文件/目录名匹配模式，支持通配符，如 *.py 或 *test*")],
        rel_path: Annotated[str, Field(description="相对于项目根目录的路径，默认为根目录。")] = "",
):
    """递归查找指定目录下的目录或文件，按模式过滤。"""
    if pattern == "*":
        return "不允许使用*来匹配所有文件,会造成性能问题"
    p = safe_path(rel_path)
    return ",".join(
        str(x.relative_to(PROJECT_ROOT))
        for x in p.rglob(pattern)
    )


@mcp.tool()
def get_project_root():
    """获取项目根目录的路径"""
    return PROJECT_ROOT


@mcp.tool()
def list_dir(
        rel_path: Annotated[str, Field(description="相对于项目根目录的路径，默认为根目录。")] = "",
        pattern: Annotated[str, Field(description="目录/文件名匹配模式，支持通配符，如 test*，默认匹配所有。")] = "*"
):
    """列出指定目录下的文件和子目录，可按模式过滤。"""
    p = safe_path(rel_path)
    return ",".join([x.name for x in p.iterdir() if x.match(pattern)])


# @mcp.tool()
# def list_files(
#         rel_path: Annotated[str, Field(description="相对于项目根目录的路径，默认为根目录。")] = "",
#         pattern: Annotated[str, Field(description="文件名匹配模式,如 *.py、*.txt，默认匹配所有文件。")] = "*"
# ):
#     """递归列出或查找指定目录下的文件，可按模式过滤。"""
#     p = safe_path(rel_path)
#     return ",".join([str(x.relative_to(PROJECT_ROOT)) for x in p.rglob(pattern) if x.is_file()])


@mcp.tool()
def patch_file(
        src: Annotated[str, Field(description="文件路径(相对于项目根目录)")],
        original_content: Annotated[str, Field(description="原始文件内容")],
        new_content: Annotated[str, Field(
            description="用于替换的新内容"
        )]
):
    """通过原文内容匹配文件中的唯一位置，并进行替换。
    """
    p = safe_path(src)
    if not p.exists():
        return f"错误：文件 {p} 不存在"
    text = p.read_text(encoding="utf-8")
    count = text.count(original_content)
    if count == 0:
        return "未匹配到指定内容，未执行任何操作。"
    elif count > 1:
        return f"匹配到 {count} 处，操作取消，请确保原文内容唯一。"
    new_text = text.replace(original_content, new_content, 1)
    p.write_text(new_text, encoding="utf-8")
    return "已成功替换。"


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
