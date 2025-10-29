import os
import shutil
import hashlib
import csv
import json
from collections import defaultdict
from datetime import datetime

# 配置临时文件夹名称
TEMP_DUPLICATES_FOLDER = "duplicates_temp"
# 移动记录文件名称
MOVE_RECORD_FILE = "duplicate_movements.kcptun_config.json"

def get_file_size(file_path):
    """获取文件大小"""
    try:
        return os.path.getsize(file_path)
    except (OSError, PermissionError):
        return None

def calculate_file_hash(file_path, block_size=65536):
    """计算文件的MD5哈希值"""
    try:
        hasher = hashlib.md5()
        with open(file_path, 'rb') as f:
            buf = f.read(block_size)
            while buf:
                hasher.update(buf)
                buf = f.read(block_size)
        return hasher.hexdigest()
    except (OSError, PermissionError) as e:
        print(f"警告: 无法读取文件 {file_path} - {e}")
        return None

def find_duplicate_files(root_dir):
    """查找指定目录下的重复文件"""
    # 首先按文件大小分组（快速筛选）
    size_groups = defaultdict(list)

    print(f"正在扫描 {root_dir} 中的文件...")
    file_count = 0

    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            file_path = os.path.join(dirpath, filename)
            file_size = get_file_size(file_path)

            if file_size is not None and file_size > 0:  # 忽略空文件
                size_groups[file_size].append(file_path)
                file_count += 1

    print(f"扫描完成，共发现 {file_count} 个非空文件")

    # 对大小相同的文件计算哈希值，进一步确认重复文件
    duplicate_groups = []
    total_to_hash = sum(len(files) for files in size_groups.values() if len(files) > 1)

    if total_to_hash > 0:
        print(f"需要验证 {total_to_hash} 个可能重复的文件...")

        for size, files in size_groups.items():
            if len(files) > 1:
                hash_groups = defaultdict(list)

                for file_path in files:
                    file_hash = calculate_file_hash(file_path)
                    if file_hash:
                        hash_groups[file_hash].append(file_path)

                # 收集真正的重复文件组
                for hash_val, hash_files in hash_groups.items():
                    if len(hash_files) > 1:
                        duplicate_groups.append({
                            'size': size,
                            'hash': hash_val,
                            'files': hash_files
                        })

        print(f"验证完成，共发现 {len(duplicate_groups)} 组重复文件")

    return duplicate_groups

def save_to_csv(duplicate_groups, output_file):
    """将结果保存为CSV文件"""
    try:
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["组号", "文件大小(字节)", "MD5哈希", "文件路径"])

            group_id = 1
            for group in duplicate_groups:
                for file_path in group['files']:
                    writer.writerow([group_id, group['size'], group['hash'], file_path])
                group_id += 1

        print(f"结果已保存到 {os.path.abspath(output_file)}")
        return True
    except IOError as e:
        print(f"无法写入文件 {output_file}: {e}")
        return False

def create_temp_folder(base_dir):
    """创建临时存放重复文件的文件夹"""
    temp_folder = os.path.join(base_dir, TEMP_DUPLICATES_FOLDER)
    os.makedirs(temp_folder, exist_ok=True)
    return temp_folder

