#!/usr/bin/env python3
"""
ChromaDB问题修复工具

解决"no such column: collections.topic"等ChromaDB相关错误
"""

import os
import shutil
import sqlite3
import time
from typing import Dict, Any
from src.knowledge_base.knowledge_base_manager import KnowledgeBaseManager
from src.persistence.database_manager import DatabaseManager


def check_chromadb_directory(chroma_dir: str = "./chroma_db") -> Dict[str, Any]:
    """检查ChromaDB目录状态"""
    print(f"🔍 检查ChromaDB目录: {chroma_dir}")
    
    status = {
        'directory_exists': os.path.exists(chroma_dir),
        'files': [],
        'size_mb': 0,
        'issues': []
    }
    
    if status['directory_exists']:
        try:
            for root, _, files in os.walk(chroma_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    file_size = os.path.getsize(file_path)
                    status['files'].append({
                        'path': file_path,
                        'size': file_size
                    })
                    status['size_mb'] += file_size / (1024 * 1024)
            
            print(f"  ✅ 目录存在，包含 {len(status['files'])} 个文件，总大小: {status['size_mb']:.2f} MB")
            
            # 检查是否有SQLite数据库文件
            sqlite_files = [f for f in status['files'] if f['path'].endswith('.sqlite') or f['path'].endswith('.db')]
            if sqlite_files:
                print(f"  📊 发现 {len(sqlite_files)} 个数据库文件")
                for db_file in sqlite_files:
                    try:
                        conn = sqlite3.connect(db_file['path'])
                        cursor = conn.cursor()
                        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                        tables = cursor.fetchall()
                        print(f"    {db_file['path']}: {len(tables)} 个表")
                        
                        # 检查是否有collections表
                        if ('collections',) in tables:
                            cursor.execute("PRAGMA table_info(collections);")
                            columns = cursor.fetchall()
                            column_names = [col[1] for col in columns]
                            print(f"      collections表列: {column_names}")
                            
                            if 'topic' not in column_names:
                                status['issues'].append(f"collections表缺少topic列: {db_file['path']}")
                        
                        conn.close()
                    except Exception as e:
                        status['issues'].append(f"无法检查数据库文件 {db_file['path']}: {e}")
                        
        except Exception as e:
            status['issues'].append(f"无法访问目录: {e}")
    else:
        print(f"  ❌ 目录不存在")
    
    return status


def clean_chromadb_directory(chroma_dir: str = "./chroma_db", backup: bool = True) -> bool:
    """清理ChromaDB目录"""
    print(f"🧹 清理ChromaDB目录: {chroma_dir}")
    
    if not os.path.exists(chroma_dir):
        print(f"  ✅ 目录不存在，无需清理")
        return True
    
    try:
        if backup:
            backup_dir = f"{chroma_dir}_backup_{int(os.time.time())}"
            print(f"  📦 创建备份: {backup_dir}")
            shutil.copytree(chroma_dir, backup_dir)
        
        print(f"  🗑️  删除目录: {chroma_dir}")
        shutil.rmtree(chroma_dir)
        
        print(f"  📁 重新创建目录: {chroma_dir}")
        os.makedirs(chroma_dir)
        
        print(f"  ✅ 清理完成")
        return True
        
    except Exception as e:
        print(f"  ❌ 清理失败: {e}")
        return False


def test_chromadb_functionality(chroma_dir: str = "./chroma_db") -> bool:
    """测试ChromaDB功能"""
    print(f"🧪 测试ChromaDB功能")
    
    try:
        # 创建测试用的KnowledgeBaseManager
        kb_manager = KnowledgeBaseManager(
            collection_name_prefix="test_fix",
            db_directory=chroma_dir
        )
        
        test_novel_id = 999999  # 使用一个不太可能冲突的ID
        
        print(f"  📝 测试添加文本...")
        test_texts = [
            "这是一个测试文本，用于验证ChromaDB功能。",
            "另一个测试文本，包含不同的内容。"
        ]
        
        kb_manager.add_texts(test_novel_id, test_texts)
        print(f"  ✅ 成功添加 {len(test_texts)} 个文本")
        
        print(f"  🔍 测试检索功能...")
        results = kb_manager.retrieve_relevant_chunks(test_novel_id, "测试", k=2)
        print(f"  ✅ 成功检索到 {len(results)} 个结果")
        
        print(f"  🗑️  清理测试数据...")
        kb_manager.delete_collection(test_novel_id)
        print(f"  ✅ 测试完成")
        
        return True
        
    except Exception as e:
        print(f"  ❌ 测试失败: {e}")
        return False


def fix_all_novel_collections() -> bool:
    """修复所有小说的知识库集合"""
    print(f"🔧 修复所有小说的知识库集合")
    
    try:
        db_manager = DatabaseManager()
        novels = db_manager.get_all_novels()
        
        if not novels:
            print(f"  ℹ️  没有找到小说数据")
            return True
        
        print(f"  📚 找到 {len(novels)} 部小说")
        
        kb_manager = KnowledgeBaseManager()
        
        for novel in novels:
            novel_id = novel['id']
            print(f"  🔧 修复小说 {novel_id} 的知识库...")
            
            try:
                # 尝试获取集合统计信息
                stats = kb_manager.get_collection_stats(novel_id)
                if stats.get('error'):
                    print(f"    ⚠️  发现问题: {stats['error']}")
                    # 清理并重新创建
                    kb_manager.clear_knowledge_base(novel_id)
                    print(f"    ✅ 已清理小说 {novel_id} 的知识库")
                else:
                    print(f"    ✅ 小说 {novel_id} 的知识库正常 ({stats.get('document_count', 0)} 个文档)")
                    
            except Exception as e:
                print(f"    ❌ 修复小说 {novel_id} 失败: {e}")
                # 尝试强制清理
                try:
                    kb_manager.clear_knowledge_base(novel_id)
                    print(f"    ✅ 强制清理小说 {novel_id} 的知识库")
                except Exception as e2:
                    print(f"    ❌ 强制清理也失败: {e2}")
        
        print(f"  ✅ 修复完成")
        return True
        
    except Exception as e:
        print(f"  ❌ 修复失败: {e}")
        return False


def main():
    """主函数"""
    print("🚀 ChromaDB问题修复工具")
    print("=" * 50)
    
    chroma_dir = "./chroma_db"
    
    # 1. 检查当前状态
    print("\n1️⃣ 检查当前状态")
    status = check_chromadb_directory(chroma_dir)
    
    if status['issues']:
        print(f"\n⚠️  发现 {len(status['issues'])} 个问题:")
        for issue in status['issues']:
            print(f"  - {issue}")
    
    # 2. 询问用户是否要清理
    if status['directory_exists'] and (status['issues'] or status['size_mb'] > 100):
        print(f"\n❓ 是否要清理ChromaDB目录？")
        print(f"   当前大小: {status['size_mb']:.2f} MB")
        print(f"   发现问题: {len(status['issues'])} 个")
        
        choice = input("输入 'y' 清理，'n' 跳过，或直接回车默认清理: ").strip().lower()
        
        if choice in ['', 'y', 'yes']:
            print("\n2️⃣ 清理ChromaDB目录")
            if clean_chromadb_directory(chroma_dir):
                print("✅ 清理成功")
            else:
                print("❌ 清理失败")
                return
        else:
            print("⏭️  跳过清理")
    
    # 3. 测试功能
    print("\n3️⃣ 测试ChromaDB功能")
    if test_chromadb_functionality(chroma_dir):
        print("✅ ChromaDB功能正常")
    else:
        print("❌ ChromaDB功能异常")
        return
    
    # 4. 修复现有小说的知识库
    print("\n4️⃣ 修复现有小说的知识库")
    if fix_all_novel_collections():
        print("✅ 修复完成")
    else:
        print("❌ 修复失败")
    
    print("\n🎉 ChromaDB修复完成！")
    print("现在可以重新运行小说生成系统了。")


if __name__ == "__main__":
    main()
