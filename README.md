## 该mcp用于赋予ai操作电脑文件的能力

- PROJECT_ROOT表示操作电脑哪个目录下的文件
- ai只能操作PROJECT_ROOT目录下的文件

## 代码配置方式：
```
[[stdio_list]]
args = ["wgk-mcp-file"]
command = "uvx"
[stdio_list.env]
PROJECT_ROOT = "C:\\Users\\xxx\\Desktop\\test"
```
## 客户端配置方式：
```
{
  "mcpServers": {
    "demo": {
      "command": "uvx",
      "args": ["wgk-mcp-file"],
      "env": {
        "PROJECT_ROOT": "C:\\Users\\xxx\\Desktop\\test"
      }
    }
  }
}
```
