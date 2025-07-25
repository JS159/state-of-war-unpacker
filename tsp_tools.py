#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TSP文件解析和打包工具
基于unpacker_v2.py中的ps6解包方法，实现tsp文件的解析和打包

使用方法:
  python tsp_tools.py parse file.tsp                    # 解析单个TSP文件
  python tsp_tools.py parse-dir input_dir               # 解析目录中所有TSP文件
  python tsp_tools.py pack input_dir tsp_name           # 打包单个TSP文件
  python tsp_tools.py pack-dir input_dir                # 打包目录中所有PNG+YAML对
"""

import os
import struct
import yaml
from PIL import Image
import argparse
from collections import defaultdict


class TSPParser:
    """TSP文件解析器"""

    def __init__(self, tsp_file=None):
        """
        初始化TSP解析器

        Args:
            tsp_file: TSP文件路径（可选，用于单文件解析）
        """
        self.tsp_file = tsp_file
        
    def parse_tsp_file(self, output_dir="tsp_output"):
        """
        解析TSP文件
        
        Args:
            output_dir: 输出目录
        """
        if not os.path.exists(self.tsp_file):
            print(f"错误: TSP文件不存在: {self.tsp_file}")
            return
            
        print(f"解析TSP文件: {self.tsp_file}")

        with open(self.tsp_file, 'rb') as f:
            data = f.read()

        # 解析TSP文件
        try:
            self._parse_as_ps6_format(data, output_dir)
        except Exception as e:
            print(f"解析失败: {e}")
    
    def _parse_as_ps6_format(self, data, output_dir):
        """
        尝试使用ps6格式解析TSP文件
        
        Args:
            data: 文件数据
            output_dir: 输出目录
        """

        
        position = 0
        
        def read_byte():
            nonlocal position
            if position >= len(data):
                raise IndexError("读取超出文件末尾")
            result = data[position]
            position += 1
            return result
        
        def read_ubyte():
            return read_byte() & 0xff
        
        def read_short():
            first = read_ubyte()
            second = read_ubyte()
            value = (first | (second << 8))
            # 处理16位有符号整数的补码
            if value & 0x8000:  # 最高位为1，表示负数
                value = -((~value & 0xffff) + 1)
            return value
        
        def read_ushort():
            first = read_ubyte()
            second = read_ubyte()
            return (first | (second << 8)) & 0xffff
        
        def read_int():
            first = read_ushort()
            second = read_ushort()
            return first | (second << 16)
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        # 读取每一帧
        frame_id = 0
        while position < len(data):
            try:
                size = read_int()

                if size == 0:
                    break

                if size < 0 or size > len(data):
                    print(f"警告: 无效的帧大小: {size}")
                    break
                
                frame_info = {}
                outer_position = position
                start_position = position
                
                # 读取帧头信息
                frame_info['width'] = read_ushort()
                frame_info['height'] = read_ushort()
                frame_info['origin_x'] = read_short()
                frame_info['origin_y'] = read_short()
                frame_info['unk1'] = read_short()
                frame_info['unk2'] = read_short()
                frame_info['unk3'] = read_short()
                frame_info['unk4'] = read_short()
                
                # 检查尺寸是否合理
                if frame_info['width'] <= 0 or frame_info['height'] <= 0 or frame_info['width'] > 2048 or frame_info['height'] > 2048:
                    print(f"警告: 跳过无效尺寸的帧 {frame_id}")
                    position = outer_position + size
                    frame_id += 1
                    continue
                
                # 创建图像
                img = Image.new('RGBA', (frame_info['width'], frame_info['height']), (0, 0, 0, 0))
                pixels = img.load()
                
                # 读取每一行的像素数据
                for y in range(frame_info['height']):
                    if position >= len(data):
                        break
                        
                    line_offset = read_int()
                    for_position = position
                    position = start_position + line_offset * 2
                    
                    if position >= len(data):
                        break
                    
                    x = 0
                    num_command = read_ushort()
                    skip_mode = read_ushort() == 0
                    
                    for i in range(num_command):
                        if position >= len(data) or x >= frame_info['width']:
                            break
                            
                        if skip_mode:
                            # 跳过透明像素
                            skip_count = read_ushort()
                            x += skip_count
                        else:
                            # 读取有颜色的像素
                            read_pixels = read_ushort()
                            
                            for j in range(read_pixels):
                                if position >= len(data) or x >= frame_info['width']:
                                    break
                                    
                                color16 = read_ushort()
                                # 将RGB565转换为RGBA
                                r = ((color16 >> 11) & 0x1f) << 3
                                g = ((color16 >> 5) & 0x3f) << 2
                                b = (color16 & 0x1f) << 3
                                a = 255  # 完全不透明
                                
                                if y < frame_info['height'] and x < frame_info['width']:
                                    pixels[x, y] = (r, g, b, a)
                                x += 1
                        
                        skip_mode = not skip_mode
                    
                    position = for_position
                
                # 保存PNG图像 - 使用TSP文件名_帧数格式
                tsp_basename = os.path.splitext(os.path.basename(self.tsp_file))[0]
                output_filename = f"{tsp_basename}_{frame_id}.png"
                png_path = os.path.join(output_dir, output_filename)
                img.save(png_path)

                # 保存YAML元数据 - 使用TSP文件名_帧数格式
                yaml_filename = f"{tsp_basename}_{frame_id}.yaml"
                yaml_path = os.path.join(output_dir, yaml_filename)
                with open(yaml_path, 'w', encoding='utf-8') as yaml_file:
                    yaml.dump({
                        'frame': frame_id,
                        'width': frame_info['width'],
                        'height': frame_info['height'],
                        'origin_x': frame_info['origin_x'],
                        'origin_y': frame_info['origin_y'],
                        'unknown1': frame_info['unk1'],
                        'unknown2': frame_info['unk2'],
                        'unknown3': frame_info['unk3'],
                        'unknown4': frame_info['unk4']
                    }, yaml_file, default_flow_style=False)
                
                position = outer_position + size
                frame_id += 1
                
            except Exception as e:
                print(f"解析帧 {frame_id} 时出错: {e}")
                break
        
        print(f"解析完成，共 {frame_id} 帧")

    def parse_directory(self, input_dir, output_dir="tsp_output"):
        """
        遍历目录解析所有TSP文件，保留目录结构

        Args:
            input_dir: 输入目录
            output_dir: 输出目录
        """
        if not os.path.exists(input_dir):
            print(f"错误: 输入目录不存在: {input_dir}")
            return

        print(f"遍历目录解析TSP文件: {input_dir}")

        tsp_files = []
        # 遍历目录查找所有TSP文件
        for root, dirs, files in os.walk(input_dir):
            for file in files:
                if file.lower().endswith('.tsp'):
                    tsp_path = os.path.join(root, file)
                    rel_path = os.path.relpath(root, input_dir)
                    tsp_files.append((tsp_path, rel_path, file))

        if not tsp_files:
            print("未找到任何TSP文件")
            return

        print(f"找到 {len(tsp_files)} 个TSP文件")

        for tsp_path, rel_path, filename in tsp_files:
            print(f"处理: {os.path.relpath(tsp_path, input_dir)}")

            # 创建对应的输出目录
            if rel_path == '.':
                file_output_dir = output_dir
            else:
                file_output_dir = os.path.join(output_dir, rel_path)

            # 临时设置当前文件路径
            original_tsp_file = self.tsp_file
            self.tsp_file = tsp_path

            try:
                self.parse_tsp_file(file_output_dir)
            except Exception as e:
                print(f"解析文件 {tsp_path} 时出错: {e}")
            finally:
                # 恢复原始文件路径
                self.tsp_file = original_tsp_file

        print(f"\n目录解析完成！输出目录: {output_dir}")
    



class TSPPacker:
    """TSP文件打包器"""

    def __init__(self, debug=False):
        """
        初始化TSP打包器

        Args:
            debug: 是否启用调试输出
        """
        self.debug = debug

    def pack_tsp_from_images(self, png_yaml_pairs, output_path):
        """
        从PNG图像和YAML元数据重建TSP文件

        Args:
            png_yaml_pairs: [(frame_id, png_path, yaml_path), ...] 帧数据列表
            output_path: 输出TSP文件路径
        """
        print(f"打包TSP文件: {output_path}")

        # 按帧ID排序
        png_yaml_pairs.sort(key=lambda x: x[0])

        frames_data = bytearray()

        for frame_id, png_path, yaml_path in png_yaml_pairs:
            if self.debug:
                print(f"  处理帧 {frame_id}: {png_path}")

            # 读取YAML元数据
            with open(yaml_path, 'r', encoding='utf-8') as f:
                metadata = yaml.safe_load(f)

            # 读取PNG图像
            image = Image.open(png_path).convert('RGBA')

            # 准备帧数据
            frame_buffer = bytearray()

            # 写入帧头信息
            width = metadata['width']
            height = metadata['height']
            origin_x = metadata['origin_x']
            origin_y = metadata['origin_y']
            unk1 = metadata['unknown1']
            unk2 = metadata['unknown2']
            unk3 = metadata['unknown3']
            unk4 = metadata['unknown4']

            # 写入宽度和高度 (无符号16位整数)
            frame_buffer.extend(struct.pack('<H', width))
            frame_buffer.extend(struct.pack('<H', height))

            # 写入锚点和未知数据 (有符号16位整数)
            frame_buffer.extend(struct.pack('<h', origin_x))
            frame_buffer.extend(struct.pack('<h', origin_y))
            frame_buffer.extend(struct.pack('<h', unk1))
            frame_buffer.extend(struct.pack('<h', unk2))
            frame_buffer.extend(struct.pack('<h', unk3))
            frame_buffer.extend(struct.pack('<h', unk4))

            # 为行偏移表保留空间 (每行4字节)
            line_offset_positions = []
            for _ in range(height):
                line_offset_positions.append(len(frame_buffer))
                frame_buffer.extend(b'\x00\x00\x00\x00')  # 占位符

            # 准备获取像素数据
            pixels = image.load()
            line_data_positions = []

            # 处理每一行的像素数据
            for y in range(height):
                line_start_pos = len(frame_buffer)
                line_data_positions.append(line_start_pos // 2)  # 以2字节为单位的偏移

                # 压缩当前行的像素
                commands = []

                # 初始模式检查（检查第一个像素是否透明）
                is_skip_mode = pixels[0, y][3] == 0

                # 处理一行中的所有像素
                x = 0
                while x < width:
                    if is_skip_mode:
                        # 计算连续的透明像素数量
                        skip_start = x
                        while x < width and pixels[x, y][3] == 0:
                            x += 1
                        skip_count = x - skip_start

                        if skip_count > 0:
                            commands.append(('skip', skip_count))
                    else:
                        # 计算连续的不透明像素数量
                        pixels_to_draw = []
                        while x < width and pixels[x, y][3] > 0:
                            # 将RGBA转换为RGB565
                            r, g, b, a = pixels[x, y]
                            r = (r >> 3) & 0x1F
                            g = (g >> 2) & 0x3F
                            b = (b >> 3) & 0x1F
                            rgb565 = (r << 11) | (g << 5) | b

                            pixels_to_draw.append(rgb565)
                            x += 1
                        draw_count = len(pixels_to_draw)

                        if draw_count > 0:
                            commands.append(('draw', draw_count, pixels_to_draw))

                    # 切换模式
                    is_skip_mode = not is_skip_mode

                # 写入命令数
                frame_buffer.extend(struct.pack('<H', len(commands)))

                # 确定第一条命令的模式
                first_cmd_type = commands[0][0] if commands else 'skip'
                is_first_skip = first_cmd_type == 'skip'
                frame_buffer.extend(struct.pack('<H', 0 if is_first_skip else 1))

                # 写入命令数据
                for cmd_type, count, *args in commands:
                    frame_buffer.extend(struct.pack('<H', count))
                    if cmd_type == 'draw':
                        for rgb565 in args[0]:
                            frame_buffer.extend(struct.pack('<H', rgb565))

            # 回填行偏移表
            for i, pos in enumerate(line_offset_positions):
                line_offset = line_data_positions[i]
                frame_buffer[pos:pos+4] = struct.pack('<I', line_offset)

            # 计算帧的总大小并写入帧数据块的开头
            frame_size = len(frame_buffer)
            frame_data_with_size = bytearray(struct.pack('<I', frame_size))
            frame_data_with_size.extend(frame_buffer)

            frames_data.extend(frame_data_with_size)

        # 添加结束标记
        frames_data.extend(struct.pack('<I', 0))

        # 创建输出目录
        output_dir = os.path.dirname(output_path)
        if output_dir:  # 只有当目录不为空时才创建
            os.makedirs(output_dir, exist_ok=True)

        # 写入TSP文件
        with open(output_path, 'wb') as f:
            f.write(frames_data)

        print(f"打包完成: {output_path}")

    def pack_directory(self, input_dir, output_dir):
        """
        遍历目录打包所有PNG+YAML对为TSP文件，保留目录结构

        Args:
            input_dir: 输入目录（包含PNG和YAML文件）
            output_dir: 输出目录
        """
        if not os.path.exists(input_dir):
            print(f"错误: 输入目录不存在: {input_dir}")
            return

        print(f"遍历目录打包TSP文件: {input_dir}")

        # 收集所有PNG+YAML对，按TSP文件名分组
        tsp_groups = defaultdict(list)

        for root, _, files in os.walk(input_dir):
            for file in files:
                if file.endswith('.yaml'):
                    base_name = os.path.splitext(file)[0]
                    png_file = base_name + '.png'
                    png_path = os.path.join(root, png_file)
                    yaml_path = os.path.join(root, file)

                    if os.path.exists(png_path):
                        # 解析文件名格式: tsp名_帧数
                        parts = base_name.split('_')
                        if len(parts) >= 2 and parts[-1].isdigit():
                            tsp_name = '_'.join(parts[:-1])
                            frame_id = int(parts[-1])

                            rel_path = os.path.relpath(root, input_dir)
                            if rel_path == '.':
                                tsp_key = tsp_name
                                output_tsp_path = os.path.join(output_dir, f"{tsp_name}.tsp")
                            else:
                                tsp_key = os.path.join(rel_path, tsp_name)
                                output_tsp_path = os.path.join(output_dir, rel_path, f"{tsp_name}.tsp")

                            tsp_groups[tsp_key].append((frame_id, png_path, yaml_path, output_tsp_path))

        if not tsp_groups:
            print("未找到任何PNG+YAML对")
            return

        print(f"找到 {len(tsp_groups)} 个TSP文件需要打包")

        for tsp_key, frames in tsp_groups.items():
            print(f"打包: {tsp_key}")

            # 获取输出路径（所有帧的输出路径应该相同）
            output_path = frames[0][3]

            # 准备帧数据
            png_yaml_pairs = [(frame_id, png_path, yaml_path) for frame_id, png_path, yaml_path, _ in frames]

            try:
                self.pack_tsp_from_images(png_yaml_pairs, output_path)
            except Exception as e:
                print(f"打包TSP文件 {tsp_key} 时出错: {e}")
                if self.debug:
                    import traceback
                    traceback.print_exc()

        print(f"目录打包完成！输出目录: {output_dir}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='TSP文件解析和打包工具',
        formatter_class=argparse.RawTextHelpFormatter
    )

    subparsers = parser.add_subparsers(dest='command', help='可用命令')

    # 解析单个TSP文件
    parse_parser = subparsers.add_parser('parse', help='解析单个TSP文件')
    parse_parser.add_argument('tsp_file', help='TSP文件路径')
    parse_parser.add_argument('--output', default='tsp_output', help='输出目录 (默认: tsp_output)')

    # 解析目录中的所有TSP文件
    parse_dir_parser = subparsers.add_parser('parse-dir', help='解析目录中的所有TSP文件')
    parse_dir_parser.add_argument('input_dir', help='输入目录路径')
    parse_dir_parser.add_argument('--output', default='tsp_output', help='输出目录 (默认: tsp_output)')

    # 打包单个TSP文件
    pack_parser = subparsers.add_parser('pack', help='从PNG+YAML文件打包单个TSP文件')
    pack_parser.add_argument('input_dir', help='包含PNG和YAML文件的目录')
    pack_parser.add_argument('tsp_name', help='TSP文件名（不含扩展名）')
    pack_parser.add_argument('--output', help='输出TSP文件路径')
    pack_parser.add_argument('--debug', action='store_true', help='启用调试输出')

    # 打包目录中的所有TSP文件
    pack_dir_parser = subparsers.add_parser('pack-dir', help='打包目录中的所有PNG+YAML对为TSP文件')
    pack_dir_parser.add_argument('input_dir', help='输入目录路径（包含PNG和YAML文件）')
    pack_dir_parser.add_argument('--output', default='tsp_packed', help='输出目录 (默认: tsp_packed)')
    pack_dir_parser.add_argument('--debug', action='store_true', help='启用调试输出')

    args = parser.parse_args()

    if args.command == 'parse':
        # 解析单个TSP文件
        parser_obj = TSPParser(args.tsp_file)
        parser_obj.parse_tsp_file(args.output)

    elif args.command == 'parse-dir':
        # 解析目录中的所有TSP文件
        parser_obj = TSPParser()
        parser_obj.parse_directory(args.input_dir, args.output)

    elif args.command == 'pack':
        # 打包单个TSP文件
        packer = TSPPacker(debug=args.debug)

        # 收集指定TSP名称的PNG+YAML对
        png_yaml_pairs = []
        for root, _, files in os.walk(args.input_dir):
            for file in files:
                if file.endswith('.yaml'):
                    base_name = os.path.splitext(file)[0]
                    png_file = base_name + '.png'
                    png_path = os.path.join(root, png_file)
                    yaml_path = os.path.join(root, file)

                    if os.path.exists(png_path):
                        # 检查是否匹配指定的TSP名称
                        parts = base_name.split('_')
                        if len(parts) >= 2 and parts[-1].isdigit():
                            tsp_name = '_'.join(parts[:-1])
                            if tsp_name == args.tsp_name:
                                frame_id = int(parts[-1])
                                png_yaml_pairs.append((frame_id, png_path, yaml_path))

        if not png_yaml_pairs:
            print(f"未找到TSP文件 '{args.tsp_name}' 的PNG+YAML对")
            return

        output_path = args.output if args.output else f"{args.tsp_name}.tsp"
        packer.pack_tsp_from_images(png_yaml_pairs, output_path)

    elif args.command == 'pack-dir':
        # 打包目录中的所有TSP文件
        packer = TSPPacker(debug=args.debug)
        packer.pack_directory(args.input_dir, args.output)

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
