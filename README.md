# Lane Annotator

基于 PyQt5 的交互式车道线标注工具，支持 CULane 和 TuSimple 两种数据集格式。

## 功能

- 加载图片与车道线标签
- 在可视化界面上拖拽控制点调整标签位置
- 支持新增、删除、复制车道线
- 支持新增、删除控制点
- 撤销 / 重做（Ctrl+Z / Ctrl+Y）
- 将调整后的标签保存为原始格式，输出到新目录
- 支持 CULane 和 TuSimple 两种格式

## 安装依赖

创建最小 conda 环境：

```bash
conda create -n lane_annotator python=3.9 -y
conda activate lane_annotator
pip install PyQt5 numpy
pip install opencv-python-headless
```

## 使用方法

进入 `lane_annotator` 目录后运行：

### CULane 批量模式

```bash
cd lane_annotator
python main.py \
    --format culane \
    --list /path/to/data/CULane/list/test.txt \
    --img-root /path/to/data/CULane \
    --gt-root /path/to/data/CULane \
    --out /path/to/output/annotated_culane
```

### CULane 单张模式

```bash
python main.py \
    --format culane \
    --img /path/to/data/CULane/driver_193_90frame/06042022_0515.MP4/00990.jpg \
    --label /path/to/data/CULane/driver_193_90frame/06042022_0515.MP4/00990.lines.txt \
    --out /path/to/output/annotated_single
```

### TuSimple 数据集目录结构

TuSimple 数据应按以下结构组织（与 CLRNet 要求一致）：

```
data/tusimple/
├── clips/
│   ├── 0313-1/
│   ├── 0313-2/
│   ├── 0530/
│   ├── 0531/
│   └── 0601/
├── seg_label/
├── label_data_0313.json
├── label_data_0531.json
├── label_data_0601.json
└── test_label.json
```

JSON 文件中的 `raw_file` 应为 `clips/...` 格式，与 `clips/` 目录对应。

### TuSimple 批量模式

```bash
python main.py \
    --format tusimple \
    --json /path/to/data/tusimple/label_data_0601.json \
    --img-root /path/to/data/tusimple \
    --out /path/to/output/annotated_tusimple
```

### TuSimple 单张模式

```bash
python main.py \
    --format tusimple \
    --json /path/to/data/tusimple/test_label.json \
    --img-root /path/to/data/tusimple \
    --img /path/to/data/tusimple/clips/0530/1492626760788443246_0/20.jpg \
    --out /path/to/output/annotated_tusimple_single
```

单张模式下只更新该图片对应的 JSON 记录，其他记录保持不变。

也支持通过 `python -m lane_annotator` 运行（需确保当前目录是 `lane_annotator` 的父目录）：

```bash
cd /path/to/parent
python -m lane_annotator --help
```

## 快捷键

| 操作 | 快捷键 |
|---|---|
| 保存当前 | Ctrl+S |
| 保存全部 | Ctrl+Shift+S |
| 撤销 | Ctrl+Z |
| 重做 | Ctrl+Y |
| 新增车道线 | A / 工具栏 Add |
| 删除选中点/车道线 | Delete |
| 插入控制点 | Shift + 点击车道线 |
| 完成新增车道线 | Enter |
| 取消新增车道线 | Esc |
| 上一张 | ← |
| 下一张 | → |
| 缩放 | 滚轮 |
| 平移 | 中键拖动 |
| 适应窗口 | F / 双击中键 |

## CULane 与 TuSimple 编辑差异

- **CULane**：控制点可自由二维拖动，可新增/删除 y 位置。
- **TuSimple**：y 坐标由 `h_samples` 固定，只能水平拖动修改 x；无效点（`-2`）可通过 "Toggle Validity" 激活后拖动。

## 输出说明

所有修改默认保存到 `--out` 指定目录，原标签文件不会被覆盖。输出目录结构与输入保持一致。

保存标签的同时，会额外生成可视化图片，保存在 `--out/visualization/` 目录下：

```
output/annotated_culane/
├── driver_193_90frame/
│   └── .../
│       ├── 00000.lines.txt
│       └── 00090.lines.txt
└── visualization/
    └── driver_193_90frame/
        └── .../
            ├── 00000.jpg
            └── 00090.jpg
```

可视化图片上绘制了调整后的车道线和控制点，方便直接查看标注效果。