def move_duplicates(duplicate_groups, root_dir):
    """复制第一个文件用于对比，移动其他重复文件到临时文件夹并记录原始位置"""
    if not duplicate_groups:
        print("没有重复文件可处理")
        return False

    temp_folder = create_temp_folder(root_dir)
    movement_record = {
        "timestamp": datetime.now().isoformat(),
        "groups": [],
        "temp_folder": temp_folder
    }

    print(f"将把重复文件处理到临时文件夹: {temp_folder}")
    print("(每组第一个文件会被复制用于对比，其他文件会被移动)")

    for group_idx, group in enumerate(duplicate_groups, 1):
        group_record = {
            "group_id": group_idx,
            "hash": group['hash'],
            "files": []
        }

        # 第一个文件：复制到临时文件夹（用于对比），原始文件保留
        reference_file = group['files'][0]
        # 其余文件：移动到临时文件夹
        move_files = group['files'][1:]

        print(f"\n组 {group_idx}: 参考文件（将复制）: {reference_file}")
        print(f"组 {group_idx}: 将移动 {len(move_files)} 个重复文件...")

        # 创建组特定的子文件夹
        group_subfolder = os.path.join(temp_folder, f"group_{group_idx}")
        os.makedirs(group_subfolder, exist_ok=True)

        # 处理参考文件（复制）
        try:
            ref_filename = os.path.basename(reference_file)
            # 给参考文件添加标识，方便识别
            ref_filename = f"REFERENCE_{ref_filename}"
            ref_dest_path = os.path.join(group_subfolder, ref_filename)

            # 处理同名情况
            counter = 1
            while os.path.exists(ref_dest_path):
                name, ext = os.path.splitext(ref_filename)
                ref_dest_path = os.path.join(group_subfolder, f"{name}_{counter}{ext}")
                counter += 1

            # 复制文件
            shutil.copy2(reference_file, ref_dest_path)  # 使用copy2保留元数据
            print(f"已复制参考文件: {reference_file} -> {ref_dest_path}")

            # 记录参考文件信息（标记为复制）
            group_record["reference_file"] = {
                "original_path": reference_file,
                "temp_path": ref_dest_path,
                "type": "copy"
            }

        except Exception as e:
            print(f"复制参考文件 {reference_file} 时出错: {e}")
            continue  # 如果参考文件复制失败，跳过整个组的处理

        # 处理其他文件（移动）
        for file_path in move_files:
            try:
                filename = os.path.basename(file_path)
                dest_path = os.path.join(group_subfolder, filename)
                counter = 1

                while os.path.exists(dest_path):
                    name, ext = os.path.splitext(filename)
                    dest_path = os.path.join(group_subfolder, f"{name}_{counter}{ext}")
                    counter += 1

                # 移动文件
                shutil.move(file_path, dest_path)

                # 记录移动信息
                group_record["files"].append({
                    "original_path": file_path,
                    "temp_path": dest_path,
                    "type": "move"
                })

                print(f"已移动: {file_path} -> {dest_path}")

            except Exception as e:
                print(f"移动文件 {file_path} 时出错: {e}")

        movement_record["groups"].append(group_record)

    # 保存移动记录
    with open(MOVE_RECORD_FILE, 'w', encoding='utf-8') as f:
        json.dump(movement_record, f, ensure_ascii=False, indent=2)

    print(f"\n已完成所有文件处理，记录已保存到 {MOVE_RECORD_FILE}")
    print(f"请在临时文件夹中处理文件: {temp_folder}")
    print("处理完成后，运行此程序并选择恢复选项将剩余文件放回原位")
    return True

