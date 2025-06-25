# State of War 游戏资源解包工具

这是一个用于解包经典即时战略游戏《蓝色警戒》(State of War) 资源文件的Python脚本。它可以解析 `sprites.data` 和 `sprites.info`，提取原始的游戏资源，并能将其中复杂的图形文件（`.ps6`, `.sha`, `.msk`）转换为现代的PNG格式和包含元数据的YAML文件。本项目参考了StateOfWar-SpriteExtractor项目，在此基础上增加了阴影和掩码文件的提取。此项目没有图形界面和资源打包，主要面向开发者。本项目代码全部由AI生成。

## 功能特性

-   **资源提取**: 从 `sprites.data` 中提取所有独立的原始文件。
-   **`.ps6` 精灵解包**: 将16位色(RGB565)的精灵动画文件解包为带透明通道的PNG图片序列，并为每一帧生成一个包含坐标、尺寸等信息的YAML文件。
-   **`.sha` 阴影解包**: 将二值化的阴影文件解包为半透明的灰度PNG图片序列，并生成对应的YAML元数据文件。
-   **`.msk` 遮罩解包**: 将二值化的遮罩文件解包为灰度PNG图片序列，并生成对应的YAML元数据文件。
-   **灵活的解包模式**: 用户可以选择只提取原始文件、只生成PNG图片，或两者都做。

## 依赖库

运行此脚本前，请确保已安装以下Python库：

-   `Pillow`: 用于图像处理和PNG文件生成。
-   `PyYAML`: 用于生成和读取YAML元数据文件。

您可以使用pip进行安装：
```shell
pip install Pillow PyYAML
```

## 使用方法

将 `unpacker_v2.py` 脚本与游戏的 `sprites.data` 和 `sprites.info` 文件放置在同一目录下，然后通过命令行运行脚本。

### 命令行参数

-   `--data <路径>`: 指向 `sprites.data` 文件的路径。(默认: `sprites.data`)
-   `--info <路径>`: 指向 `sprites.info` 文件的路径。(默认: `sprites.info`)
-   `--output <目录>`: 指定所有解包文件的输出目录。(默认: `output`)
-   `--mode <模式>`: 选择解包模式，可选值为 `raw`, `png`, `both`。(默认: `both`)
    -   `raw`: 仅从 `sprites.data` 中提取原始文件，不进行任何转换。
    -   `png`: 仅将 `.ps6`, `.sha`, `.msk` 文件解包成PNG图片和YAML元数据，不保存原始文件。
    -   `both`: 执行 `raw` 和 `png` 的所有操作，既提取原始文件，也进行图片转换。

### 示例

1.  **完整解包（默认行为）**:
    提取所有原始文件，并将 `.ps6`, `.sha`, `.msk` 转换为PNG和YAML。
    ```shell
    python unpacker_v2.py
    ```
    或者明确指定模式：
    ```shell
    python unpacker_v2.py --mode both --output ./unpacked_files
    ```

2.  **仅提取原始文件**:
    如果你只需要游戏原本的 `.ps6`, `.sha` 等文件，而不需要PNG图片。
    ```shell
    python unpacker_v2.py --mode raw
    ```

3.  **仅生成PNG图片**:
    如果你不关心原始的 `.ps6` 文件，只想直接得到最终的PNG图片和元数据。
    ```shell
    python unpacker_v2.py --mode png
    ``` 