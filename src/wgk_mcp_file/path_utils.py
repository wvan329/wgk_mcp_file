from pathlib import Path


def find_project_root(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / "资料").exists():
            return p / "资料"
    raise RuntimeError("Project root not found")


PROJECT_ROOT = find_project_root(Path(__file__).resolve())


def root_path(*paths) -> Path:
    """获取基于项目根目录的 Path"""
    return PROJECT_ROOT.joinpath(*paths)


def safe_path(rel_path: str) -> Path:
    # resolve()会将路径中的..和.解析掉,并返回绝对路径, 不会出现:a/../../b
    # 此时p的parents里是不会有a的, 否则a/../../b的parents里就会有a
    p = root_path(rel_path).resolve()
    if PROJECT_ROOT not in p.parents and p != PROJECT_ROOT:
        raise ValueError("Path escapes project root")
    return p
