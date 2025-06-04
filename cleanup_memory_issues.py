#!/usr/bin/env python3
"""
清理记忆问题的简化脚本
直接操作数据库解决人物记忆混杂问题
"""

import sqlite3
import os
import json
from datetime import datetime, timezone

def backup_database(db_file):
    """备份数据库"""
    backup_file = f"{db_file}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    try:
        # 使用SQLite的备份功能
        source = sqlite3.connect(db_file)
        backup = sqlite3.connect(backup_file)
        source.backup(backup)
        source.close()
        backup.close()
        print(f"✅ 数据库已备份到: {backup_file}")
        return backup_file
    except Exception as e:
        print(f"❌ 备份失败: {e}")
        return None

def analyze_memory_issues(db_file):
    """分析记忆问题"""
    print(f"🔍 分析数据库: {db_file}")
    
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        # 检查重复角色名称
        cursor.execute("""
            SELECT name, COUNT(*) as count, GROUP_CONCAT(novel_id || ':' || id) as details
            FROM characters 
            GROUP BY name 
            HAVING COUNT(*) > 1
            ORDER BY count DESC
        """)
        
        duplicate_names = cursor.fetchall()
        
        issues = {
            'duplicate_characters': [],
            'novel_stats': {},
            'recommendations': []
        }
        
        if duplicate_names:
            print(f"  ⚠️  发现 {len(duplicate_names)} 个重复的角色名称:")
            for name, count, details in duplicate_names:
                print(f"    '{name}' 出现 {count} 次: {details}")
                issues['duplicate_characters'].append({
                    'name': name,
                    'count': count,
                    'details': details
                })
        
        # 获取各小说统计
        cursor.execute("""
            SELECT n.id, n.user_theme, COUNT(c.id) as char_count
            FROM novels n
            LEFT JOIN characters c ON n.id = c.novel_id
            GROUP BY n.id, n.user_theme
            ORDER BY n.id
        """)
        
        novel_stats = cursor.fetchall()
        print(f"\n  📊 小说统计:")
        for novel_id, theme, char_count in novel_stats:
            print(f"    小说 {novel_id}: {char_count} 个角色 - {theme[:50]}...")
            issues['novel_stats'][novel_id] = {
                'theme': theme,
                'character_count': char_count
            }
        
        # 生成建议
        if duplicate_names:
            issues['recommendations'].append("建议重命名或删除重复的角色")
        
        if len(novel_stats) > 10:
            issues['recommendations'].append("考虑清理不需要的小说数据")
        
        conn.close()
        return issues
        
    except Exception as e:
        print(f"❌ 分析失败: {e}")
        return None

def fix_duplicate_characters(db_file, interactive=True):
    """修复重复角色问题"""
    print(f"🔧 修复重复角色问题...")
    
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        # 获取重复角色详情
        cursor.execute("""
            SELECT name, novel_id, id, role_in_story, creation_date
            FROM characters 
            WHERE name IN (
                SELECT name FROM characters GROUP BY name HAVING COUNT(*) > 1
            )
            ORDER BY name, novel_id
        """)
        
        duplicate_chars = cursor.fetchall()
        
        if not duplicate_chars:
            print("  ✅ 未发现重复角色")
            conn.close()
            return True
        
        print(f"  发现重复角色:")
        current_name = None
        chars_to_process = []
        
        for name, novel_id, char_id, role, creation_date in duplicate_chars:
            if name != current_name:
                if chars_to_process:
                    # 处理前一组重复角色
                    if interactive:
                        action = handle_duplicate_group_interactive(chars_to_process)
                    else:
                        action = handle_duplicate_group_auto(chars_to_process)
                    
                    if action:
                        execute_character_action(cursor, action)
                
                current_name = name
                chars_to_process = []
            
            chars_to_process.append({
                'name': name,
                'novel_id': novel_id,
                'id': char_id,
                'role': role,
                'creation_date': creation_date
            })
        
        # 处理最后一组
        if chars_to_process:
            if interactive:
                action = handle_duplicate_group_interactive(chars_to_process)
            else:
                action = handle_duplicate_group_auto(chars_to_process)
            
            if action:
                execute_character_action(cursor, action)
        
        conn.commit()
        conn.close()
        print("  ✅ 重复角色问题修复完成")
        return True
        
    except Exception as e:
        print(f"❌ 修复失败: {e}")
        return False

def handle_duplicate_group_interactive(chars):
    """交互式处理重复角色组"""
    name = chars[0]['name']
    print(f"\n  处理重复角色 '{name}':")
    
    for i, char in enumerate(chars):
        print(f"    {i+1}. 小说 {char['novel_id']}, ID {char['id']}, 角色: {char['role']}")
    
    print(f"    {len(chars)+1}. 重命名所有角色（添加小说ID后缀）")
    print(f"    {len(chars)+2}. 跳过")
    
    while True:
        try:
            choice = input(f"  选择操作 (1-{len(chars)+2}): ").strip()
            choice_num = int(choice)
            
            if 1 <= choice_num <= len(chars):
                # 删除其他角色，保留选中的
                keep_id = chars[choice_num - 1]['id']
                delete_ids = [char['id'] for char in chars if char['id'] != keep_id]
                return {'action': 'delete', 'ids': delete_ids}
            
            elif choice_num == len(chars) + 1:
                # 重命名所有角色
                renames = []
                for char in chars:
                    new_name = f"{char['name']}_小说{char['novel_id']}"
                    renames.append({'id': char['id'], 'new_name': new_name})
                return {'action': 'rename', 'renames': renames}
            
            elif choice_num == len(chars) + 2:
                # 跳过
                return None
            
            else:
                print("  无效选择，请重试")
                
        except ValueError:
            print("  请输入有效数字")

