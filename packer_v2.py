#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
StateOfWar资源打包工具
用于将解包的文件夹重新打包为sprites.data和sprites.info文件
支持打包原始文件和从PNG+YAML元数据重建资源
"""

import os
import struct
import yaml
from PIL import Image
import argparse
from collections import defaultdict

class SpritePacker:
    """资源打包器"""
    
    def __init__(self, input_dir, debug=False):
        """
        初始化打包器
        
        Args:
            input_dir: 解包后的文件目录
            debug: 是否启用调试输出
        """
        self.input_dir = input_dir
        self.resources = []
        self.data_buffer = bytearray()
        self.debug = debug
        
    def scan_directory(self):
        """扫描目录，收集所有需要打包的资源"""
        print("扫描目录中的资源文件...")
        
        # 用于存储将要处理的所有资源路径，避免重复处理
        processed_paths = set()
        
        # 遍历整个目录
        for root, dirs, files in os.walk(self.input_dir):
            # 检查当前目录是否是shadows或masks
            current_dir = os.path.basename(root)
            if current_dir in ['shadows', 'masks']:
                if self.debug:
                    print(f"跳过目录: {root} (shadows/masks目录将被忽略)")
                continue  # 跳过shadows和masks目录
            
            # 处理从PNG+YAML重建的资源，仅处理ps6文件
            png_yaml_groups = defaultdict(list)
            
            # 先收集所有yaml/png对，确定它们的资源类型
            for f in files:
                if f.endswith('.yaml'):
                    base_name = os.path.splitext(f)[0]
                    png_file = base_name + '.png'
                    if os.path.exists(os.path.join(root, png_file)):
                        # 提取基础名称(不包含帧号)
                        parts = base_name.split('_')
                        if parts[-1].isdigit():
                            resource_name = '_'.join(parts[:-1])
                            frame_id = int(parts[-1])
                            
                            # 只处理PS6文件，忽略SHA和MSK
                            res_type = 'ps6'
                            rel_path = os.path.relpath(root, self.input_dir)
                            if rel_path == '.':
                                rel_path = ''
                            resource_path = os.path.join(rel_path, resource_name + '.ps6')
                            
                            # 将此资源路径标记为已处理
                            processed_paths.add(resource_path.lower())
                            
                            png_yaml_groups[(resource_name, res_type, resource_path)].append((frame_id, f, png_file))
            
            # 处理收集到的PNG+YAML组 (只有PS6)
            for (resource_name, res_type, resource_path), frames in png_yaml_groups.items():
                # 按帧ID排序
                frames.sort(key=lambda x: x[0])
                
                if self.debug:
                    print(f"发现PS6资源 {resource_path}，包含 {len(frames)} 个帧")
                    for frame_id, yaml_file, png_file in frames:
                        print(f"  帧 {frame_id}: {yaml_file} + {png_file}")
                
                # 添加到资源列表
                self.resources.append({
                    'name': resource_path,
                    'type': 'png_yaml',
                    'res_type': res_type,
                    'frames': frames,
                    'root': root
                })
            
            # 处理所有原始文件（包括.sha和.msk文件）
            for f in files:
                if not f.endswith(('.yaml', '.png')):  # 跳过yaml和png文件
                    file_path = os.path.join(root, f)
                    rel_path = os.path.relpath(file_path, self.input_dir)
                    
                    # 处理PS6文件 - 如果有对应的PNG已处理则跳过
                    if f.endswith('.ps6') and rel_path.lower() in processed_paths:
                        if self.debug:
                            print(f"跳过已处理的PS6文件: {rel_path}")
                        continue
                    
                    # 保留所有.sha和.msk文件
                    if f.endswith(('.sha', '.msk')) or not f.endswith('.ps6'):
                        self.resources.append({
                            'name': rel_path,
                            'type': 'raw',
                            'file_path': file_path
                        })
                        
                        if self.debug:
                            ext = os.path.splitext(f)[1].lower()
                            if ext in ['.sha', '.msk']:
                                print(f"添加原始{ext}文件: {rel_path}")
                            else:
                                print(f"添加其他原始文件: {rel_path}")
        
        print(f"找到 {len(self.resources)} 个资源")
    
    def pack_raw_file(self, resource):
        """
        打包原始文件
        
        Args:
            resource: 资源信息字典
        
        Returns:
            (offset, length): 在data_buffer中的偏移量和长度
        """
        with open(resource['file_path'], 'rb') as f:
            data = f.read()
        
        offset = len(self.data_buffer)
        self.data_buffer.extend(data)
        return offset, len(data)
    
    def pack_ps6_from_images(self, resource):
        """
        从PNG图像和YAML元数据重建.ps6文件
        
        Args:
            resource: 资源信息字典
        
        Returns:
            (offset, length): 在data_buffer中的偏移量和长度
        """
        offset = len(self.data_buffer)
        start_size = len(self.data_buffer)
        
        if self.debug:
            print(f"\n打包PS6资源: {resource['name']}")
            print(f"帧数量: {len(resource['frames'])}")
        
        for frame_id, yaml_file, png_file in resource['frames']:
            if self.debug:
                print(f"\n处理帧 {frame_id}:")
            
            with open(os.path.join(resource['root'], yaml_file), 'r', encoding='utf-8') as f:
                metadata = yaml.safe_load(f)
            
            img = Image.open(os.path.join(resource['root'], png_file)).convert('RGBA')
            width, height = img.size
            
            if self.debug:
                print(f"  尺寸: {width}x{height}")
                print(f"  原点: ({metadata['origin_x']}, {metadata['origin_y']})")
            
            # 帧大小占位，稍后更新
            frame_size_pos = len(self.data_buffer)
            self.data_buffer.extend(struct.pack('<I', 0))
            
            # 帧头信息
            self.data_buffer.extend(struct.pack('<H', width))  # width
            self.data_buffer.extend(struct.pack('<H', height))  # height
            self.data_buffer.extend(struct.pack('<H', metadata['origin_x']))  # origin_x
            self.data_buffer.extend(struct.pack('<H', metadata['origin_y']))  # origin_y
            self.data_buffer.extend(struct.pack('<H', metadata['unknown1']))  # unk1
            self.data_buffer.extend(struct.pack('<H', metadata['unknown2']))  # unk2
            self.data_buffer.extend(struct.pack('<H', metadata['unknown3']))  # unk3
            self.data_buffer.extend(struct.pack('<H', metadata['unknown4']))  # unk4
            
            # 为所有行预留偏移量空间
            offsets_start = len(self.data_buffer)
            line_offsets = []
            for _ in range(height):
                self.data_buffer.extend(struct.pack('<I', 0))
                line_offsets.append(len(self.data_buffer))
            
            # 计算第一行数据的偏移量(以"short"为单位)
            first_line_offset = (len(self.data_buffer) - frame_size_pos) // 2
            
            # 写入每行的数据
            for y in range(height):
                # 记录当前行的起始位置
                line_start_pos = len(self.data_buffer)
                
                # 计算当前行的偏移量(相对于帧起始位置，以short为单位)
                current_offset = (line_start_pos - frame_size_pos) // 2
                
                # 更新行偏移量
                self.data_buffer[offsets_start + y * 4:offsets_start + y * 4 + 4] = struct.pack('<I', current_offset)
                
                if self.debug and y < 3:  # 只显示前几行的详细信息
                    print(f"\n  行 {y} 偏移量: {current_offset} shorts")
                
                # 分析当前行的像素数据
                line = []
                x = 0
                in_skip = True  # 默认开始是跳过模式（透明）
                count = 0
                pixels_to_write = []
                
                # 分析一行像素
                while x < width:
                    r, g, b, a = img.getpixel((x, y))
                    is_skip = (a < 128)  # 透明度低于128认为是透明像素
                    
                    if (in_skip and is_skip) or (not in_skip and not is_skip):
                        # 继续当前模式
                        count += 1
                        if not is_skip:
                            # 将RGB转换为RGB565格式
                            r5 = (r >> 3) & 0x1F
                            g6 = (g >> 2) & 0x3F
                            b5 = (b >> 3) & 0x1F
                            color565 = (r5 << 11) | (g6 << 5) | b5
                            pixels_to_write.append(color565)
                    else:
                        # 模式切换
                        if not in_skip:
                            # 写入模式，保存颜色值
                            line.append((in_skip, count, pixels_to_write))
                            pixels_to_write = []
                        else:
                            # 跳过模式，不需要颜色值
                            line.append((in_skip, count, []))
                        
                        in_skip = not in_skip
                        count = 1
                        
                        if not is_skip:
                            # 当前像素不透明，准备写入颜色
                            r5 = (r >> 3) & 0x1F
                            g6 = (g >> 2) & 0x3F
                            b5 = (b >> 3) & 0x1F
                            color565 = (r5 << 11) | (g6 << 5) | b5
                            pixels_to_write.append(color565)
                    
                    x += 1
                
                # 添加最后一段
                if count > 0:
                    if not in_skip:
                        line.append((in_skip, count, pixels_to_write))
                    else:
                        line.append((in_skip, count, []))
                
                if self.debug and y < 3:
                    print(f"    RLE段: {[(mode, cnt, len(pixels)) for mode, cnt, pixels in line]}")
                
                # 写入命令数量
                self.data_buffer.extend(struct.pack('<H', len(line)))
                
                # 写入初始模式，与unpacker_v2.py中的模式保持一致:
                # is_skip_mode_first = read_short() == 0
                # 即，如果read_short()返回0，是跳过模式
                is_skip_first = 0 if line[0][0] else 1  # 如果第一个段是跳过段，写入0，否则写入1
                self.data_buffer.extend(struct.pack('<H', is_skip_first))
                
                if self.debug and y < 3:
                    print(f"    命令数: {len(line)}, 初始模式: {is_skip_first} (0=跳过,1=写入)")
                
                # 写入每个命令
                for is_skip, count, pixels in line:
                    self.data_buffer.extend(struct.pack('<H', count))
                    
                    if not is_skip:
                        # 写入模式，需要写入所有像素的颜色值
                        for color565 in pixels:
                            self.data_buffer.extend(struct.pack('<H', color565))
            
            # 更新帧大小
            frame_size = len(self.data_buffer) - frame_size_pos
            self.data_buffer[frame_size_pos:frame_size_pos + 4] = struct.pack('<I', frame_size)
            
            if self.debug:
                print(f"  帧大小: {frame_size} 字节")
        
        # 结束标记
        self.data_buffer.extend(struct.pack('<I', 0))
        
        if self.debug:
            print(f"资源总大小: {len(self.data_buffer) - start_size} 字节")
        
        return offset, len(self.data_buffer) - start_size
    
    def pack_binary_rle_from_images(self, resource):
        """
        从PNG图像和YAML元数据重建二值RLE文件(.sha, .msk)
        
        Args:
            resource: 资源信息字典
        
        Returns:
            (offset, length): 在data_buffer中的偏移量和长度
        """
        offset = len(self.data_buffer)
        start_size = len(self.data_buffer)
        
        if self.debug:
            print(f"\n打包{resource['res_type'].upper()}资源: {resource['name']}")
            print(f"帧数量: {len(resource['frames'])}")
        
        for frame_id, yaml_file, png_file in resource['frames']:
            if self.debug:
                print(f"\n处理帧 {frame_id}:")
            
            with open(os.path.join(resource['root'], yaml_file), 'r', encoding='utf-8') as f:
                metadata = yaml.safe_load(f)
            
            img = Image.open(os.path.join(resource['root'], png_file)).convert('L')
            width, height = img.size
            
            if self.debug:
                print(f"  尺寸: {width}x{height}")
                print(f"  原点: ({metadata['origin_x']}, {metadata['origin_y']})")
            
            # 帧大小占位，稍后更新
            frame_size_pos = len(self.data_buffer)
            self.data_buffer.extend(struct.pack('<I', 0))
            
            # 帧头信息
            self.data_buffer.extend(struct.pack('<H', width))  # width
            self.data_buffer.extend(struct.pack('<H', height))  # height
            self.data_buffer.extend(struct.pack('<H', metadata['origin_x']))  # origin_x
            self.data_buffer.extend(struct.pack('<H', metadata['origin_y']))  # origin_y
            self.data_buffer.extend(struct.pack('<H', metadata['unknown1']))  # unk1
            self.data_buffer.extend(struct.pack('<H', metadata['unknown2']))  # unk2
            self.data_buffer.extend(struct.pack('<H', metadata['unknown3']))  # unk3
            self.data_buffer.extend(struct.pack('<H', metadata['unknown4']))  # unk4
            
            # 为所有行预留偏移量空间
            offsets_start = len(self.data_buffer)
            line_offsets = []
            for _ in range(height):
                self.data_buffer.extend(struct.pack('<I', 0))
                line_offsets.append(len(self.data_buffer))
            
            # 计算第一行数据的偏移量(以"short"为单位)
            first_line_offset = (len(self.data_buffer) - frame_size_pos) // 2
            
            # 写入每行的数据
            for y in range(height):
                # 记录当前行的起始位置
                line_start_pos = len(self.data_buffer)
                
                # 计算当前行的偏移量(相对于帧起始位置，以short为单位)
                current_offset = (line_start_pos - frame_size_pos) // 2
                
                # 更新行偏移量
                self.data_buffer[offsets_start + y * 4:offsets_start + y * 4 + 4] = struct.pack('<I', current_offset)
                
                if self.debug and y < 3:  # 只显示前几行的详细信息
                    print(f"\n  行 {y} 偏移量: {current_offset} shorts")
                
                # 分析当前行的像素数据
                line = []
                x = 0
                in_skip = True  # 默认开始是跳过模式（透明）
                count = 0
                
                # 分析一行像素
                while x < width:
                    pixel_value = img.getpixel((x, y))
                    is_skip = (pixel_value < 64)  # 判断是否为跳过点
                    
                    if (in_skip and is_skip) or (not in_skip and not is_skip):
                        # 继续当前模式
                        count += 1
                    else:
                        # 模式切换
                        line.append((in_skip, count))
                        in_skip = not in_skip
                        count = 1
                    
                    x += 1
                
                # 添加最后一段
                if count > 0:
                    line.append((in_skip, count))
                
                if self.debug and y < 3:
                    print(f"    RLE段: {line}")
                
                # 写入命令数量
                self.data_buffer.extend(struct.pack('<H', len(line)))
                
                # 写入初始模式，与unpacker_v2.py中的模式保持一致:
                # is_skip_mode_first = read_short() == 0
                # 即，如果read_short()返回0，是跳过模式
                is_skip_first = 0 if line[0][0] else 1  # 如果第一个段是跳过段，写入0，否则写入1
                self.data_buffer.extend(struct.pack('<H', is_skip_first))
                
                if self.debug and y < 3:
                    print(f"    命令数: {len(line)}, 初始模式: {is_skip_first} (0=跳过,1=写入)")
                
                # 写入每个命令的长度
                for is_skip, count in line:
                    self.data_buffer.extend(struct.pack('<H', count))
            
            # 更新帧大小
            frame_size = len(self.data_buffer) - frame_size_pos
            self.data_buffer[frame_size_pos:frame_size_pos + 4] = struct.pack('<I', frame_size)
            
            if self.debug:
                print(f"  帧大小: {frame_size} 字节")
        
        # 结束标记
        self.data_buffer.extend(struct.pack('<I', 0))
        
        if self.debug:
            print(f"资源总大小: {len(self.data_buffer) - start_size} 字节")
        
        return offset, len(self.data_buffer) - start_size
    
    def create_info_data_files(self, output_data, output_info):
        """
        创建sprites.data和sprites.info文件
        
        Args:
            output_data: sprites.data输出路径
            output_info: sprites.info输出路径
        """
        # 处理所有资源
        info_entries = []
        
        for resource in self.resources:
            try:
                if resource['type'] == 'raw':
                    offset, length = self.pack_raw_file(resource)
                elif resource['type'] == 'png_yaml':
                    if resource['res_type'] == 'ps6':
                        offset, length = self.pack_ps6_from_images(resource)
                    else:
                        print(f"警告: 未知资源类型 {resource['res_type']}，跳过")
                        continue
                
                info_entries.append({
                    'name': resource['name'],
                    'offset': offset,
                    'length': length
                })
                
                print(f"打包资源: {resource['name']}, 偏移量: {offset}, 长度: {length}")
            
            except Exception as e:
                print(f"打包 {resource['name']} 时出错: {str(e)}")
                if self.debug:
                    import traceback
                    traceback.print_exc()
        
        # 创建sprites.info文件
        with open(output_info, 'wb') as f:
            # 写入签名
            f.write(struct.pack('<I', 0x01010101))
            
            # 写入条目数量
            f.write(struct.pack('<I', len(info_entries)))
            
            # 写入每个条目
            for entry in info_entries:
                # 写入文件名(每个字符加上0x0a)
                for char in entry['name']:
                    f.write(struct.pack('B', ord(char) + 0x0a))
                f.write(struct.pack('B', 0))  # null终止符
                
                # 写入偏移量和长度
                f.write(struct.pack('<I', entry['offset']))
                f.write(struct.pack('<I', entry['length']))
        
        # 创建sprites.data文件
        with open(output_data, 'wb') as f:
            f.write(self.data_buffer)
    
    def pack(self, output_data, output_info):
        """
        执行打包操作
        
        Args:
            output_data: sprites.data输出路径
            output_info: sprites.info输出路径
        """
        # 扫描目录
        self.scan_directory()
        
        # 创建data和info文件
        self.create_info_data_files(output_data, output_info)
        
        print("\n打包完成！")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='StateOfWar资源打包工具',
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('--input', default='output', help='输入目录路径 (默认: output)')
    parser.add_argument('--data', default='sprites.data.new', help='输出sprites.data文件路径 (默认: sprites.data.new)')
    parser.add_argument('--info', default='sprites.info.new', help='输出sprites.info文件路径 (默认: sprites.info.new)')
    parser.add_argument('--debug', action='store_true', help='启用调试输出')
    
    args = parser.parse_args()
    
    # 检查目录是否存在
    if not os.path.exists(args.input):
        print(f"错误: 未找到输入目录: {args.input}")
        return
    
    # 初始化打包器
    packer = SpritePacker(args.input, debug=args.debug)
    
    # 执行打包
    packer.pack(args.data, args.info)


if __name__ == '__main__':
    main() 