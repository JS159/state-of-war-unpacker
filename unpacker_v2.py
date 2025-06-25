#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
StateOfWar资源解包工具
用于将sprites.data和sprites.info文件解包为原始文件，
并可选择性地将.ps6文件解包为PNG图片和对应的YAML元数据文件。
"""

import os
import struct
import yaml
from PIL import Image
import argparse


class SpriteUnpacker:
    """资源解包器"""
    
    def __init__(self, data_file, info_file):
        """
        初始化解包器
        
        Args:
            data_file: sprites.data文件路径
            info_file: sprites.info文件路径
        """
        self.data_file = data_file
        self.info_file = info_file
        self.sprites = []
        
    def read_info_file(self):
        """读取sprites.info文件，获取所有资源的信息"""
        with open(self.info_file, 'rb') as f:
            # 读取文件头
            signature = struct.unpack('<I', f.read(4))[0]
            if signature != 0x01010101:
                raise ValueError(f"无效的sprites.info文件，签名不匹配: {hex(signature)}")
            
            # 读取条目数量
            entries_count = struct.unpack('<I', f.read(4))[0]
            print(f"找到 {entries_count} 个资源条目")
            
            # 读取每个资源的信息
            for i in range(entries_count):
                # 读取文件名
                name_bytes = bytearray()
                while True:
                    byte = f.read(1)
                    if byte == b'\x00':
                        break
                    name_bytes.append(byte[0] - 0x0a)  # 减去0xa获取实际字符
                
                name = name_bytes.decode('utf-8')
                
                # 读取偏移量和长度
                offset = struct.unpack('<I', f.read(4))[0]
                length = struct.unpack('<I', f.read(4))[0]
                
                # 分离文件夹和文件名
                folder = os.path.dirname(name)
                basename = os.path.basename(name)
                file_ext = os.path.splitext(basename)[1]
                
                self.sprites.append({
                    'name': name,
                    'folder': folder,
                    'basename': os.path.splitext(basename)[0],
                    'ext': file_ext,
                    'offset': offset,
                    'length': length,
                    'frames': []
                })
                print(f"读取资源: {name}, 偏移量: {offset}, 长度: {length}")
    
    def unpack_raw_file(self, sprite_data, output_dir):
        """
        解包单个原始文件
        
        Args:
            sprite_data: 文件数据字典
            output_dir: 输出目录
        """
        with open(self.data_file, 'rb') as f:
            # 定位到文件数据
            f.seek(sprite_data['offset'])
            
            # 读取文件数据
            data = f.read(sprite_data['length'])
            
            # 创建输出目录
            output_folder = os.path.join(output_dir, sprite_data['folder'])
            os.makedirs(output_folder, exist_ok=True)
            
            # 保存原始文件
            output_path = os.path.join(output_folder, sprite_data['basename'] + sprite_data['ext'])
            with open(output_path, 'wb') as out_f:
                out_f.write(data)

    def unpack_sprite(self, sprite_data, output_dir):
        """
        解包单个精灵图
        
        Args:
            sprite_data: 精灵图数据字典
            output_dir: 输出目录
        """
        with open(self.data_file, 'rb') as f:
            # 定位到精灵图数据
            f.seek(sprite_data['offset'])
            
            # 读取精灵图数据
            data = f.read(sprite_data['length'])
            
            # 创建MasterReader类似的功能
            position = 0
            
            def read_byte():
                nonlocal position
                result = data[position]
                position += 1
                return result
            
            def read_ubyte():
                return read_byte() & 0xff
            
            def read_short():
                first = read_ubyte()
                second = read_ubyte()
                return (first | (second << 8))
            
            def read_ushort():
                return read_short() & 0xffff
            
            def read_int():
                first = read_ushort()
                second = read_ushort()
                return first | (second << 16)
            
            # 读取每一帧
            frame_id = 0
            while position < len(data):
                size = read_int()
                
                if size == 0:
                    break
                
                frame_info = {}
                outer_position = position
                start_position = position
                
                # 读取帧头信息
                frame_info['width'] = read_short()
                frame_info['height'] = read_short()
                
                frame_info['origin_x'] = read_short()
                frame_info['origin_y'] = read_short()
                
                frame_info['unk1'] = read_short()
                frame_info['unk2'] = read_short()
                frame_info['unk3'] = read_short()
                frame_info['unk4'] = read_short()
                
                # 创建图像
                if frame_info['width'] > 0 and frame_info['height'] > 0:
                    # 创建空白RGBA图像
                    img = Image.new('RGBA', (frame_info['width'], frame_info['height']), (0, 0, 0, 0))
                    pixels = img.load()
                    
                    # 读取每一行的像素数据
                    for y in range(frame_info['height']):
                        line_offset = read_int()
                        for_position = position
                        position = start_position + line_offset * 2
                        
                        x = 0
                        num_command = read_short()
                        skip_mode = read_short() == 0
                        
                        for i in range(num_command):
                            if skip_mode:
                                # 跳过透明像素
                                x += read_short()
                            else:
                                # 读取有颜色的像素
                                read_pixels = read_short()
                                
                                for j in range(read_pixels):
                                    color16 = read_short()
                                    # 将RGB565转换为RGBA
                                    r = ((color16 >> 11) & 0x1f) << 3
                                    g = ((color16 >> 5) & 0x3f) << 2
                                    b = (color16 & 0x1f) << 3
                                    a = 255  # 完全不透明
                                    
                                    pixels[x, y] = (r, g, b, a)
                                    x += 1
                            
                            skip_mode = not skip_mode
                        
                        position = for_position
                    
                    # 创建输出目录
                    sprite_folder = os.path.join(output_dir, sprite_data['folder'])
                    os.makedirs(sprite_folder, exist_ok=True)
                    
                    # 保存PNG图像
                    output_filename = f"{sprite_data['basename']}_{frame_id}"
                    png_path = os.path.join(sprite_folder, f"{output_filename}.png")
                    img.save(png_path)
                    
                    # 保存YAML元数据
                    yaml_path = os.path.join(sprite_folder, f"{output_filename}.yaml")
                    with open(yaml_path, 'w', encoding='utf-8') as yaml_file:
                        yaml.dump({
                            'name': sprite_data['basename'],
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
    
    def unpack_binary_rle(self, sprite_data, output_dir):
        """
        解包使用二值RLE编码的文件（.sha, .msk）
        
        Args:
            sprite_data: 文件数据字典
            output_dir: 输出目录
        """
        with open(self.data_file, 'rb') as f:
            f.seek(sprite_data['offset'])
            data = f.read(sprite_data['length'])

        position = 0

        def read_byte():
            nonlocal position
            if position >= len(data): raise IndexError("Attempt to read past end of data")
            result = data[position]
            position += 1
            return result

        def read_ubyte():
            return read_byte() & 0xff

        def read_short():
            first = read_ubyte()
            second = read_ubyte()
            return first | (second << 8)

        def read_int():
            first = read_short()
            second = read_short()
            return (first | (second << 16)) & 0xffffffff

        frame_id = 0
        while position < len(data):
            try:
                size = read_int()
            except IndexError:
                break 

            if size == 0:
                break

            frame_info = {}
            frame_start_pos = position
            
            frame_info['width'] = read_short()
            frame_info['height'] = read_short()
            
            frame_info['origin_x'] = read_short()
            frame_info['origin_y'] = read_short()
            
            frame_info['unk1'] = read_short()
            frame_info['unk2'] = read_short()
            frame_info['unk3'] = read_short()
            frame_info['unk4'] = read_short()
            
            if frame_info['width'] > 0 and frame_info['height'] > 0:
                img = Image.new('L', (frame_info['width'], frame_info['height']), 0)
                pixels = img.load()
                
                line_offsets = [read_int() for _ in range(frame_info['height'])]
                main_pos_after_offsets = position

                for y in range(frame_info['height']):
                    line_data_pos = frame_start_pos + line_offsets[y] * 2
                    position = line_data_pos
                    
                    x = 0
                    try:
                        num_commands = read_short()
                        is_skip_mode_first = read_short()
                        is_skip_mode = is_skip_mode_first == 0

                        for _ in range(num_commands):
                            if x >= frame_info['width']: break
                            count = read_short()
                            
                            if is_skip_mode:
                                x += count
                            else:
                                gray_value = 128
                                for _ in range(count):
                                    if x >= frame_info['width']: break
                                    pixels[x, y] = gray_value
                                    x += 1
                            
                            is_skip_mode = not is_skip_mode
                    except IndexError:
                        continue
                
                position = main_pos_after_offsets

                # 创建输出子目录
                sub_folder_name = "shadows" if sprite_data['ext'] == '.sha' else "masks"
                output_folder = os.path.join(output_dir, os.path.dirname(sprite_data['name']), sub_folder_name)
                os.makedirs(output_folder, exist_ok=True)
                
                # 保存PNG图像
                output_filename = f"{sprite_data['basename']}_{frame_id}.png"
                png_path = os.path.join(output_folder, output_filename)
                img.save(png_path)

                # 保存YAML元数据
                yaml_path = os.path.join(output_folder, f"{sprite_data['basename']}_{frame_id}.yaml")
                with open(yaml_path, 'w', encoding='utf-8') as yaml_file:
                    yaml.dump({
                        'name': sprite_data['basename'],
                        'frame': frame_id,
                        'type': 'shadow' if sprite_data['ext'] == '.sha' else 'mask',
                        'width': frame_info['width'],
                        'height': frame_info['height'],
                        'origin_x': frame_info['origin_x'],
                        'origin_y': frame_info['origin_y'],
                        'unknown1': frame_info['unk1'],
                        'unknown2': frame_info['unk2'],
                        'unknown3': frame_info['unk3'],
                        'unknown4': frame_info['unk4']
                    }, yaml_file, default_flow_style=False)

            position = frame_start_pos + size
            frame_id += 1

    def unpack_all(self, output_dir, mode):
        """
        解包所有文件
        
        Args:
            output_dir: 输出目录
            mode: 解包模式
        """
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        
        # 读取sprites.info文件
        self.read_info_file()
        
        print("\n开始解包...")
        # 解包每个文件
        for sprite_data in self.sprites:
            try:
                self.unpack_raw_file(sprite_data, output_dir)
                output_path = os.path.join(output_dir, sprite_data['folder'], sprite_data['basename'] + sprite_data['ext'])
                print(f"成功提取原始文件: {output_path}")

                # 模式 'png' 或 'both' -> 解包为图片
                if mode in ['png', 'both']:
                    if sprite_data['ext'] == '.ps6':
                        self.unpack_sprite(sprite_data, output_dir)
                        folder_path = os.path.join(output_dir, sprite_data['folder'])
                        print(f"-> 成功解包为PNG图片: {os.path.join(folder_path, sprite_data['basename'])}")
                    elif sprite_data['ext'] in ['.sha', '.msk']:
                        self.unpack_binary_rle(sprite_data, output_dir)
                        folder_path = os.path.join(output_dir, sprite_data['folder'])
                        file_type = "Shadow" if sprite_data['ext'] == '.sha' else "Mask"
                        print(f"-> 成功解包为 {file_type} 图片: {os.path.join(folder_path, sprite_data['basename'])}")

            except Exception as e:
                print(f"解包 {sprite_data['name']} 时出错: {str(e)}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='StateOfWar资源解包工具',
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('--data', default='sprites.data', help='sprites.data文件路径 (默认: sprites.data)')
    parser.add_argument('--info', default='sprites.info', help='sprites.info文件路径 (默认: sprites.info)')
    parser.add_argument('--output', default='output', help='输出目录路径 (默认: output)')
    parser.add_argument(
        '--mode',
        default='both',
        choices=['raw', 'png', 'both'],
        help="""解包模式 (默认: both):
- raw: 仅提取原始文件 (.ps6, .sha, .msk等)。
- png: 仅将 .ps6/.sha/.msk 解包为PNG图片和元数据。
- both: 提取原始文件，并进行PNG解包。"""
    )
    
    args = parser.parse_args()
    
    # 检查文件是否存在
    if not os.path.exists(args.data):
        print(f"错误: 未找到 data 文件: {args.data}")
        return
    if not os.path.exists(args.info):
        print(f"错误: 未找到 info 文件: {args.info}")
        return

    # 初始化解包器
    unpacker = SpriteUnpacker(args.data, args.info)
    
    # 解包所有文件
    unpacker.unpack_all(args.output, args.mode)
    
    print("\n解包完成！")


if __name__ == '__main__':
    main() 