def handle_duplicate_group_auto(chars):
    """自动处理重复角色组"""
    # 自动策略：重命名所有角色，添加小说ID后缀
    renames = []
    for char in chars:
        new_name = f"{char['name']}_小说{char['novel_id']}"
        renames.append({'id': char['id'], 'new_name': new_name})
    
    print(f"  自动重命名角色组 '{chars[0]['name']}'")
    return {'action': 'rename', 'renames': renames}

def execute_character_action(cursor, action):
    """执行角色操作"""
    if action['action'] == 'delete':
        for char_id in action['ids']:
            cursor.execute("DELETE FROM characters WHERE id = ?", (char_id,))
            print(f"    删除角色 ID {char_id}")
    
    elif action['action'] == 'rename':
        for rename in action['renames']:
            cursor.execute(
                "UPDATE characters SET name = ? WHERE id = ?",
                (rename['new_name'], rename['id'])
            )
            print(f"    重命名角色 ID {rename['id']} -> {rename['new_name']}")

def clear_novel_data(db_file, novel_id, clear_characters=True, clear_chapters=False):
    """清除指定小说的数据"""
    print(f"🗑️  清除小说 {novel_id} 的数据...")
    
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        if clear_characters:
            cursor.execute("DELETE FROM characters WHERE novel_id = ?", (novel_id,))
            deleted_chars = cursor.rowcount
            print(f"  删除了 {deleted_chars} 个角色")
        
        if clear_chapters:
            cursor.execute("DELETE FROM chapters WHERE novel_id = ?", (novel_id,))
            deleted_chapters = cursor.rowcount
            print(f"  删除了 {deleted_chapters} 个章节")
        
        # 清除知识库条目
        cursor.execute("DELETE FROM knowledge_base_entries WHERE novel_id = ?", (novel_id,))
        deleted_kb = cursor.rowcount
        print(f"  删除了 {deleted_kb} 个知识库条目")
        
        conn.commit()
        conn.close()
        print(f"  ✅ 小说 {novel_id} 数据清除完成")
        return True
        
    except Exception as e:
        print(f"❌ 清除失败: {e}")
        return False

def main():
    """主函数"""
    print("🧹 小说生成系统记忆清理工具")
    print("=" * 50)
    
    # 切换到正确目录
    os.chdir('/media/sc/data/sc/novel_generation')
    
    db_files = ['novel_mvp.db', 'main_novel_generation.db']
    
    for db_file in db_files:
        if not os.path.exists(db_file):
            print(f"⚠️  数据库文件不存在: {db_file}")
            continue
        
        print(f"\n处理数据库: {db_file}")
        print("-" * 30)
        
        # 备份数据库
        backup_file = backup_database(db_file)
        if not backup_file:
            print("❌ 无法备份数据库，跳过处理")
            continue
        
        # 分析问题
        issues = analyze_memory_issues(db_file)
        if not issues:
            continue
        
        # 询问是否修复
        if issues['duplicate_characters']:
            print(f"\n发现 {len(issues['duplicate_characters'])} 个重复角色问题")
            
            fix_choice = input("是否修复重复角色问题? (y/N): ").strip().lower()
            if fix_choice == 'y':
                interactive = input("使用交互模式? (Y/n): ").strip().lower() != 'n'
                fix_duplicate_characters(db_file, interactive)
        
        # 询问是否清理小说
        if len(issues['novel_stats']) > 5:
            print(f"\n发现 {len(issues['novel_stats'])} 部小说")
            clean_choice = input("是否清理不需要的小说数据? (y/N): ").strip().lower()
            
            if clean_choice == 'y':
                print("小说列表:")
                for novel_id, stats in issues['novel_stats'].items():
                    print(f"  {novel_id}: {stats['character_count']} 角色 - {stats['theme'][:50]}...")
                
                novel_ids_to_clean = input("输入要清理的小说ID (用逗号分隔，或输入'all'清理所有): ").strip()
                
                if novel_ids_to_clean.lower() == 'all':
                    for novel_id in issues['novel_stats'].keys():
                        clear_novel_data(db_file, novel_id)
                elif novel_ids_to_clean:
                    try:
                        ids = [int(x.strip()) for x in novel_ids_to_clean.split(',')]
                        for novel_id in ids:
                            if novel_id in issues['novel_stats']:
                                clear_novel_data(db_file, novel_id)
                            else:
                                print(f"⚠️  小说 ID {novel_id} 不存在")
                    except ValueError:
                        print("❌ 无效的小说ID格式")
    
    print("\n🎉 清理完成！")
    print("建议:")
    print("  1. 重新运行测试脚本验证修复效果")
    print("  2. 如果有问题，可以从备份文件恢复")
    print("  3. 定期运行此清理工具维护数据库")

if __name__ == "__main__":
    main()
