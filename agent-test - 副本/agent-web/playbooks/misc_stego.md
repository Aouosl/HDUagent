# Misc / 隐写术 — 标准操作流程

## Phase 1: 文件基础分析

```bash
# 1. 文件类型和元数据
file <target>
exiftool <target>        # EXIF 元数据（可能藏信息在 Comment 等字段）
xxd <target> | head -20  # 查看文件头

# 2. 字符串搜索
strings <target> | grep -iE "(flag|ctf|key|secret|hint)"
strings -n 20 <target>   # 长字符串，可能是编码数据

# 3. 嵌入文件检测
binwalk <target>
binwalk -e <target>      # 自动提取嵌入文件
foremost -i <target> -o /tmp/carved
```

## Phase 2: 图片隐写

### PNG 文件：
```bash
# 1. 检查 PNG 结构
pngcheck -v <image>.png

# 2. LSB 隐写
zsteg <image>.png        # 检查所有通道的 LSB
zsteg -a <image>.png     # 更详细的分析

# 3. 检查 IDAT 块
python3 -c "
import struct, zlib
data = open('<image>.png', 'rb').read()
# 检查是否有额外数据在 IEND 之后
iend = data.find(b'IEND')
if iend != -1 and iend + 12 < len(data):
    print(f'Extra data after IEND: {data[iend+12:][:100]}')
"
```

### JPEG 文件：
```bash
# 1. steghide（需要密码，先试空密码）
steghide extract -sf <image>.jpg -p ""
steghide info <image>.jpg

# 2. jsteg
jsteg reveal <image>.jpg output.txt

# 3. 检查 JPEG 注释段
python3 -c "
data = open('<image>.jpg', 'rb').read()
# APP0 之后可能有隐藏数据
print(data[:100])
"
```

### GIF 文件：
```bash
# 检查帧数和帧间隔
identify -verbose <image>.gif
# 提取所有帧
convert <image>.gif -coalesce frame_%03d.png
```

## Phase 3: 音频隐写

```bash
# 1. 频谱分析（频谱图中可能藏有文字/图案）
# 使用 Audacity 打开，切换到频谱视图
sox <audio> -n spectrogram -o /tmp/spectrogram.png

# 2. LSB 音频隐写
# 使用 WavSteg 或手动提取

# 3. DTMF 解码
multimon-ng -t wav -a DTMF <audio>.wav

# 4. 摩尔斯电码
# 听音频判断是否有长短音模式
```

## Phase 4: 压缩包与编码

```bash
# 1. ZIP 文件
unzip -l <file>.zip      # 列出内容
# 如果有密码：
fcrackzip -b -c 'aA1' -l 1-8 <file>.zip   # 暴力破解
john --wordlist=/usr/share/wordlists/rockyou.txt zip_hash.txt

# 2. 多层编码
# 常见套路：Base64 → Hex → ROT13 → Flag
# 逐层尝试解码

# 3. 特殊编码
# Brainfuck、Ook!、JSFuck、零宽字符等
# 使用在线工具或专用解码器
```

## Phase 5: 写结论

**结论必须包含：**
1. **文件信息**：类型、大小、元数据
2. **分析方法**：使用了哪些工具和技术
3. **隐藏内容**：发现了什么
4. **Flag**（如果找到）

## 常见陷阱

| 陷阱 | 应对 |
|------|------|
| steghide 需要密码 | 先试空密码，再看题目描述中的提示词 |
| 图片看起来正常 | 对比通道、调整亮度对比度、检查 LSB |
| 压缩包套压缩包 | 可能需要写脚本自动解套 |
| 编码套编码 | 用 CyberChef 的 Magic 模式自动识别 |