def restore_files():
    """根据记录恢复文件到原始位置"""
    if not os.path.exists(MOVE_RECORD_FILE):
        print(f"未找到移动记录文件 {MOVE_RECORD_FILE}")
        return False

    # 读取移动记录
    with open(MOVE_RECORD_FILE, 'r', encoding='utf-8') as f:
        movement_record = json.load(f)

    print(f"找到 {len(movement_record['groups'])} 组文件的记录，开始恢复...")

    for group in movement_record['groups']:
        print(f"\n处理组 {group['group_id']} 的文件...")

        # 先删除临时文件夹中的参考文件副本（它本来就是复制的）
        if "reference_file" in group:
            ref_file = group["reference_file"]
            if os.path.exists(ref_file["temp_path"]):
                try:
                    os.remove(ref_file["temp_path"])
                    print(f"已删除参考文件副本: {ref_file['temp_path']}")
                except Exception as e:
                    print(f"删除参考文件副本时出错: {e}")

        # 恢复移动的文件
        for file_info in group['files']:
            # 检查临时文件是否还存在
            if os.path.exists(file_info['temp_path']):
                try:
                    # 确保原始目录仍然存在
                    original_dir = os.path.dirname(file_info['original_path'])
                    os.makedirs(original_dir, exist_ok=True)

                    # 如果原始位置已有文件，不覆盖
                    if os.path.exists(file_info['original_path']):
                        print(f"跳过恢复 {file_info['temp_path']}，原始位置已有文件")
                        continue

                    # 移动文件回原始位置
                    shutil.move(file_info['temp_path'], file_info['original_path'])
                    print(f"已恢复: {file_info['temp_path']} -> {file_info['original_path']}")

                except Exception as e:
                    print(f"恢复文件 {file_info['temp_path']} 时出错: {e}")

    # 清理空的临时文件夹
    try:
        shutil.rmtree(movement_record['temp_folder'], ignore_errors=True)
        print(f"\n已清理临时文件夹: {movement_record['temp_folder']}")
    except Exception as e:
        print(f"清理临时文件夹时出错: {e}")

    # 删除移动记录文件
    try:
        os.remove(MOVE_RECORD_FILE)
        print(f"已删除移动记录文件: {MOVE_RECORD_FILE}")
    except Exception as e:
        print(f"删除移动记录文件时出错: {e}")

    print("\n恢复操作完成")
    return True

def interactive_mode():
    """交互式输入模式"""
    print("===== 重复文件管理工具 =====")

    # 检查是否有可恢复的记录
    if os.path.exists(MOVE_RECORD_FILE):
        choice = input("检测到有未完成的文件处理记录，是否要恢复文件? (y/n): ").strip().lower()
        if choice in ['y', 'yes']:
            restore_files()
            return

    # 主功能选择
    print("\n请选择操作:")
    print("1. 查找重复文件并保存到CSV")
    print("2. 处理重复文件（复制参考文件，移动其他文件）")
    print("3. 恢复已移动的文件（如果有记录）")

    choice = input("请输入选项 (1/2/3): ").strip()

    if choice == '1':
        # 查找重复文件并保存到CSV
        while True:
            target_dir = input("请输入要检查的文件夹路径: ").strip()
            if os.path.isdir(target_dir):
                break
            print(f"错误: '{target_dir}' 不是一个有效的文件夹，请重新输入")

        # 获取CSV文件名
        while True:
            output_file = input("请输入保存结果的CSV文件名 (例如: duplicates.csv): ").strip()
            if output_file:
                if not output_file.lower().endswith('.csv'):
                    output_file += '.csv'
                break
            print("文件名不能为空，请重新输入")

        # 执行检查
        duplicates = find_duplicate_files(target_dir)

        # 保存到CSV
        if save_to_csv(duplicates, output_file) and duplicates:
            if input("\n是否要处理这些重复文件（复制参考文件，移动其他文件）? (y/n): ").strip().lower() in ['y', 'yes']:
                move_duplicates(duplicates, target_dir)

    elif choice == '2':
        # 处理重复文件
        while True:
            target_dir = input("请输入要处理的文件夹路径: ").strip()
            if os.path.isdir(target_dir):
                break
            print(f"错误: '{target_dir}' 不是一个有效的文件夹，请重新输入")

        # 获取CSV文件名
        while True:
            output_file = input("请输入保存结果的CSV文件名 (例如: duplicates.csv): ").strip()
            if output_file:
                if not output_file.lower().endswith('.csv'):
                    output_file += '.csv'
                break
            print("文件名不能为空，请重新输入")

        duplicates = find_duplicate_files(target_dir)
        save_to_csv(duplicates, output_file)

        if duplicates:
            move_duplicates(duplicates, target_dir)
        else:
            print("未发现重复文件，无需处理")

    elif choice == '3':
        # 恢复文件
        restore_files()

    else:
        print("无效的选项")

if __name__ == "__main__":
    interactive_mode()
